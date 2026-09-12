import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Sidebar from './Sidebar'
import './Layout.css'

export default function Layout({ children }) {
  const navigate = useNavigate()
  const user     = JSON.parse(localStorage.getItem('user') || '{}')
  const [showSwitch, setShowSwitch] = useState(false)
  const [switching, setSwitching]   = useState(false)

  const dbKey   = user.db_key   || 'test'
  const dbLabel = user.db_label || 'TEST'
  const dbColor = user.db_color || 'orange'

  const isProd = dbKey === 'prod'

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/login')
  }

  const handleSwitch = async () => {
    const targetKey = isProd ? 'test' : 'prod'
    if (isProd) {
      // Already in prod, switch to test — safe, no confirmation needed
    } else {
      // About to switch to PRODUCTION — require confirmation
      const ok = window.confirm(
        '⚠️ You are about to switch to the PRODUCTION database.\n\n' +
        'All changes will affect real production data.\n\n' +
        'Are you sure?'
      )
      if (!ok) return
    }

    setSwitching(true)
    try {
      const token = localStorage.getItem('token')
      const res = await fetch('http://localhost:8000/auth/switch-db', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ db_key: targetKey }),
      })
      if (!res.ok) {
        const err = await res.json()
        alert(err.detail || 'Error switching database')
        return
      }
      const data = await res.json()
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('user', JSON.stringify({
        username:  data.username,
        full_name: data.full_name,
        niveau:    data.niveau,
        db_key:    data.db_key,
        db_label:  data.db_label,
        db_color:  data.db_color,
      }))
      // Reload to refresh all data from new DB
      window.location.reload()
    } catch {
      alert('Connection error while switching database')
    } finally {
      setSwitching(false)
    }
  }

  return (
    <div className="layout">
      <header className="layout-header">
        <div className="header-left">
          <span className="header-logo">🏭</span>
          <h1>FactoryManager</h1>
        </div>

        {/* DB Indicator — center */}
        <div className="db-indicator" style={{
          background: isProd ? 'rgba(231,76,60,0.15)' : 'rgba(230,126,34,0.15)',
          border: `2px solid ${isProd ? '#e74c3c' : '#e67e22'}`,
          borderRadius: 8,
          padding: '4px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <span style={{
            width: 10, height: 10, borderRadius: '50%',
            background: isProd ? '#e74c3c' : '#e67e22',
            boxShadow: isProd ? '0 0 6px #e74c3c' : '0 0 6px #e67e22',
            flexShrink: 0,
          }} />
          <span style={{
            color: isProd ? '#ff6b6b' : '#f0a500',
            fontWeight: 800,
            fontSize: 13,
            letterSpacing: 1,
          }}>
            {dbLabel}
          </span>
          <button
            onClick={handleSwitch}
            disabled={switching}
            style={{
              background: 'rgba(255,255,255,0.1)',
              border: '1px solid rgba(255,255,255,0.2)',
              borderRadius: 4,
              color: 'rgba(255,255,255,0.8)',
              cursor: 'pointer',
              fontSize: 11,
              padding: '2px 8px',
              transition: 'all 0.15s',
            }}
          >
            {switching ? '...' : isProd ? '→ Switch to TEST' : '→ Switch to PROD'}
          </button>
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
