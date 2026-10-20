import { BoxIcon, GridIcon, SproutIcon, TrophyIcon } from '../../components/icons.jsx'
import { ContainerFormPanel, ContainerPanel, GuidePanel, ItemPanel, NewGuidePanel, SpacePanel } from './GardenPanels.jsx'
import { GardenTiles, HarvestsView, PlantsView, TodayView } from './GardenViews.jsx'
import DoctorView from './DoctorView.jsx'
import { GuideView, SuppliesView } from './GuideView.jsx'
import { LayoutView } from './LayoutView.jsx'
import PlantingPanel from './PlantingPanel.jsx'

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
  banner: { scene: 'hills', seed: 27, tagline: 'Grow something every day.' },
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
