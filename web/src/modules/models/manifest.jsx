import ColoursView from '../../components/ColoursView.jsx'
import { BoxIcon, CartIcon, DropsIcon, PlaneIcon } from '../../components/icons.jsx'
import InventoryView from '../../components/InventoryView.jsx'
import ModelsView from '../../components/ModelsView.jsx'
import WishlistView from '../../components/WishlistView.jsx'
import { ModelsCards, ModelsStats } from './ModelsHome.jsx'

// Shelf of Shame: model kits and their supplies (the original app). Pages live at /models/<path>.
export default {
  id: 'models',
  name: 'Shelf of Shame',
  what: 'Model kits',
  short: 'Shelf',          // its tab on phones
  Icon: PlaneIcon,
  home: { Stats: ModelsStats, Cards: ModelsCards },   // its parts of the Home page
  pages: [
    {
      path: 'inventory', label: 'Inventory', Icon: BoxIcon,
      render: (app) => <InventoryView lookups={app.lookups} refreshKey={app.refreshKey} onAdjusted={app.adjusted}
        onOpen={app.openItem} onAdd={app.openAdd} />,
    },
    {
      path: 'wishlist', label: 'Wishlist', Icon: CartIcon,
      render: (app) => <WishlistView lookups={app.lookups} settings={app.settings} refreshKey={app.refreshKey}
        onChanged={app.changed} />,
    },
    {
      path: 'kits', label: 'Models', Icon: PlaneIcon,
      render: (app) => <ModelsView lookups={app.lookups} refreshKey={app.refreshKey} onOpen={app.openModel} />,
    },
    {
      path: 'colours', label: 'Colours', Icon: DropsIcon,
      render: (app) => <ColoursView refreshKey={app.refreshKey} onChanged={app.changed} onOpenItem={app.openItem}
        onOpenModel={app.openModel} />,
    },
  ],
}
