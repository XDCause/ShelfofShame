import { BookIcon, GridIcon, JournalIcon, LanguageIcon, TrophyIcon } from '../../components/icons.jsx'
import { LanguageTiles } from './HomeTiles.jsx'
import { part } from '../lazy.js'

// its pages and panels: loaded when first shown (modules/lazy.js)
const TodayView = part(() => import('./LanguageViews.jsx'), 'TodayView')
const CardsView = part(() => import('./LanguageViews.jsx'), 'CardsView')
const LogView = part(() => import('./LanguageViews.jsx'), 'LogView')
const ResourcesView = part(() => import('./LanguageViews.jsx'), 'ResourcesView')
const ProgressView = part(() => import('./LanguageProgress.jsx'), 'ProgressView')
const ReviewView = part(() => import('./ReviewView.jsx'), 'ReviewView')
const LanguagePanel = part(() => import('./LanguagePanels.jsx'), 'LanguagePanel')
const CardPanel = part(() => import('./LanguagePanels.jsx'), 'CardPanel')
const BulkPanel = part(() => import('./LanguagePanels.jsx'), 'BulkPanel')
const StudyPanel = part(() => import('./LanguagePanels.jsx'), 'StudyPanel')
const ResourcePanel = part(() => import('./LanguagePanels.jsx'), 'ResourcePanel')

// Language learning (2026-11-17): the best of the language apps in one place, with no outside service. A deck per
// language on FSRS spaced repetition (Anki's scheduler: api/app/srs.py) - flip, type the answer (accents forgiven but
// noted), listen (the browser's own voice) and cloze sentences (Clozemaster); a study log with a streak and a daily
// minutes goal (Duolingo); input hours toward Dreaming Spanish / Refold milestones; resources you're working through
// (LingQ's library); tutor and class notes (italki); a CEFR can-do checklist (Busuu / Babbel's levels).
export default {
  id: 'language',
  name: 'Language learning',
  // its colour (a raspberry rose: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx)
  hue: '#c8507a',
  banner: { scene: 'coast', seed: 47, time: 'dawn', extras: ['birds', 'distant'], tagline: 'A little every day, a lot every year.' },
  what: 'Flashcards that space themselves, a study log, input hours, resources, your level',
  Icon: LanguageIcon,
  home: { Tiles: LanguageTiles },
  actions: [{ label: 'Review cards', Icon: LanguageIcon, run: (app) => app.navigate('/language/review') }],
  panels: { langlanguage: LanguagePanel, langcard: CardPanel, langbulk: BulkPanel, langstudy: StudyPanel, langresource: ResourcePanel },
  pages: [
    { path: 'today', label: 'Today', Icon: TrophyIcon, render: () => <TodayView /> },
    { path: 'review', label: 'Review', Icon: LanguageIcon, render: () => <ReviewView /> },
    { path: 'cards', label: 'Cards', Icon: GridIcon, render: () => <CardsView /> },
    { path: 'log', label: 'Study log', Icon: JournalIcon, render: () => <LogView /> },
    { path: 'resources', label: 'Resources', Icon: BookIcon, render: () => <ResourcesView /> },
    { path: 'progress', label: 'Progress', Icon: TrophyIcon, render: () => <ProgressView /> },
  ],
}
