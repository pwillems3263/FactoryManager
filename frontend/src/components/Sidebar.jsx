import { NavLink } from 'react-router-dom'
import './Sidebar.css'

// Top-level item, shown above all groups (home page)
const TOP_ITEM = { path: '/dashboard', icon: '📊', label: 'Dashboard', ready: true }

// Grouped navigation
const GROUPS = [
  {
    label: 'Planning & Reporting',
    items: [
      { path: '/planning',  icon: '📅', label: 'Planning',            ready: true  },
      { path: '/suivi',     icon: '📈', label: 'Production Tracking', ready: true  },
      { path: '/pointage',  icon: '⏱️', label: 'Time Tracking',       ready: true  },
      { path: '/rebuts',    icon: '🗑️', label: 'Scrap',               ready: false },
    ],
  },
  {
    label: 'Orders',
    items: [
      { path: '/commandes', icon: '📋', label: 'Orders',          ready: true },
      { path: '/of',        icon: '🏭', label: 'Assembly Orders', ready: true },
    ],
  },
  {
    label: 'Configuration',
    items: [
      { path: '/assemblages',  icon: '🔗', label: 'Assemblies',     ready: true },
      { path: '/composants',   icon: '📦', label: 'Components',    ready: true },
      { path: '/services',     icon: '⚙️', label: 'Services',       ready: true },
      { path: '/pieces-ext',   icon: '🔩', label: 'External Parts', ready: true },
      { path: '/matieres',     icon: '🧱', label: 'Material',       ready: true },
      { path: '/machines',     icon: '🏗️', label: 'Machines',       ready: true },
      { path: '/db-config',    icon: '🗄️', label: 'DB Configuration', ready: true },
    ],
  },
]

function SidebarLink({ item }) {
  return item.ready ? (
    <NavLink
      to={item.path}
      className={({ isActive }) =>
        'sidebar-item' + (isActive ? ' active' : '')
      }
    >
      <span className="sidebar-icon">{item.icon}</span>
      <span className="sidebar-label">{item.label}</span>
    </NavLink>
  ) : (
    <div className="sidebar-item disabled">
      <span className="sidebar-icon">{item.icon}</span>
      <span className="sidebar-label">{item.label}</span>
      <span className="sidebar-soon">soon</span>
    </div>
  )
}

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        <SidebarLink item={TOP_ITEM} />

        {GROUPS.map((group) => (
          <div className="sidebar-group" key={group.label}>
            <div className="sidebar-group-label">{group.label}</div>
            {group.items.map((item) => (
              <SidebarLink key={item.path} item={item} />
            ))}
          </div>
        ))}
      </nav>
    </aside>
  )
}











