import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import api from '../api/client'
import './Composants.css'

const TYPE_OPTIONS = ['machining', 'welding', 'assembly', 'other']

const EMPTY_FORM = {
  reference: '', nom: '', type: '', description: '', plan_url: '',
  id_matiere_brut: '', forme_brut: '',
  brut_diametre: '', brut_diam_ext: '', brut_diam_int: '',
  brut_longueur: '', brut_largeur: '', brut_hauteur: '', brut_epaisseur: '',
}

export default function Composants() {
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

  const fetchComposants = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/composants', {
        params: { search: search || undefined, page, limit: 50 }
      })
      setItems(data.items)
      setTotal(data.total)
      setPages(data.pages)
      setError('')
    } catch {
      setError('Error loading components')
    } finally {
      setLoading(false)
    }
  }, [search, page])

  useEffect(() => { fetchComposants() }, [fetchComposants])

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
      reference:      selected.reference      || '',
      nom:            selected.nom            || '',
      type:           selected.type           || '',
      description:    selected.description    || '',
      plan_url:       selected.plan_url       || '',
      id_matiere_brut: selected.id_matiere_brut || '',
      forme_brut:     selected.forme_brut     || '',
      brut_diametre:  selected.brut_diametre  || '',
      brut_diam_ext:  selected.brut_diam_ext  || '',
      brut_diam_int:  selected.brut_diam_int  || '',
      brut_longueur:  selected.brut_longueur  || '',
      brut_largeur:   selected.brut_largeur   || '',
      brut_hauteur:   selected.brut_hauteur   || '',
      brut_epaisseur: selected.brut_epaisseur || '',
    })
    setFormMode('edit')
    setFormError('')
    setShowForm(true)
  }

  const handleDelete = async () => {
    if (!selected) return
    if (!window.confirm(`Delete "${selected.nom}"?`)) return
    try {
      await api.delete(`/composants/${selected.id_composant}`)
      setSelected(null)
      fetchComposants()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error deleting component')
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setFormError('')
    const payload = { ...formData }
    const numFields = ['id_matiere_brut','brut_diametre','brut_diam_ext','brut_diam_int',
                       'brut_longueur','brut_largeur','brut_hauteur','brut_epaisseur']
    numFields.forEach(f => {
      payload[f] = (payload[f] === '' || payload[f] === null) ? null : parseFloat(payload[f])
    })
    Object.keys(payload).forEach(k => { if (payload[k] === '') payload[k] = null })
    try {
      if (formMode === 'create') {
        await api.post('/composants', payload)
      } else {
        await api.put(`/composants/${selected.id_composant}`, payload)
      }
      setShowForm(false)
      setSelected(null)
      fetchComposants()
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Error saving component')
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
          <h2>📦 Components</h2>
          <span className="module-count">{total} component{total > 1 ? 's' : ''}</span>
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
          placeholder="🔍 Search by name or reference..."
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
              <th>Reference</th>
              <th>Name</th>
              <th>Type</th>
              <th>Material</th>
              <th>Cost Price</th>
              <th>Routings</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="table-loading">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={6} className="table-empty">No components found</td></tr>
            ) : items.map((c) => (
              <tr
                key={c.id_composant}
                className={selected?.id_composant === c.id_composant ? 'selected' : ''}
                onClick={() => setSelected(c)}
                onDoubleClick={openEdit}
              >
                <td>{c.reference || '—'}</td>
                <td className="td-nom">{c.nom}</td>
                <td>{c.type || '—'}</td>
                <td>{c.matiere_nom || '—'}</td>
                <td className="td-prix">
                  {c.prix_revient != null ? `${parseFloat(c.prix_revient).toFixed(2)} €` : '—'}
                </td>
                <td className="td-center">
                  {c.nb_gammes > 0
                    ? <span className="badge badge-blue">{c.nb_gammes}</span>
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
            <div><label>Reference</label><span>{selected.reference || '—'}</span></div>
            <div><label>Type</label><span>{selected.type || '—'}</span></div>
            <div><label>Raw Material</label><span>{selected.matiere_nom || '—'}</span></div>
            <div><label>Raw Shape</label><span>{selected.forme_brut || '—'}</span></div>
            <div><label>Cost Price</label>
              <span>{selected.prix_revient != null ? `${parseFloat(selected.prix_revient).toFixed(2)} €` : '—'}</span>
            </div>
            <div><label>Routings</label><span>{selected.nb_gammes}</span></div>
            {selected.description && (
              <div className="detail-full"><label>Description</label><span>{selected.description}</span></div>
            )}
            {selected.plan_url && (
              <div className="detail-full">
                <label>Drawing</label>
                <a href={selected.plan_url} target="_blank" rel="noreferrer">🔗 Open drawing</a>
              </div>
            )}
          </div>
        </div>
      )}

      {showForm && (
        <div className="modal-overlay" onClick={() => setShowForm(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{formMode === 'create' ? '+ New Component' : '✏ Edit Component'}</h3>
              <button className="modal-close" onClick={() => setShowForm(false)}>✕</button>
            </div>

            <form onSubmit={handleSubmit} className="modal-form">
              {formError && <div className="alert alert-error">{formError}</div>}

              <div className="form-row">
                <div className="form-group">
                  <label>Reference</label>
                  <input name="reference" value={formData.reference} onChange={handleChange} placeholder="e.g. COMP-001" />
                </div>
                <div className="form-group">
                  <label>Name *</label>
                  <input name="nom" value={formData.nom} onChange={handleChange} required placeholder="Component name" />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Type</label>
                  <select name="type" value={formData.type} onChange={handleChange}>
                    <option value="">— Select —</option>
                    {TYPE_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Raw Shape</label>
                  <select name="forme_brut" value={formData.forme_brut} onChange={handleChange}>
                    <option value="">— None —</option>
                    <option value="axe">Shaft</option>
                    <option value="tube">Tube</option>
                    <option value="plaque">Plate</option>
                  </select>
                </div>
              </div>

              {formData.forme_brut === 'axe' && (
                <div className="form-row">
                  <div className="form-group">
                    <label>Diameter (mm)</label>
                    <input type="number" step="0.001" name="brut_diametre" value={formData.brut_diametre} onChange={handleChange} />
                  </div>
                  <div className="form-group">
                    <label>Length (mm)</label>
                    <input type="number" step="0.001" name="brut_longueur" value={formData.brut_longueur} onChange={handleChange} />
                  </div>
                </div>
              )}
              {formData.forme_brut === 'tube' && (
                <div className="form-row">
                  <div className="form-group">
                    <label>Outer Diam. (mm)</label>
                    <input type="number" step="0.001" name="brut_diam_ext" value={formData.brut_diam_ext} onChange={handleChange} />
                  </div>
                  <div className="form-group">
                    <label>Inner Diam. (mm)</label>
                    <input type="number" step="0.001" name="brut_diam_int" value={formData.brut_diam_int} onChange={handleChange} />
                  </div>
                  <div className="form-group">
                    <label>Length (mm)</label>
                    <input type="number" step="0.001" name="brut_longueur" value={formData.brut_longueur} onChange={handleChange} />
                  </div>
                </div>
              )}
              {formData.forme_brut === 'plaque' && (
                <div className="form-row">
                  <div className="form-group">
                    <label>Width (mm)</label>
                    <input type="number" step="0.001" name="brut_largeur" value={formData.brut_largeur} onChange={handleChange} />
                  </div>
                  <div className="form-group">
                    <label>Height (mm)</label>
                    <input type="number" step="0.001" name="brut_hauteur" value={formData.brut_hauteur} onChange={handleChange} />
                  </div>
                  <div className="form-group">
                    <label>Thickness (mm)</label>
                    <input type="number" step="0.001" name="brut_epaisseur" value={formData.brut_epaisseur} onChange={handleChange} />
                  </div>
                </div>
              )}

              <div className="form-group">
                <label>Description</label>
                <textarea name="description" value={formData.description} onChange={handleChange} rows={3} />
              </div>

              <div className="form-group">
                <label>Drawing URL</label>
                <input name="plan_url" value={formData.plan_url} onChange={handleChange} placeholder="https://..." />
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
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
