import { BookIcon, GridIcon, QuoteIcon, SparkleIcon, TrophyIcon } from '../../components/icons.jsx'
import BookPanel from './BookPanel.jsx'
import { AddBookPanel } from './readingParts.jsx'
import { BooksView, Dashboard, QuotesView, ReadingTiles, StatsView } from './ReadingViews.jsx'
import { RecsView } from './RecsView.jsx'

// Reading: your books (api/app/reading.py) - found on Open Library by title, author or a scanned
// ISBN, or imported from Goodreads - with the page you're on, a yearly goal, stars, reviews and
// quotes, and suggestions of what to read next (For you). Pages live at /reading/<path>; reading days show on the calendar, books can be
// mentioned in the journal.
export default {
  id: 'reading',
  name: 'Reading',
  // its colour (ink blue: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx scenes)
  hue: '#4f8fc9',
  banner: { scene: 'forest', seed: 17, tagline: 'Better books. Bigger worlds.' },
  what: "Books: what you're reading, your goal, ratings and quotes",
  Icon: BookIcon,
  home: { Tiles: ReadingTiles },
  actions: [
    { label: 'Add a book', Icon: BookIcon, run: (app) => app.openPanel('addbook', {}) },
  ],
  panels: { book: BookPanel, addbook: AddBookPanel },
  pages: [
    { path: 'dashboard', label: 'Dashboard', Icon: TrophyIcon, render: () => <Dashboard /> },
    { path: 'books', label: 'Books', Icon: BookIcon, render: () => <BooksView /> },
    { path: 'foryou', label: 'For you', Icon: SparkleIcon, render: () => <RecsView /> },
    { path: 'stats', label: 'Stats', Icon: GridIcon, render: () => <StatsView /> },
    { path: 'quotes', label: 'Quotes', Icon: QuoteIcon, render: () => <QuotesView /> },
  ],
}
