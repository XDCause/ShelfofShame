import { BallIcon, BookIcon, BootIcon, BoxIcon, ChessIcon, DiceIcon, GamepadIcon, JournalIcon, PlaneIcon, ShoeIcon, SproutIcon, TargetIcon } from '../components/icons.jsx'

// How the activity feed (api/app/activity.py) looks wherever it's shown (Home, the calendar):
// a colour per verb ("Finished" green, "Used" purple...), and an icon and a name per kind.
export const VERB_TONE = {
  Finished: 'ok', Bought: 'tint', Added: 'tint', Started: 'low', 'Worked on': 'low', Played: 'teal', Trained: 'low',
  Used: 'purple', Logged: 'teal', Wrote: 'teal', Drew: 'purple', Removed: 'out', Unlocked: 'purple', Perfected: 'ok',
  Read: 'teal', 'Started reading': 'low', 'Stopped reading': 'out', Reached: 'ok', 'Progress on': 'tint', Hiked: 'ok',
  Sowed: 'low', Planted: 'ok', Harvested: 'ok', Repotted: 'low', Spotted: 'out', Treated: 'low', Sprouted: 'ok', Flowered: 'purple',
  Photographed: 'teal', Noted: 'teal',
}
export const KIND_ICON = {
  page: JournalIcon, model: PlaneIcon, supply: BoxIcon, game: DiceIcon, volleyball: BallIcon, gear: ShoeIcon, videogame: GamepadIcon,
  chess: ChessIcon, book: BookIcon, goal: TargetIcon, hike: BootIcon,
  planting: SproutIcon, gcontainer: SproutIcon, gspace: SproutIcon,
}
export const KIND_NAME = {
  model: 'Kit', supply: 'Supply', page: 'Journal', game: 'Board game', volleyball: 'Volleyball', gear: 'Gear', videogame: 'Video game',
  chess: 'Chess', book: 'Book', goal: 'Goal', hike: 'Hike',
  planting: 'Plant', gcontainer: 'Pot', gspace: 'Garden',
}
