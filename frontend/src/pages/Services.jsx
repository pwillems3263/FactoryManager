import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import api from '../api/client'
import './modules.css'
import { useDraggable } from '../hooks/useDraggable'

const EMPTY_FORM = {
  code_produit: '', nom: '', description: '',
  type_service: 'internal', type_cout: 'horaire',
  cout_horaire: '', cout_au_kg: '', cout_fixe: '', multi_taches: false,
}

export default function Services() {
  const [items, setItems]         = useState([])
  const [total, setTotal]         = useState(0)
  const [page, setPage]           = useState(1)
  const [pages, setPages]         = useState(1)
  const [search, setSearch]       = useState('')
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')
  const [selected, setSelected]   = useState(null)
  const [showForm, setShowForm]   = useState(false)
  const [formData, setFormData]   = useState(EMPTY_FORM)
  const [formMode, setFormMode]   = useState('create')
  const [saving, setSaving]       = useState(false)
  const [formError, setFormError] = useState('')
  const dragForm = useDraggable()

  const fetchItems = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/services', {
        params: { search: search || undefined, page, limit: 100 }
      })
      setItems(data.items)
      setTotal(data.total)
      setPages(data.pages)
      setError('')
    } catch {
      setError('Error loading services')
    } finally {
      setLoading(false)
    }
  }, [search, page])

  useEffect(() => { fetchItems() }, [fetchItems])

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
      code_produit: selected.code_produit  || '',
      nom:          selected.nom           || '',
      description:  selected.description   || '',
      type_service: selected.type_service  || 'internal',
      type_cout:    selected.type_cout     || 'horaire',
      cout_horaire: selected.cout_horaire  || '',
      cout_au_kg:   selected.cout_au_kg    || '',
      cout_fixe:    selected.cout_fixe     || '',
      multi_taches: selected.multi_taches  || false,
    })
    setFormMode('edit')
    setFormError('')
    setShowForm(true)
  }

  const handleDelete = async () => {
    if (!selected) return
    if (!window.confirm(`Delete "${selected.nom}"?`)) return
    try {
      await api.delete(`/services/${selected.id_service}`)
      setSelected(null)
      fetchItems()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error deleting service')
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setFormError('')
    const payload = {
      code_produit: formData.code_produit || null,
      nom:          formData.nom,
      description:  formData.description  || null,
      type_service: formData.type_service,
      type_cout:    formData.type_cout,
      // Only the cost field matching the chosen cost type is sent — the
      // others are cleared so stale values from a previous mode don't
      // linger and confuse the price calculation.
      cout_horaire: formData.type_cout === 'horaire' && formData.cout_horaire !== '' ? parseFloat(formData.cout_horaire) : null,
      cout_au_kg:   formData.type_cout === 'poids'   && formData.cout_au_kg   !== '' ? parseFloat(formData.cout_au_kg)   : null,
      cout_fixe:    formData.type_cout === 'fixe'    && formData.cout_fixe    !== '' ? parseFloat(formData.cout_fixe)    : null,
      multi_taches: formData.multi_taches,
    }
    try {
      if (formMode === 'create') {
        await api.post('/services', payload)
      } else {
        await api.put(`/services/${selected.id_service}`, payload)
      }
      setShowForm(false); dragForm.reset()
      setSelected(null)
      fetchItems()
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Error saving service')
    } finally {
      setSaving(false)
    }
  }

  const handleChange = (e) => {
    const val = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setFormData(prev => ({ ...prev, [e.target.name]: val }))
  }

  return (
    <Layout>
      <div className="module-header">
        <div>
          <h2>⚙️ Services</h2>
          <span className="module-count">{total} service{total > 1 ? 's' : ''}</span>
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
          placeholder="🔍 Search by name or code..."
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
              <th>Code</th>
              <th>Name</th>
              <th>Type</th>
              <th>Cost</th>
              <th>Multi-task</th>
              <th>Components</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="table-loading">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={6} className="table-empty">No services found</td></tr>
            ) : items.map((s) => (
              <tr
                key={s.id_service}
                className={selected?.id_service === s.id_service ? 'selected' : ''}
                onClick={() => setSelected(s)}
                onDoubleClick={openEdit}
              >
                <td>{s.code_produit || '—'}</td>
                <td className="td-nom">{s.nom}</td>
                <td>
                  <span className={`badge ${s.type_service === 'internal' ? 'badge-blue' : 'badge-orange'}`}>
                    {s.type_service}
                  </span>
                </td>
                <td className="td-prix">
                  {s.type_cout === 'horaire' && s.cout_horaire != null && `${parseFloat(s.cout_horaire).toFixed(2)} €/h`}
                  {s.type_cout === 'poids'   && s.cout_au_kg   != null && `${parseFloat(s.cout_au_kg).toFixed(4)} €/kg`}
                  {s.type_cout === 'fixe'    && s.cout_fixe    != null && `${parseFloat(s.cout_fixe).toFixed(2)} €`}
                  {!((s.type_cout === 'horaire' && s.cout_horaire != null) ||
                     (s.type_cout === 'poids'   && s.cout_au_kg   != null) ||
                     (s.type_cout === 'fixe'    && s.cout_fixe    != null)) && '—'}
                </td>
                <td className="td-center">{s.multi_taches ? '✅' : '—'}</td>
                <td className="td-center">
                  {s.nb_composants > 0
                    ? <span className="badge badge-blue">{s.nb_composants}</span>
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
            <div><label>Code</label><span>{selected.code_produit || '—'}</span></div>
            <div><label>Type</label><span>{selected.type_service}</span></div>
            <div><label>Cost Type</label><span>{{ horaire: 'Per hour', poids: 'Per kg', fixe: 'Fixed price' }[selected.type_cout] || '—'}</span></div>
            <div><label>Cost</label><span>
              {selected.type_cout === 'horaire' && selected.cout_horaire != null && `${parseFloat(selected.cout_horaire).toFixed(2)} €/h`}
              {selected.type_cout === 'poids'   && selected.cout_au_kg   != null && `${parseFloat(selected.cout_au_kg).toFixed(4)} €/kg`}
              {selected.type_cout === 'fixe'    && selected.cout_fixe    != null && `${parseFloat(selected.cout_fixe).toFixed(2)} €`}
            </span></div>
            <div><label>Multi-task</label><span>{selected.multi_taches ? 'Yes' : 'No'}</span></div>
            <div><label>Used in Components</label><span>{selected.nb_composants}</span></div>
            {selected.description && (
              <div className="detail-full"><label>Description</label><span>{selected.description}</span></div>
            )}
          </div>
        </div>
      )}

      {showForm && (
        <div className="modal-overlay" onClick={() => { setShowForm(false); dragForm.reset() }}>
          <div className="modal" style={{ transform: `translate(${dragForm.pos.x}px, ${dragForm.pos.y}px)` }} onClick={e => e.stopPropagation()}>
            <div className="modal-header" onMouseDown={dragForm.onMouseDown} style={{ cursor: 'grab', userSelect: 'none' }}>
              <h3>{formMode === 'create' ? '+ New Service' : '✏ Edit Service'}</h3>
              <button className="modal-close" onClick={() => { setShowForm(false); dragForm.reset() }}>✕</button>
            </div>
            <form onSubmit={handleSubmit} className="modal-form">
              {formError && <div className="alert alert-error">{formError}</div>}

              <div className="form-row">
                <div className="form-group">
                  <label>Code</label>
                  <input name="code_produit" value={formData.code_produit} onChange={handleChange} placeholder="e.g. SRV-001" />
                </div>
                <div className="form-group">
                  <label>Name *</label>
                  <input name="nom" value={formData.nom} onChange={handleChange} required placeholder="Service name" />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Type *</label>
                  <select name="type_service" value={formData.type_service} onChange={handleChange}>
                    <option value="internal">Internal</option>
                    <option value="external">External</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Cost Type *</label>
                  <select name="type_cout" value={formData.type_cout} onChange={handleChange}>
                    <option value="horaire">Per hour</option>
                    <option value="poids">Per kg</option>
                    <option value="fixe">Fixed price</option>
                  </select>
                </div>
              </div>

              <div className="form-row">
                {formData.type_cout === 'horaire' && (
                  <div className="form-group">
                    <label>Hourly Rate (€/h) *</label>
                    <input type="number" step="0.01" name="cout_horaire" value={formData.cout_horaire} onChange={handleChange} placeholder="0.00" />
                  </div>
                )}
                {formData.type_cout === 'poids' && (
                  <div className="form-group">
                    <label>Price per kg (€/kg) *</label>
                    <input type="number" step="0.0001" name="cout_au_kg" value={formData.cout_au_kg} onChange={handleChange} placeholder="0.0000" />
                  </div>
                )}
                {formData.type_cout === 'fixe' && (
                  <div className="form-group">
                    <label>Fixed Cost (€) *</label>
                    <input type="number" step="0.01" name="cout_fixe" value={formData.cout_fixe} onChange={handleChange} placeholder="0.00" />
                  </div>
                )}
                <div className="form-group" style={{ justifyContent: 'flex-end', flexDirection: 'row', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" name="multi_taches" id="multi_taches" checked={formData.multi_taches} onChange={handleChange} />
                  <label htmlFor="multi_taches" style={{ cursor: 'pointer' }}>Allow multi-task</label>
                </div>
              </div>

              {formData.type_cout === 'poids' && (
                <p style={{ color: '#7f8c8d', fontSize: 12, marginTop: -8 }}>
                  When this service is used in a component's routing, its cost is computed automatically
                  from the raw stock weight — no operation time needs to be entered for that step.
                </p>
              )}
              {formData.type_cout === 'fixe' && (
                <p style={{ color: '#7f8c8d', fontSize: 12, marginTop: -8 }}>
                  This service always costs the fixed amount per unit — no operation time needs to be
                  entered for that step.
                </p>
              )}

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
