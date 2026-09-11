import { useNavigate } from 'react-router-dom'
import Sidebar from './Sidebar'
import './Layout.css'

export default function Layout({ children }) {
  const navigate = useNavigate()
  const user = JSON.parse(localStorage.getItem('user') || '{}')

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/login')
  }

  return (
    <div className="layout">
      <header className="layout-header">
        <div className="header-left">
          <span className="header-logo">🏭</span>
          <h1>FactoryManager</h1>
        </div>
        <div className="header-right">
          <span className="header-user">👤 {user.full_name || user.username}</span>
          <button className="logout-btn" onClick={handleLogout}>Logout</button>
        </div>
      </header>
      <div className="layout-body">
        <Sidebar />
        <main className="layout-content">{children}</main>
      </div>
    </div>
  )
}
