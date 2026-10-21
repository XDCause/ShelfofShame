import { BoxIcon, GridIcon, SproutIcon, TrophyIcon } from '../../components/icons.jsx'
import { GardenTiles } from './HomeTiles.jsx'
import { part } from '../lazy.js'

// its pages and panels: loaded when first shown (modules/lazy.js)
const ContainerFormPanel = part(() => import('./GardenPanels.jsx'), 'ContainerFormPanel')
const ContainerPanel = part(() => import('./GardenPanels.jsx'), 'ContainerPanel')
const GuidePanel = part(() => import('./GardenPanels.jsx'), 'GuidePanel')
const ItemPanel = part(() => import('./GardenPanels.jsx'), 'ItemPanel')
const NewGuidePanel = part(() => import('./GardenPanels.jsx'), 'NewGuidePanel')
const SpacePanel = part(() => import('./GardenPanels.jsx'), 'SpacePanel')
const HarvestsView = part(() => import('./GardenViews.jsx'), 'HarvestsView')
const PlantsView = part(() => import('./GardenViews.jsx'), 'PlantsView')
const TodayView = part(() => import('./GardenViews.jsx'), 'TodayView')
const DoctorView = part(() => import('./DoctorView.jsx'))
const GuideView = part(() => import('./GuideView.jsx'), 'GuideView')
const SuppliesView = part(() => import('./GuideView.jsx'), 'SuppliesView')
const LayoutView = part(() => import('./LayoutView.jsx'), 'LayoutView')
const PlantingPanel = part(() => import('./PlantingPanel.jsx'))

// Gardening, for an apartment (api/app/garden.py, garden_guide.py, garden_items.py): your balcony,
// windowsills and shelves drawn to scale with your pots on them; each plant's stage, watering, feeding,
// harvest window, notes and photos; Today's jobs and weather tips; a plant guide with what to sow now;
// harvests; supplies and seeds, with Bunnings links; a plant doctor (signs -> what to do). Pages live at
// /gardening/<path>.
export default {
  id: 'gardening',
  name: 'Gardening',
  // its colour (new leaf: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx scenes)
  hue: '#78b043',
  banner: { scene: 'hills', seed: 27, time: 'dawn', extras: ['meadow', 'rainbow', 'clouds'], tagline: 'Grow something every day.' },
  what: 'Balcony and windowsill garden: layout, plants, watering, photos, harvests, Bunnings',
  Icon: SproutIcon,
  home: { Tiles: GardenTiles },
  actions: [{ label: 'Add a plant', Icon: SproutIcon, run: (app) => app.openPanel('planting', {}) }],
  panels: {
    planting: PlantingPanel, gcontainer: ContainerPanel, gcontainerform: ContainerFormPanel, gspace: SpacePanel,
    gguide: GuidePanel, gguidenew: NewGuidePanel, gitem: ItemPanel,
  },
  pages: [
    { path: 'today', label: 'Today', Icon: SproutIcon, render: () => <TodayView /> },
    { path: 'layout', label: 'Layout', Icon: GridIcon, render: () => <LayoutView /> },
    { path: 'plants', label: 'Plants', Icon: SproutIcon, render: () => <PlantsView /> },
    { path: 'guide', label: 'Guide', Icon: SproutIcon, render: () => <GuideView /> },
    { path: 'doctor', label: 'Doctor', Icon: SproutIcon, render: () => <DoctorView /> },
    { path: 'harvests', label: 'Harvests', Icon: TrophyIcon, render: () => <HarvestsView /> },
    { path: 'supplies', label: 'Supplies', Icon: BoxIcon, render: () => <SuppliesView /> },
  ],
}
