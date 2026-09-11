import { NavLink } from 'react-router-dom'
import './Sidebar.css'

const MENU = [
  { path: '/dashboard',    icon: '📊', label: 'Dashboard',       ready: true  },
  { path: '/composants',   icon: '📦', label: 'Composants',      ready: false },
  { path: '/matieres',     icon: '🧱', label: 'Matières',        ready: false },
  { path: '/pieces-ext',   icon: '🔩', label: 'Pièces externes', ready: false },
  { path: '/services',     icon: '⚙️', label: 'Services',        ready: false },
  { path: '/machines',     icon: '🏗️', label: 'Machines',        ready: false },
  { path: '/assemblages',  icon: '🔗', label: 'Assemblages',     ready: false },
  { path: '/commandes',    icon: '📋', label: 'Commandes',       ready: false },
  { path: '/of',           icon: '🏭', label: 'Ordres de fab.',  ready: false },
  { path: '/suivi',        icon: '📈', label: 'Suivi production', ready: false },
  { path: '/pointage',     icon: '⏱️', label: 'Pointage',        ready: false },
  { path: '/planning',     icon: '📅', label: 'Planning',        ready: false },
  { path: '/utilisateurs', icon: '👥', label: 'Utilisateurs',    ready: false },
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
              <span className="sidebar-soon">bientôt</span>
            </div>
          )
        )}
      </nav>
    </aside>
  )
}
