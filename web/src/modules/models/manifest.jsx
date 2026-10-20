import ColoursView from '../../components/ColoursView.jsx'
import { DropsIcon, PlaneIcon, RobotIcon, ShieldIcon } from '../../components/icons.jsx'
import ModelsView from '../../components/ModelsView.jsx'
import { ModelsCards, ModelsTiles } from './ModelsHome.jsx'
import GundamRange from './GundamRange.jsx'
import WarhammerRange from './WarhammerRange.jsx'

// Models: scale models, Gundam and Warhammer kits - the shelf of shame - and paint colours.
// Pages live at /models/<path>. The paints themselves are hobby supplies (core, /supplies).
export default {
  id: 'models',
  name: 'Models',
  // its colour (terracotta: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx scenes)
  hue: '#d0704f',
  banner: { scene: 'peaks', seed: 4, tagline: 'Build. Paint. Display.' },
  what: 'Scale models, Gundam and Warhammer',
  Icon: PlaneIcon,
  home: { Tiles: ModelsTiles, Cards: ModelsCards },
  actions: [{ label: 'Add kit', Icon: PlaneIcon, run: (app) => app.openModel(null) }],
  pages: [
    {
      path: 'kits', label: 'Kits', Icon: PlaneIcon,
      render: (app) => <ModelsView lookups={app.lookups} refreshKey={app.refreshKey} onOpen={app.openModel} />,
    },
    {
      path: 'warhammer', label: 'Warhammer', Icon: ShieldIcon,
      render: (app) => <WarhammerRange onOpenModel={app.openModel} />,
    },
    {
      path: 'gundam', label: 'Gundam', Icon: RobotIcon,
      render: (app) => <GundamRange onOpenModel={app.openModel} />,
    },
    {
      path: 'colours', label: 'Colours', Icon: DropsIcon,
      render: (app) => <ColoursView refreshKey={app.refreshKey} onChanged={app.changed} onOpenItem={app.openItem}
        onOpenModel={app.openModel} />,
    },
  ],
}
