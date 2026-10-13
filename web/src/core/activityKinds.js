import { BallIcon, BoxIcon, DiceIcon, JournalIcon, PlaneIcon, ShoeIcon } from '../components/icons.jsx'

// How the activity feed (api/app/activity.py) looks wherever it's shown (Home, the calendar):
// a colour per verb ("Finished" green, "Used" purple...), and an icon and a name per kind.
export const VERB_TONE = {
  Finished: 'ok', Bought: 'tint', Added: 'tint', Started: 'low', 'Worked on': 'low', Played: 'teal', Trained: 'low',
  Used: 'purple', Logged: 'teal', Wrote: 'teal', Drew: 'purple', Removed: 'out',
}
export const KIND_ICON = { page: JournalIcon, model: PlaneIcon, supply: BoxIcon, game: DiceIcon, volleyball: BallIcon, gear: ShoeIcon }
export const KIND_NAME = { model: 'Kit', supply: 'Supply', page: 'Journal', game: 'Board game', volleyball: 'Volleyball', gear: 'Gear' }
