import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import api from '../api/client'
import './modules.css'
import { useDraggable } from '../hooks/useDraggable'

const NIVEAU_LABELS = { 1: 'Operator', 2: 'Coordinator', 3: 'Manager', 4: 'Administrator' }
const NIVEAU_COLORS = { 1: '#27ae60', 2: '#3498db', 3: '#e67e22', 4: '#e74c3c' }

const EMPTY_FORM = { username: '', full_name: '', password: '', niveau: 1, actif: true }

export default function Users() {
  const [items, setItems]         = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')
  const [selected, setSelected]   = useState(null)
  const [showForm, setShowForm]   = useState(false)
  const [formData, setFormData]   = useState(EMPTY_FORM)
  const [formMode, setFormMode]   = useState('create')
  const [saving, setSaving]       = useState(false)
  const [formError, setFormError] = useState('')
  const [showPwd, setShowPwd]     = useState(false)
  const [newPwd, setNewPwd]       = useState('')
  const dragForm = useDraggable()
  const dragPwd = useDraggable()

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/users')
      setItems(data); setError('')
    } catch { setError('Error loading users') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchUsers() }, [fetchUsers])

  const openCreate = () => {
    setFormData(EMPTY_FORM); setFormMode('create'); setFormError(''); setShowForm(true)
  }

  const openEdit = () => {
    if (!selected) return
    setFormData({
      username:  selected.username  || '',
      full_name: selected.full_name || '',
      password:  '',
      niveau:    selected.niveau    || 1,
      actif:     selected.actif,
    })
    setFormMode('edit'); setFormError(''); setShowForm(true)
  }

  const handleDelete = async () => {
    if (!selected) return
    if (!window.confirm(`Delete user "${selected.username}"?`)) return
    try {
      await api.delete(`/users/${selected.id_user}`)
      setSelected(null); fetchUsers()
    } catch (err) { alert(err.response?.data?.detail || 'Error deleting user') }
  }

  const handleToggleActive = async () => {
    if (!selected) return
    try {
      await api.put(`/users/${selected.id_user}`, { actif: !selected.actif })
      fetchUsers()
    } catch (err) { alert(err.response?.data?.detail || 'Error updating user') }
  }

  const handleSubmit = async (e) => {
    e.preventDefault(); setSaving(true); setFormError('')
    try {
      if (formMode === 'create') {
        await api.post('/users', {
          username:  formData.username,
          full_name: formData.full_name || null,
          password:  formData.password,
          niveau:    parseInt(formData.niveau),
          actif:     formData.actif,
        })
      } else {
        await api.put(`/users/${selected.id_user}`, {
          full_name: formData.full_name || null,
          niveau:    parseInt(formData.niveau),
          actif:     formData.actif,
        })
      }
      setShowForm(false); dragForm.reset(); setSelected(null); fetchUsers()
    } catch (err) { setFormError(err.response?.data?.detail || 'Error saving user') }
    finally { setSaving(false) }
  }

  const handlePasswordChange = async () => {
    if (!newPwd) return
    try {
      await api.put(`/users/${selected.id_user}/password`, { new_password: newPwd })
      setShowPwd(false); dragPwd.reset(); setNewPwd('')
      alert('Password updated successfully')
    } catch (err) { alert(err.response?.data?.detail || 'Error changing password') }
  }

  const handleChange = (e) => {
    const val = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setFormData(prev => ({ ...prev, [e.target.name]: val }))
  }

  return (
    <Layout>
      <div className="module-header">
        <div>
          <h2>👥 Users</h2>
          <span className="module-count">{items.length} user{items.length > 1 ? 's' : ''}</span>
        </div>
        <div className="module-actions">
          <button className="btn btn-primary" onClick={openCreate}>+ New User</button>
          <button className="btn btn-secondary" onClick={openEdit} disabled={!selected}>✏ Edit</button>
          <button className="btn btn-primary" style={{ background: '#16a085' }}
            onClick={() => { setNewPwd(''); setShowPwd(true) }} disabled={!selected}>
            🔑 Change Password
          </button>
          <button className="btn btn-danger" onClick={handleDelete} disabled={!selected}>🗑 Delete</button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Username</th><th>Full Name</th><th>Level</th><th>PIN</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className="table-loading">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={5} className="table-empty">No users found</td></tr>
            ) : items.map((u) => (
              <tr key={u.id_user}
                className={selected?.id_user === u.id_user ? 'selected' : ''}
                onClick={() => setSelected(u)} onDoubleClick={openEdit}>
                <td style={{ fontWeight: 700 }}>{u.username}</td>
                <td>{u.full_name || '—'}</td>
                <td>
                  <span className="badge" style={{ background: NIVEAU_COLORS[u.niveau] || '#95a5a6', color: 'white' }}>
                    {NIVEAU_LABELS[u.niveau] || u.niveau_label}
                  </span>
                </td>
                <td className="td-center">{u.has_pin ? '✅' : '—'}</td>
                <td>
                  <span className={`badge ${u.actif ? 'badge-green' : 'badge-red'}`}
                    style={{ cursor: 'pointer' }}
                    onClick={(e) => { e.stopPropagation(); setSelected(u); handleToggleActive() }}>
                    {u.actif ? 'Active' : 'Inactive'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="detail-card">
          <h3>Details — {selected.username}</h3>
          <div className="detail-grid">
            <div><label>Username</label><span>{selected.username}</span></div>
            <div><label>Full Name</label><span>{selected.full_name || '—'}</span></div>
            <div><label>Level</label>
              <span style={{ color: NIVEAU_COLORS[selected.niveau], fontWeight: 700 }}>
                {NIVEAU_LABELS[selected.niveau]}
              </span>
            </div>
            <div><label>PIN Set</label><span>{selected.has_pin ? 'Yes' : 'No'}</span></div>
            <div><label>Status</label>
              <span style={{ color: selected.actif ? '#27ae60' : '#e74c3c', fontWeight: 700 }}>
                {selected.actif ? 'Active' : 'Inactive'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* User Form Modal */}
      {showForm && (
        <div className="modal-overlay" onClick={() => { setShowForm(false); dragForm.reset() }}>
          <div className="modal" style={{ transform: `translate(${dragForm.pos.x}px, ${dragForm.pos.y}px)` }} onClick={e => e.stopPropagation()}>
            <div className="modal-header" onMouseDown={dragForm.onMouseDown} style={{ cursor: 'grab', userSelect: 'none' }}>
              <h3>{formMode === 'create' ? '+ New User' : '✏ Edit User'}</h3>
              <button className="modal-close" onClick={() => { setShowForm(false); dragForm.reset() }}>✕</button>
            </div>
            <form onSubmit={handleSubmit} className="modal-form">
              {formError && <div className="alert alert-error">{formError}</div>}

              <div className="form-row">
                <div className="form-group">
                  <label>Username *</label>
                  <input name="username" value={formData.username} onChange={handleChange}
                    required disabled={formMode === 'edit'} placeholder="username" />
                </div>
                <div className="form-group">
                  <label>Full Name</label>
                  <input name="full_name" value={formData.full_name} onChange={handleChange}
                    placeholder="First Last" />
                </div>
              </div>

              {formMode === 'create' && (
                <div className="form-group">
                  <label>Password *</label>
                  <input type="password" name="password" value={formData.password}
                    onChange={handleChange} required placeholder="Initial password" />
                </div>
              )}

              <div className="form-row">
                <div className="form-group">
                  <label>Level *</label>
                  <select name="niveau" value={formData.niveau} onChange={handleChange}>
                    <option value={1}>1 — Operator</option>
                    <option value={2}>2 — Coordinator</option>
                    <option value={3}>3 — Manager</option>
                    <option value={4}>4 — Administrator</option>
                  </select>
                </div>
                <div className="form-group" style={{ justifyContent: 'flex-end', flexDirection: 'row', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" name="actif" id="actif" checked={formData.actif} onChange={handleChange} />
                  <label htmlFor="actif" style={{ cursor: 'pointer' }}>Active account</label>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => { setShowForm(false); dragForm.reset() }}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Change Password Modal */}
      {showPwd && selected && (
        <div className="modal-overlay" onClick={() => { setShowPwd(false); dragPwd.reset() }}>
          <div className="modal" style={{ transform: `translate(${dragPwd.pos.x}px, ${dragPwd.pos.y}px)` }} onClick={e => e.stopPropagation()}>
            <div className="modal-header" onMouseDown={dragPwd.onMouseDown} style={{ cursor: 'grab', userSelect: 'none' }}>
              <h3>🔑 Change Password — {selected.username}</h3>
              <button className="modal-close" onClick={() => { setShowPwd(false); dragPwd.reset() }}>✕</button>
            </div>
            <div className="modal-form">
              <div className="form-group">
                <label>New Password *</label>
                <input type="password" value={newPwd} onChange={e => setNewPwd(e.target.value)}
                  placeholder="New password" autoFocus />
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => { setShowPwd(false); dragPwd.reset() }}>Cancel</button>
                <button className="btn btn-primary" onClick={handlePasswordChange} disabled={!newPwd}>
                  Change Password
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
