import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import api from '../api/client'
import './modules.css'
import { useDraggable } from '../hooks/useDraggable'

const EMPTY_FORM = {
  nom: '', unite: '', stock_actuel: '0',
  poids_volumique: '', prix_au_kg: '',
}

export default function Matieres() {
  const [items, setItems]         = useState([])
  const [total, setTotal]         = useState(0)
  const [page, setPage]           = useState(1)
  const [pages, setPages]         = useState(1)
  const [search, setSearch]       = useState('')
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')
  const [selected, setSelected]   = useState(null)
  const [priceHistory, setPriceHistory] = useState([])
  const [showForm, setShowForm]   = useState(false)
  const [formData, setFormData]   = useState(EMPTY_FORM)
  const [formMode, setFormMode]   = useState('create')
  const [saving, setSaving]       = useState(false)
  const [formError, setFormError] = useState('')
  const dragForm = useDraggable()

  const fetchMatieres = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/matieres', {
        params: { search: search || undefined, page, limit: 100 }
      })
      setItems(data.items)
      setTotal(data.total)
      setPages(data.pages)
      setError('')
    } catch {
      setError('Error loading raw materials')
    } finally {
      setLoading(false)
    }
  }, [search, page])

  useEffect(() => { fetchMatieres() }, [fetchMatieres])

  useEffect(() => {
    if (!selected) { setPriceHistory([]); return }
    api.get(`/matieres/${selected.id_matiere}/historique-prix`)
      .then(({ data }) => setPriceHistory(data))
      .catch(() => setPriceHistory([]))
  }, [selected])

  const handleSearch = (e) => { setSearch(e.target.value); setPage(1) }

  const openCreate = () => {
    setFormData(EMPTY_FORM)
    setFormMode('create')
    setFormError('')
    setShowForm(true)
  }

  const openEdit = () => {
    if (!selected) return
    setFormData({
      nom:             selected.nom             || '',
      unite:           selected.unite           || '',
      stock_actuel:    selected.stock_actuel    ?? '0',
      poids_volumique: selected.poids_volumique || '',
      prix_au_kg:      selected.prix_au_kg      || '',
    })
    setFormMode('edit')
    setFormError('')
    setShowForm(true)
  }

  const handleDelete = async () => {
    if (!selected) return
    if (!window.confirm(`Delete "${selected.nom}"?`)) return
    try {
      await api.delete(`/matieres/${selected.id_matiere}`)
      setSelected(null)
      fetchMatieres()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error deleting raw material')
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setFormError('')
    const payload = {
      nom:             formData.nom,
      unite:           formData.unite,
      stock_actuel:    parseFloat(formData.stock_actuel) || 0,
      poids_volumique: formData.poids_volumique !== '' ? parseFloat(formData.poids_volumique) : null,
      prix_au_kg:      formData.prix_au_kg      !== '' ? parseFloat(formData.prix_au_kg)      : null,
    }
    try {
      if (formMode === 'create') {
        await api.post('/matieres', payload)
      } else {
        await api.put(`/matieres/${selected.id_matiere}`, payload)
      }
      setShowForm(false); dragForm.reset()
      setSelected(null)
      fetchMatieres()
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Error saving raw material')
    } finally {
      setSaving(false)
    }
  }

  const handleChange = (e) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }))
  }

  return (
    <Layout>
      <div className="module-header">
        <div>
          <h2>🧱 Raw Materials</h2>
          <span className="module-count">{total} material{total > 1 ? 's' : ''}</span>
        </div>
        <div className="module-actions">
          <button className="btn btn-primary" onClick={openCreate}>+ New</button>
          <button className="btn btn-secondary" onClick={openEdit} disabled={!selected}>✏ Edit</button>
          <button className="btn btn-danger" onClick={handleDelete} disabled={!selected}>🗑 Delete</button>
        </div>
      </div>

      <div className="search-bar">
        <input
          type="text"
          placeholder="🔍 Search by name..."
          value={search}
          onChange={handleSearch}
          className="search-input"
        />
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Unit</th>
              <th>Current Stock</th>
              <th>Density (kg/cm³)</th>
              <th>Price (€/kg)</th>
              <th>Components</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="table-loading">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={6} className="table-empty">No raw materials found</td></tr>
            ) : items.map((m) => (
              <tr
                key={m.id_matiere}
                className={selected?.id_matiere === m.id_matiere ? 'selected' : ''}
                onClick={() => setSelected(m)}
                onDoubleClick={openEdit}
              >
                <td className="td-nom">{m.nom}</td>
                <td>{m.unite}</td>
                <td className="td-prix">{parseFloat(m.stock_actuel).toFixed(3)}</td>
                <td className="td-prix">{m.poids_volumique != null ? parseFloat(m.poids_volumique).toFixed(6) : '—'}</td>
                <td className="td-prix">{m.prix_au_kg != null ? `${parseFloat(m.prix_au_kg).toFixed(4)} €` : '—'}</td>
                <td className="td-center">
                  {m.nb_composants > 0
                    ? <span className="badge badge-blue">{m.nb_composants}</span>
                    : <span className="badge badge-gray">0</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pages > 1 && (
        <div className="pagination">
          <button onClick={() => setPage(p => Math.max(1, p-1))} disabled={page === 1}>◀</button>
          <span>Page {page} / {pages}</span>
          <button onClick={() => setPage(p => Math.min(pages, p+1))} disabled={page === pages}>▶</button>
        </div>
      )}

      {selected && (
        <div className="detail-card">
          <h3>Details — {selected.nom}</h3>
          <div className="detail-grid">
            <div><label>Unit</label><span>{selected.unite}</span></div>
            <div><label>Current Stock</label><span>{parseFloat(selected.stock_actuel).toFixed(3)} {selected.unite}</span></div>
            <div><label>Density (kg/cm³)</label>
              <span>{selected.poids_volumique != null ? parseFloat(selected.poids_volumique).toFixed(6) : '—'}</span>
            </div>
            <div><label>Price (€/kg)</label>
              <span>{selected.prix_au_kg != null ? `${parseFloat(selected.prix_au_kg).toFixed(4)} €` : '—'}</span>
            </div>
            <div>
              <label className="info-tooltip">
                Used in Components
                <span className="info-icon">i</span>
                <span className="tooltip-bubble">
                  Number of components whose bill of materials references this raw material.
                  A material used by at least one component cannot be deleted.
                </span>
              </label>
              <span>{selected.nb_composants}</span>
            </div>
          </div>

          {priceHistory.length > 0 && (
            <div className="price-history">
              <h4>Price History</h4>
              <table className="data-table">
                <thead>
                  <tr><th>Date</th><th>Old Price</th><th>New Price</th></tr>
                </thead>
                <tbody>
                  {priceHistory.map((h, i) => (
                    <tr key={i}>
                      <td>{new Date(h.date_modification).toLocaleString()}</td>
                      <td>{h.ancien_prix != null ? `${h.ancien_prix.toFixed(4)} €` : '—'}</td>
                      <td>{h.nouveau_prix != null ? `${h.nouveau_prix.toFixed(4)} €` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {showForm && (
        <div className="modal-overlay" onClick={() => { setShowForm(false); dragForm.reset() }}>
          <div className="modal" style={{ transform: `translate(${dragForm.pos.x}px, ${dragForm.pos.y}px)` }} onClick={e => e.stopPropagation()}>
            <div className="modal-header" onMouseDown={dragForm.onMouseDown} style={{ cursor: 'grab', userSelect: 'none' }}>
              <h3>{formMode === 'create' ? '+ New Raw Material' : '✏ Edit Raw Material'}</h3>
              <button className="modal-close" onClick={() => { setShowForm(false); dragForm.reset() }}>✕</button>
            </div>

            <form onSubmit={handleSubmit} className="modal-form">
              {formError && <div className="alert alert-error">{formError}</div>}

              <div className="form-row">
                <div className="form-group">
                  <label>Name *</label>
                  <input name="nom" value={formData.nom} onChange={handleChange} required placeholder="e.g. Steel 1.4112" />
                </div>
                <div className="form-group">
                  <label>Unit *</label>
                  <input name="unite" value={formData.unite} onChange={handleChange} required placeholder="e.g. kg, m, pcs" />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Current Stock</label>
                  <input type="number" step="0.001" name="stock_actuel" value={formData.stock_actuel} onChange={handleChange} />
                </div>
                <div className="form-group">
                  <label>Density (kg/cm³)</label>
                  <input type="number" step="0.000001" name="poids_volumique" value={formData.poids_volumique} onChange={handleChange} placeholder="e.g. 0.00785" />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Price (€/kg)</label>
                  <input type="number" step="0.0001" name="prix_au_kg" value={formData.prix_au_kg} onChange={handleChange} placeholder="e.g. 2.5000" />
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
    </Layout>
  )
}
