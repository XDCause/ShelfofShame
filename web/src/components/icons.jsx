// Line icons in the spirit of Apple's SF Symbols: 24px grid, round caps, drawn with the text
// colour so they follow light/dark mode and the selected tab's tint.
const Icon = ({ children, size = 24, ...props }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...props}>{children}</svg>
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
export const CloseIcon = (p) => <Icon {...p}><path d="M6 6l12 12M18 6 6 18" /></Icon>
export const ChevronIcon = (p) => <Icon {...p}><path d="m9 6 6 6-6 6" /></Icon>
