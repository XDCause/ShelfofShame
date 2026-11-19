import { describe, expect, it } from 'vitest'
import { esc, pickGames, playersText, shelfHtml, weightWord } from '../modules/boardgames/shelfFile.js'

const G = (o) => ({ kind: 'game', status: 'Owned', categories: [], plays: 0, ...o })
const GAMES = [
  G({ game_id: 1, name: 'Wingspan', min_players: 1, max_players: 5, play_minutes: 70, weight: 2.45, year: 2019, rating: 9, plays: 12,
    price_paid: 89.95, notes: 'SECRET NOTE', shop_name: 'Some Shop', bgg_url: 'https://boardgamegeek.com/boardgame/266192', photo_url: '/x' }),
  G({ game_id: 2, name: 'Wingspan: European Expansion', kind: 'expansion', base_game_id: 1 }),
  G({ game_id: 3, name: 'azul', min_players: 2, max_players: 4, play_minutes: 40 }),
  G({ game_id: 4, name: 'Gloomhaven', status: 'Wanted', min_players: 1, max_players: 4 }),
  G({ game_id: 5, name: 'Catan', status: 'Gone' }),
  G({ game_id: 6, name: 'Root', status: 'Borrowed' }),
  G({ game_id: 7, name: 'Lone expansion', kind: 'expansion', base_game_id: 99 }),
  G({ game_id: 8, name: '<script>alert(1)</script>', status: 'To sell' }),
]

describe('share my shelf: the file', () => {
  it('picks the owned games (to sell too), expansions on their game, the rest as their own cards', () => {
    const cards = pickGames(GAMES)
    expect(cards.map((g) => g.name)).toEqual(['<script>alert(1)</script>', 'azul', 'Lone expansion', 'Wingspan'])
    expect(cards.find((g) => g.game_id === 1).riders).toEqual(['Wingspan: European Expansion'])
    expect(pickGames(GAMES, { borrowed: true }).map((g) => g.name)).toContain('Root')
    expect(pickGames(GAMES, { expansions: false }).find((g) => g.game_id === 1).riders).toEqual([])
    expect(pickGames(GAMES, { list: 'wanted' }).map((g) => g.name)).toEqual(['Gloomhaven'])
  })

  it('never puts in prices, notes or shops, and escapes every name', () => {
    const html = shelfHtml(GAMES, { rating: true, plays: true, links: true })
    expect(html).not.toContain('89.95')
    expect(html).not.toContain('SECRET NOTE')
    expect(html).not.toContain('Some Shop')
    expect(html).not.toContain('<script>alert(1)</script>')
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).toContain('Rated 9/10')
    expect(html).toContain('Played 12 times')
    expect(html).toContain('href="https://boardgamegeek.com/boardgame/266192"')
    expect(html).toContain('+ Wingspan: European Expansion')
    expect(html).toContain('1-5 players · 70 min · Medium-light · 2019')
  })

  it('leaves ratings, plays and links out unless asked, and names the file by its list', () => {
    const html = shelfHtml(GAMES, {})
    expect(html).not.toContain('Rated 9/10')
    expect(html).not.toContain('Played 12')
    expect(html).not.toContain('boardgamegeek.com')
    expect(html).toContain('<title>My board games</title>')
    expect(shelfHtml(GAMES, { list: 'wanted' })).toContain("<title>Games I&#39;d like</title>")
    expect(shelfHtml(GAMES, { title: 'Sam & Jo\'s games', note: 'Pick one!' })).toContain('<h1>Sam &amp; Jo&#39;s games</h1>')
  })

  it('uses a photo only when one was made, and carries the filter data', () => {
    const html = shelfHtml(GAMES, { photos: { 1: 'data:image/jpeg;base64,AAAA' } })
    expect(html).toContain('<img src="data:image/jpeg;base64,AAAA"')
    expect(html.match(/<img /g)).toHaveLength(1)
    expect(html).toContain('data-min="2" data-max="4" data-time="40"')
  })

  it('the small words', () => {
    expect(esc('a<b>"c"&\'')).toBe('a&lt;b&gt;&quot;c&quot;&amp;&#39;')
    expect(weightWord(1.2)).toBe('Light')
    expect(weightWord(4.5)).toBe('Heavy')
    expect(weightWord(null)).toBe(null)
    expect(playersText({ min_players: 2, max_players: 2 })).toBe('2 players')
    expect(playersText({ min_players: 1 })).toBe('1 player')
    expect(playersText({})).toBe(null)
  })

  it("the file's own filters: players, time and search", () => {
    const html = shelfHtml(GAMES, {})
    document.body.innerHTML = html.slice(html.indexOf('<header>'), html.indexOf('<script>'))
    new Function(html.slice(html.indexOf('<script>') + 8, html.indexOf('</script>')))()   // the file's own script, run as the browser would
    const shown = () => [...document.querySelectorAll('#games > li')].filter((li) => !li.hidden).map((li) => li.querySelector('h2').textContent)
    const pick = (id, value) => { const el = document.getElementById(id); el.value = value; el.dispatchEvent(new Event('input')) }
    expect(shown()).toHaveLength(4)
    pick('p', '5')                                          // 5 players: Wingspan (1-5), and games with no count known
    expect(shown()).toEqual(['<script>alert(1)</script>', 'Lone expansion', 'Wingspan'])
    pick('t', '60')                                         // ...in an hour: not Wingspan (70 min)
    expect(shown()).not.toContain('Wingspan')
    pick('p', '')
    pick('t', '')
    pick('q', 'AZ')
    expect(shown()).toEqual(['azul'])
    expect(document.getElementById('n').textContent).toBe('1 of 4 games')
    document.body.innerHTML = ''
  })
})
