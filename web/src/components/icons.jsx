// Line icons in the spirit of Apple's SF Symbols: 24px grid, round caps, drawn with the text
// colour so they follow light/dark mode and the selected tab's tint.
const Icon = ({ children, size = 24, ...props }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...props}>{children}</svg>
)

export const SparkleIcon = (p) => (
  <Icon {...p}><path d="M11 3.5c.5 3.9 2.6 6 6.5 6.5-3.9.5-6 2.6-6.5 6.5-.5-3.9-2.6-6-6.5-6.5 3.9-.5 6-2.6 6.5-6.5z" />
    <path d="M18.5 15c.2 1.6 1 2.4 2.5 2.5-1.5.1-2.3.9-2.5 2.5-.2-1.6-1-2.4-2.5-2.5 1.5-.1 2.3-.9 2.5-2.5z" /></Icon>
)
export const RobotIcon = (p) => (
  <Icon {...p}><path d="M9 3.5 12 6l3-2.5" /><rect x="5.5" y="6" width="13" height="10" rx="2.5" />
    <path d="M9.5 10.5h.01M14.5 10.5h.01M9.5 13.5h5M8 16v4.5M16 16v4.5" /></Icon>
)
export const ShieldIcon = (p) => (
  <Icon {...p}><path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.3 7.5 9.5 4.3-1.2 7.5-4.9 7.5-9.5V6z" /><path d="M12 7.5v9M8 11h8" /></Icon>
)
export const BoxIcon = (p) => (
  <Icon {...p}><path d="M3.5 7.5 12 3l8.5 4.5v9L12 21l-8.5-4.5z" /><path d="M3.5 7.5 12 12l8.5-4.5M12 12v9" /></Icon>
)
export const CartIcon = (p) => (
  <Icon {...p}><path d="M3 4h2l2.2 10.2a1.5 1.5 0 0 0 1.5 1.2h8.6a1.5 1.5 0 0 0 1.5-1.1L20.5 8H6.2" />
    <circle cx="9.5" cy="19.5" r="1.3" /><circle cx="17" cy="19.5" r="1.3" /></Icon>
)
export const PlaneIcon = (p) => (
  <Icon {...p}><path d="M12 2.8c.9 0 1.4 1 1.4 2.2v4.4l7.4 4.3v2l-7.4-2.3v4.2l2.2 1.7v1.6L12 20l-3.6.9v-1.6l2.2-1.7v-4.2l-7.4 2.3v-2l7.4-4.3V5c0-1.2.5-2.2 1.4-2.2z" /></Icon>
)
export const DropsIcon = (p) => (
  <Icon {...p}><path d="M8.5 3.5S4 8.6 4 11.6a4.5 4.5 0 0 0 9 0c0-3-4.5-8.1-4.5-8.1z" />
    <path d="M16.5 10.5s-3.5 3.9-3.5 6.3a3.5 3.5 0 0 0 7 0c0-2.4-3.5-6.3-3.5-6.3z" /></Icon>
)
export const GearIcon = (p) => (
  <Icon {...p}><circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></Icon>
)
export const ScanIcon = (p) => (
  <Icon {...p}><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2" />
    <path d="M7 8v8M10 8v8M13 8v8M17 8v8" /></Icon>
)
export const TimerIcon = (p) => (
  <Icon {...p}><circle cx="12" cy="13" r="8" /><path d="M12 9v4l2.5 2M9.5 2.5h5" /></Icon>
)
export const HomeIcon = (p) => (
  <Icon {...p}><path d="M3.5 10.5 12 3.5l8.5 7" /><path d="M5.5 9v10.5h4.5v-6h4v6h4.5V9" /></Icon>
)
export const JournalIcon = (p) => (
  <Icon {...p}><path d="M6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5v-15A1.5 1.5 0 0 1 6.5 3z" />
    <path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19v-3M9 7.5h6M9 11h4" /></Icon>
)
export const ClockIcon = (p) => (
  <Icon {...p}><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></Icon>
)
export const BoltIcon = (p) => <Icon {...p}><path d="M13 3 5 13.5h6L10.5 21 19 10.5h-6z" /></Icon>
export const SearchIcon = (p) => <Icon {...p}><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4.2-4.2" /></Icon>
export const ChevronIcon = (p) => <Icon {...p}><path d="m9 6 6 6-6 6" /></Icon>
export const CalendarIcon = (p) => (
  <Icon {...p}><rect x="3.5" y="5" width="17" height="15.5" rx="2.5" /><path d="M3.5 10h17M8 3v4M16 3v4" />
    <path d="M8 14h.01M12 14h.01M16 14h.01M8 17.5h.01M12 17.5h.01" /></Icon>
)
export const DiceIcon = (p) => (
  <Icon {...p}><rect x="3.5" y="3.5" width="17" height="17" rx="3.5" />
    <circle cx="8.5" cy="8.5" r="1" fill="currentColor" /><circle cx="15.5" cy="15.5" r="1" fill="currentColor" />
    <circle cx="12" cy="12" r="1" fill="currentColor" /><circle cx="15.5" cy="8.5" r="1" fill="currentColor" />
    <circle cx="8.5" cy="15.5" r="1" fill="currentColor" /></Icon>
)
export const BallIcon = (p) => (
  <Icon {...p}><circle cx="12" cy="12" r="8.5" /><path d="M12 3.5c-1.5 3.5-1.2 7 1 8.5s6.3 1.5 7.4-.5" />
    <path d="M5 7.2c3.3.2 6.2 1.8 7 4.8M12 12c-1.8 2.7-5.2 4.3-8.2 4.1M13 20.4c-.4-3.3.6-6.7 3-8.4" /></Icon>
)
export const GridIcon = (p) => (
  <Icon {...p}><rect x="3.5" y="3.5" width="7" height="7" rx="2" /><rect x="13.5" y="3.5" width="7" height="7" rx="2" />
    <rect x="3.5" y="13.5" width="7" height="7" rx="2" /><rect x="13.5" y="13.5" width="7" height="7" rx="2" /></Icon>
)
export const VideoIcon = (p) => (
  <Icon {...p}><rect x="3" y="6" width="13" height="12" rx="2.5" /><path d="m16 10.5 5-3v9l-5-3" /></Icon>
)
export const ShoeIcon = (p) => (
  <Icon {...p}><path d="M3 16.5V9.5l4.5-3 2 3.5c1.5 1.3 4 1.8 6 2.3 3 .7 5.5 1.8 5.5 4.2v.5H3z" />
    <path d="M3 19.5h18M9.5 10l1.5-1M11.5 11.3 13 10.2" /></Icon>
)
export const TrophyIcon = (p) => (
  <Icon {...p}><path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H4.5v1.5A3 3 0 0 0 8 10.4M16 6h3.5v1.5a3 3 0 0 1-3.5 2.9" />
    <path d="M12 13v4M8.5 20.5h7M9.5 17h5v3.5h-5z" /></Icon>
)
export const PenIcon = (p) => (
  <Icon {...p}><path d="M15.5 4.5 19.5 8.5 8.5 19.5 3.5 20.5 4.5 15.5z" /><path d="M13 7l4 4" /></Icon>
)
export const GamepadIcon = (p) => (
  <Icon {...p}><path d="M7 7.5h10a4.5 4.5 0 0 1 4.4 5.5l-1 4.4a2.3 2.3 0 0 1-4 .9L14.5 16h-5l-1.9 2.3a2.3 2.3 0 0 1-4-.9l-1-4.4A4.5 4.5 0 0 1 7 7.5z" />
    <path d="M8 10.5v3M6.5 12h3M15.5 11.2h.01M17.5 13h.01" /></Icon>
)
// A bell curve: "the median" (the middle of everyone's times).
export const BellCurveIcon = (p) => (
  <Icon {...p}><path d="M2.5 19.5h19" /><path d="M3 17.5c3.5 0 4.5-1.5 6-6S11 5.5 12 5.5s1.5 1.5 3 6 2.5 6 6 6" /></Icon>
)
// A knight: chess.
export const ChessIcon = (p) => (
  <Icon {...p}><path d="M6.5 20.5h11" /><path d="M8 20.5c0-3.2 1.2-5.2 3.4-7.1-2.1.2-3.6-.4-4.4-1.8 1.4-2.4 3.3-5 5.6-6.6 3.2.6 5.4 3.6 5.4 7.6 0 3.2-.9 5.6-.9 7.9" />
    <path d="M12.3 8.6h.01" /></Icon>
)
// An open book: reading.
export const BookIcon = (p) => (
  <Icon {...p}><path d="M12 6.5c-1.8-1.3-4.3-2-7.5-2v13c3.2 0 5.7.7 7.5 2 1.8-1.3 4.3-2 7.5-2v-13c-3.2 0-5.7.7-7.5 2z" />
    <path d="M12 6.5v13" /></Icon>
)
// Speech marks: a saved quote.
export const QuoteIcon = (p) => (
  <Icon {...p}><path d="M5 17.5c2.5-1 4-3.2 4-6.5V7H4.5v5H8M15 17.5c2.5-1 4-3.2 4-6.5V7h-4.5v5H18" /></Icon>
)
// A puzzle piece: an add-on (DLC).
export const PuzzleIcon = (p) => (
  <Icon {...p}><path d="M4.5 8.5h4a2.2 2.2 0 1 1 4.4 0h4.6v4.6a2.2 2.2 0 1 1 0 4.4v3h-13z" /></Icon>
)
export const HourglassIcon = (p) => (
  <Icon {...p}><path d="M7 3.5h10M7 20.5h10" /><path d="M8 3.5c0 4.5 8 5.5 8 8.5s-8 4-8 8.5M16 3.5c0 4.5-8 5.5-8 8.5s8 4 8 8.5" /></Icon>
)
export const CarIcon = (p) => (
  <Icon {...p}><path d="M4 15.5v-3l1.8-4.2A2 2 0 0 1 7.6 7h8.8a2 2 0 0 1 1.8 1.3L20 12.5v3" /><path d="M3 15.5h18v2.5H3zM4.5 12.5h15" />
    <circle cx="7.5" cy="18.5" r="1.6" /><circle cx="16.5" cy="18.5" r="1.6" /></Icon>
)
// "Under construction": a spanner.
export const WrenchIcon = (p) => (
  <Icon {...p}><path d="M14.7 6.3a4 4 0 0 0 4.8 5.2l-8.3 8.3a2 2 0 0 1-2.8-2.8l8.3-8.3a4 4 0 0 0-5.2-4.8l2.6 2.6-.4 2.2-2.2.4z" /></Icon>
)
