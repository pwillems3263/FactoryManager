import { NavLink } from 'react-router-dom'
import './Sidebar.css'

const MENU = [
  { path: '/dashboard',    icon: '📊', label: 'Dashboard',        ready: true  },
  { path: '/composants',   icon: '📦', label: 'Components',       ready: true  },
  { path: '/matieres',     icon: '🧱', label: 'Raw Materials',    ready: false },
  { path: '/pieces-ext',   icon: '🔩', label: 'External Parts',   ready: false },
  { path: '/services',     icon: '⚙️', label: 'Services',         ready: false },
  { path: '/machines',     icon: '🏗️', label: 'Machines',         ready: false },
  { path: '/assemblages',  icon: '🔗', label: 'Assemblies',       ready: false },
  { path: '/commandes',    icon: '📋', label: 'Orders',           ready: false },
  { path: '/of',           icon: '🏭', label: 'Work Orders',      ready: false },
  { path: '/suivi',        icon: '📈', label: 'Production Track', ready: false },
  { path: '/pointage',     icon: '⏱️', label: 'Time Tracking',    ready: false },
  { path: '/planning',     icon: '📅', label: 'Planning',         ready: false },
  { path: '/utilisateurs', icon: '👥', label: 'Users',            ready: false },
]

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        {MENU.map((item) =>
          item.ready ? (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                'sidebar-item' + (isActive ? ' active' : '')
              }
            >
              <span className="sidebar-icon">{item.icon}</span>
              <span className="sidebar-label">{item.label}</span>
            </NavLink>
          ) : (
            <div key={item.path} className="sidebar-item disabled">
              <span className="sidebar-icon">{item.icon}</span>
              <span className="sidebar-label">{item.label}</span>
              <span className="sidebar-soon">soon</span>
            </div>
          )
        )}
      </nav>
    </aside>
  )
}
