import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import api from '../api/client'
import './modules.css'
import { useDraggable } from '../hooks/useDraggable'

const EMPTY_FORM = {
  code_produit: '', nom: '', description: '',
  fournisseur: '', prix_unitaire: '',
}

export default function PiecesExternes() {
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

  const fetchItems = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/external-parts', {
        params: { search: search || undefined, page, limit: 100 }
      })
      setItems(data.items)
      setTotal(data.total)
      setPages(data.pages)
      setError('')
    } catch {
      setError('Error loading external parts')
    } finally {
      setLoading(false)
    }
  }, [search, page])

  useEffect(() => { fetchItems() }, [fetchItems])

  useEffect(() => {
    if (!selected) { setPriceHistory([]); return }
    api.get(`/external-parts/${selected.id_piece_externe}/historique-prix`)
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
      code_produit:  selected.code_produit  || '',
      nom:           selected.nom           || '',
      description:   selected.description   || '',
      fournisseur:   selected.fournisseur   || '',
      prix_unitaire: selected.prix_unitaire || '',
    })
    setFormMode('edit')
    setFormError('')
    setShowForm(true)
  }

  const handleDelete = async () => {
    if (!selected) return
    if (!window.confirm(`Delete "${selected.nom}"?`)) return
    try {
      await api.delete(`/external-parts/${selected.id_piece_externe}`)
      setSelected(null)
      fetchItems()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error deleting external part')
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setFormError('')
    const payload = {
      code_produit:  formData.code_produit  || null,
      nom:           formData.nom,
      description:   formData.description   || null,
      fournisseur:   formData.fournisseur   || null,
      prix_unitaire: formData.prix_unitaire !== '' ? parseFloat(formData.prix_unitaire) : null,
    }
    try {
      if (formMode === 'create') {
        await api.post('/external-parts', payload)
      } else {
        await api.put(`/external-parts/${selected.id_piece_externe}`, payload)
      }
      setShowForm(false); dragForm.reset()
      setSelected(null)
      fetchItems()
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Error saving external part')
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
          <h2>🔩 External Parts</h2>
          <span className="module-count">{total} part{total > 1 ? 's' : ''}</span>
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
          placeholder="🔍 Search by name or product code..."
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
              <th>Product Code</th>
              <th>Name</th>
              <th>Supplier</th>
              <th>Unit Price (€)</th>
              <th>Components</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className="table-loading">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={5} className="table-empty">No external parts found</td></tr>
            ) : items.map((p) => (
              <tr
                key={p.id_piece_externe}
                className={selected?.id_piece_externe === p.id_piece_externe ? 'selected' : ''}
                onClick={() => setSelected(p)}
                onDoubleClick={openEdit}
              >
                <td>{p.code_produit || '—'}</td>
                <td className="td-nom">{p.nom}</td>
                <td>{p.fournisseur || '—'}</td>
                <td className="td-prix">
                  {p.prix_unitaire != null ? `${parseFloat(p.prix_unitaire).toFixed(2)} €` : '—'}
                </td>
                <td className="td-center">
                  {p.nb_composants > 0
                    ? <span className="badge badge-blue">{p.nb_composants}</span>
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
            <div><label>Product Code</label><span>{selected.code_produit || '—'}</span></div>
            <div><label>Supplier</label><span>{selected.fournisseur || '—'}</span></div>
            <div><label>Unit Price</label>
              <span>{selected.prix_unitaire != null ? `${parseFloat(selected.prix_unitaire).toFixed(2)} €` : '—'}</span>
            </div>
            <div>
              <label className="info-tooltip">
                Used in Components
                <span className="info-icon">i</span>
                <span className="tooltip-bubble">
                  Number of components whose bill of materials references this external part.
                  A part used by at least one component cannot be deleted.
                </span>
              </label>
              <span>{selected.nb_composants}</span>
            </div>
            {selected.description && (
              <div className="detail-full"><label>Description</label><span>{selected.description}</span></div>
            )}
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
                      <td>{h.ancien_prix != null ? `${h.ancien_prix.toFixed(2)} €` : '—'}</td>
                      <td>{h.nouveau_prix != null ? `${h.nouveau_prix.toFixed(2)} €` : '—'}</td>
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
              <h3>{formMode === 'create' ? '+ New External Part' : '✏ Edit External Part'}</h3>
              <button className="modal-close" onClick={() => { setShowForm(false); dragForm.reset() }}>✕</button>
            </div>
            <form onSubmit={handleSubmit} className="modal-form">
              {formError && <div className="alert alert-error">{formError}</div>}

              <div className="form-row">
                <div className="form-group">
                  <label>Product Code</label>
                  <input name="code_produit" value={formData.code_produit} onChange={handleChange} placeholder="e.g. EXT-001" />
                </div>
                <div className="form-group">
                  <label>Name *</label>
                  <input name="nom" value={formData.nom} onChange={handleChange} required placeholder="Part name" />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Supplier</label>
                  <input name="fournisseur" value={formData.fournisseur} onChange={handleChange} placeholder="Supplier name" />
                </div>
                <div className="form-group">
                  <label>Unit Price (€)</label>
                  <input type="number" step="0.01" name="prix_unitaire" value={formData.prix_unitaire} onChange={handleChange} placeholder="0.00" />
                </div>
              </div>

              <div className="form-group">
                <label>Description</label>
                <textarea name="description" value={formData.description} onChange={handleChange} rows={3} />
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
