import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import UsersPanel from '../components/UsersPanel'
import api from '../api/client'
import './modules.css'

const TABS = [
  { key: 'users',   label: '👥 Users' },
  { key: 'storage', label: '📁 Plans Storage' },
  { key: 'database', label: '🗄️ Database' },
]

// ─── Plans storage location panel ────────────────────────────────────────────

const EMPTY_STORAGE = { provider: 'onedrive', base_path: '', notes: '' }

const PROVIDER_OPTIONS = [
  { value: 'onedrive',   label: 'OneDrive' },
  { value: 'sharepoint', label: 'SharePoint' },
  { value: 'local',      label: 'Local / network folder' },
  { value: 'other',      label: 'Other' },
]

function PlansStoragePanel() {
  const [form, setForm]       = useState(EMPTY_STORAGE)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useState('')
  const [saved, setSaved]     = useState(false)

  const fetchConfig = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/settings/plans-storage')
      setForm({ provider: data.provider || 'onedrive', base_path: data.base_path || '', notes: data.notes || '' })
      setError('')
    } catch {
      setError('Error loading the current configuration')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchConfig() }, [fetchConfig])

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm(prev => ({ ...prev, [name]: value }))
    setSaved(false)
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true); setError(''); setSaved(false)
    try {
      await api.put('/settings/plans-storage', form)
      setSaved(true)
    } catch (err) {
      setError(err.response?.data?.detail || 'Error saving the configuration')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className="empty">Loading...</p>

  return (
    <div className="detail-card">
      <h3>📁 Drawings / Plans Storage Location</h3>
      <p style={{ color: '#7f8c8d', fontSize: 13, marginTop: -8, marginBottom: 16 }}>
        Defines where drawing files referenced by the "Drawing URL" fields (Components, Assemblies,
        Operations) actually live. This is informational — it doesn't change existing links, it just
        tells everyone on the team where to find and drop new files.
      </p>

      {error && <div className="alert alert-error">{error}</div>}
      {saved && <div className="alert" style={{ background: '#eafaf1', color: '#27ae60', border: '1px solid #27ae60' }}>Saved.</div>}

      <form onSubmit={handleSave} className="modal-form" style={{ padding: 0, maxWidth: 640 }}>
        <div className="form-row">
          <div className="form-group">
            <label>Provider</label>
            <select name="provider" value={form.provider} onChange={handleChange}>
              {PROVIDER_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Base path / URL</label>
            <input name="base_path" value={form.base_path} onChange={handleChange}
              placeholder="e.g. https://yourcompany-my.sharepoint.com/personal/.../Plans" />
          </div>
        </div>

        <div className="form-group">
          <label>Notes</label>
          <textarea name="notes" value={form.notes} onChange={handleChange}
            placeholder="e.g. Ask IT for access, sync the folder locally before opening large drawings..." />
        </div>

        <div className="modal-footer" style={{ borderTop: 'none', paddingTop: 0 }}>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </form>
    </div>
  )
}

// ─── Database maintenance panel (replicate PROD → TEST) ─────────────────────

function DatabasePanel() {
  const [confirmText, setConfirmText] = useState('')
  const [running, setRunning]         = useState(false)
  const [result, setResult]           = useState(null)
  const [error, setError]             = useState('')

  const CONFIRM_PHRASE = 'REPLICATE PROD TO DEV'
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  const isOnTest = (user.db_key || 'test') !== 'prod'

  const handleReplicate = async () => {
    if (confirmText.trim() !== CONFIRM_PHRASE) return
    if (!window.confirm(
      'This will PERMANENTLY ERASE all data currently in the TEST/DEV database ' +
      'and replace it with an exact copy of PRODUCTION.\n\nThis cannot be undone. Continue?'
    )) return

    setRunning(true); setError(''); setResult(null)
    try {
      const { data } = await api.post('/db-admin/replicate-prod-to-test', { confirm_phrase: confirmText.trim() })
      setResult(data)
      setConfirmText('')
    } catch (err) {
      setError(err.response?.data?.detail || 'Error replicating the database')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="detail-card">
      <h3>🗄️ Replicate PRODUCTION → TEST / DEV</h3>
      <p style={{ color: '#7f8c8d', fontSize: 13, marginTop: -8, marginBottom: 16 }}>
        Wipes the TEST database and replaces its content with a full copy of PRODUCTION data.
        Production is never modified — this only ever writes into TEST. Administrator only.
      </p>

      {!isOnTest && (
        <div className="alert alert-error">
          You are currently switched to PRODUCTION. Switch back to TEST (top bar) before running this.
        </div>
      )}

      {error && <div className="alert alert-error">{error}</div>}
      {result && (
        <div className="alert" style={{ background: '#eafaf1', color: '#27ae60', border: '1px solid #27ae60' }}>
          Done — {result.tables_copied} tables, {result.rows_copied} rows copied into TEST.
        </div>
      )}

      <div className="form-group" style={{ maxWidth: 480 }}>
        <label>Type "{CONFIRM_PHRASE}" to enable the button</label>
        <input value={confirmText} onChange={e => setConfirmText(e.target.value)}
          placeholder={CONFIRM_PHRASE} disabled={!isOnTest || running} />
      </div>

      <div className="modal-footer" style={{ borderTop: 'none', paddingTop: 8, justifyContent: 'flex-start' }}>
        <button className="btn btn-danger"
          disabled={!isOnTest || running || confirmText.trim() !== CONFIRM_PHRASE}
          onClick={handleReplicate}>
          {running ? 'Replicating...' : '⚠ Replicate PROD → TEST'}
        </button>
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DbConfig() {
  const [tab, setTab] = useState('users')

  return (
    <Layout>
      <div className="module-header">
        <div>
          <h2>🗄️ DB Configuration</h2>
        </div>
      </div>

      <div className="sidebar-group" style={{ display: 'flex', flexDirection: 'row', gap: 8, marginBottom: 16 }}>
        {TABS.map(t => (
          <button key={t.key}
            className={`btn ${tab === t.key ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'users' && <UsersPanel />}
      {tab === 'storage' && <PlansStoragePanel />}
      {tab === 'database' && <DatabasePanel />}
    </Layout>
  )
}
