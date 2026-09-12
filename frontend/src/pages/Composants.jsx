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
  const [matieres, setMatieres]   = useState([])

  // ── Manufacturing Routing (Gamme) ──────────────────────────────────────
  const [gamme, setGamme]           = useState(null)
  const [loadingGamme, setLoadingGamme] = useState(false)
  const [machinesList, setMachinesList] = useState([])
  const [servicesList, setServicesList] = useState([])
  const [extPartsList, setExtPartsList] = useState([])
  const [showOpForm, setShowOpForm]     = useState(false)
  const [opFormMode, setOpFormMode]     = useState('create')
  const [opFormError, setOpFormError]   = useState('')
  const [opSaving, setOpSaving]         = useState(false)
  const EMPTY_OP = {
    id_operation: null, step_type: 'machine',
    description: '', tps_preparation: 0, tps_execution: 0, plan_url: '',
    id_machine: '', id_service: '', id_piece_externe: '',
  }
  const [opFormData, setOpFormData] = useState(EMPTY_OP)

  const fetchGamme = useCallback(async (id_composant) => {
    if (!id_composant) { setGamme(null); return }
    setLoadingGamme(true)
    try {
      const { data } = await api.get(`/composants/${id_composant}/gamme`)
      setGamme(data)
    } catch { setGamme(null) }
    finally { setLoadingGamme(false) }
  }, [])

  const fetchResources = useCallback(async () => {
    try {
      const [m, s, e] = await Promise.all([
        api.get('/machines', { params: { limit: 500 } }),
        api.get('/services', { params: { limit: 500 } }),
        api.get('/external-parts', { params: { limit: 500 } }),
      ])
      setMachinesList(m.data.items)
      setServicesList(s.data.items)
      setExtPartsList(e.data.items)
    } catch { /* non-blocking */ }
  }, [])

  const refreshSelected = useCallback(async (id_composant) => {
    if (!id_composant) return
    try {
      const { data } = await api.get(`/composants/${id_composant}`)
      setSelected(data)
    } catch { /* keep stale selection rather than clearing it */ }
  }, [])

  const fetchMatieres = useCallback(async () => {
    try {
      const { data } = await api.get('/matieres', { params: { limit: 500 } })
      setMatieres(data.items)
    } catch { /* non-blocking */ }
  }, [])

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
  useEffect(() => { fetchMatieres() }, [fetchMatieres])
  useEffect(() => { fetchResources() }, [fetchResources])
  useEffect(() => { fetchGamme(selected?.id_composant) }, [selected, fetchGamme])

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

  // ── Manufacturing Routing (Gamme) handlers ──────────────────────────────

  const openAddOperation = () => {
    const nextOrdre = gamme?.operations?.length
      ? Math.max(...gamme.operations.map(o => o.ordre)) + 1 : 1
    setOpFormData({ ...EMPTY_OP, ordre: nextOrdre })
    setOpFormMode('create')
    setOpFormError('')
    setShowOpForm(true)
  }

  const openEditOperation = (op) => {
    setOpFormData({
      id_operation: op.id_operation,
      step_type: op.id_machine ? 'machine' : op.id_service ? 'service' : 'external',
      description: op.description || '',
      tps_preparation: op.tps_preparation,
      tps_execution: op.tps_execution,
      plan_url: op.plan_url || '',
      id_machine: op.id_machine || '',
      id_service: op.id_service || '',
      id_piece_externe: op.id_piece_externe || '',
    })
    setOpFormMode('edit')
    setOpFormError('')
    setShowOpForm(true)
  }

  const handleOpSubmit = async (e) => {
    e.preventDefault()
    setOpSaving(true)
    setOpFormError('')
    const payload = {
      description: opFormData.description || null,
      tps_preparation: parseInt(opFormData.tps_preparation) || 0,
      tps_execution: parseInt(opFormData.tps_execution) || 0,
      plan_url: opFormData.plan_url || null,
      id_machine: opFormData.step_type === 'machine' && opFormData.id_machine ? parseInt(opFormData.id_machine) : null,
      id_service: opFormData.step_type === 'service' && opFormData.id_service ? parseInt(opFormData.id_service) : null,
      id_piece_externe: opFormData.step_type === 'external' && opFormData.id_piece_externe ? parseInt(opFormData.id_piece_externe) : null,
    }
    try {
      if (opFormMode === 'create') {
        await api.post(`/composants/${selected.id_composant}/gamme/operations`, {
          ...payload, ordre: opFormData.ordre,
        })
      } else {
        await api.put(`/composants/${selected.id_composant}/gamme/operations/${opFormData.id_operation}`, payload)
      }
      setShowOpForm(false)
      fetchGamme(selected.id_composant)
      fetchComposants()
      refreshSelected(selected.id_composant)
    } catch (err) {
      setOpFormError(err.response?.data?.detail || 'Error saving step')
    } finally {
      setOpSaving(false)
    }
  }

  const handleDeleteOperation = async (id_operation) => {
    if (!window.confirm('Delete this operation from the routing?')) return
    try {
      await api.delete(`/composants/${selected.id_composant}/gamme/operations/${id_operation}`)
      fetchGamme(selected.id_composant)
      fetchComposants()
      refreshSelected(selected.id_composant)
    } catch (err) { alert(err.response?.data?.detail || 'Error deleting step') }
  }

  const handleMoveOperation = async (id_operation, direction) => {
    try {
      await api.put(`/composants/${selected.id_composant}/gamme/operations/${id_operation}/move`, { direction })
      fetchGamme(selected.id_composant)
    } catch (err) { alert(err.response?.data?.detail || 'Error moving step') }
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

      {selected && (
        <div className="detail-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <h3>🛠 Manufacturing Routing{gamme?.version ? ` — v${gamme.version}` : ''}</h3>
            <button className="btn btn-primary" style={{ padding: '6px 12px', fontSize: '12px' }}
              onClick={openAddOperation}>+ Add Operation</button>
          </div>
          {loadingGamme ? (
            <p className="empty">Loading routing...</p>
          ) : !gamme || gamme.operations.length === 0 ? (
            <p className="empty">No routing yet — add at least one operation before this component can be scheduled</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order</th><th>Description</th><th>Machine / Service / Ext.</th>
                  <th>Setup (min)</th><th>Cycle (min/unit)</th><th></th>
                </tr>
              </thead>
              <tbody>
                {gamme.operations.map((op, idx) => (
                  <tr key={op.id_operation}>
                    <td className="td-center" style={{ fontWeight: 700 }}>{op.ordre}</td>
                    <td className="td-nom">{op.description || '—'}</td>
                    <td>{op.machine_nom || op.service_nom || op.piece_externe_nom || '—'}</td>
                    <td className="td-center">{op.tps_preparation}</td>
                    <td className="td-center">{op.tps_execution}</td>
                    <td style={{ display: 'flex', gap: 4 }}>
                      <button className="btn btn-secondary" style={{ padding: '3px 6px', fontSize: '11px' }}
                        disabled={idx === 0} onClick={() => handleMoveOperation(op.id_operation, 'up')}>↑</button>
                      <button className="btn btn-secondary" style={{ padding: '3px 6px', fontSize: '11px' }}
                        disabled={idx === gamme.operations.length - 1} onClick={() => handleMoveOperation(op.id_operation, 'down')}>↓</button>
                      <button className="btn btn-secondary" style={{ padding: '3px 6px', fontSize: '11px' }}
                        onClick={() => openEditOperation(op)}>✏</button>
                      <button className="btn btn-danger" style={{ padding: '3px 6px', fontSize: '11px' }}
                        onClick={() => handleDeleteOperation(op.id_operation)}>✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
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
                  <label>Raw Material</label>
                  <select name="id_matiere_brut" value={formData.id_matiere_brut} onChange={handleChange}>
                    <option value="">— None —</option>
                    {matieres.map(m => <option key={m.id_matiere} value={m.id_matiere}>{m.nom}</option>)}
                  </select>
                </div>
              </div>

              <div className="form-row">
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

      {/* Operation (routing step) Form Modal */}
      {showOpForm && (
        <div className="modal-overlay" onClick={() => setShowOpForm(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{opFormMode === 'create' ? '+ Add Operation' : '✏ Edit Operation'}</h3>
              <button className="modal-close" onClick={() => setShowOpForm(false)}>✕</button>
            </div>

            <form onSubmit={handleOpSubmit} className="modal-form">
              {opFormError && <div className="alert alert-error">{opFormError}</div>}

              <div className="form-row">
                <div className="form-group">
                  <label>Order</label>
                  <input type="number" min="1" value={opFormData.ordre ?? ''}
                    onChange={e => setOpFormData(p => ({ ...p, ordre: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label>Description</label>
                  <input value={opFormData.description} placeholder="e.g. Rough turning"
                    onChange={e => setOpFormData(p => ({ ...p, description: e.target.value }))} />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Setup time (min)</label>
                  <input type="number" min="0" value={opFormData.tps_preparation}
                    onChange={e => setOpFormData(p => ({ ...p, tps_preparation: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label>Cycle time (min/unit)</label>
                  <input type="number" min="0" value={opFormData.tps_execution}
                    onChange={e => setOpFormData(p => ({ ...p, tps_execution: e.target.value }))} />
                </div>
              </div>

              <div className="form-group">
                <label>Drawing URL</label>
                <input value={opFormData.plan_url} placeholder="https://..."
                  onChange={e => setOpFormData(p => ({ ...p, plan_url: e.target.value }))} />
              </div>

              <div className="form-group">
                <label>Step Type</label>
                <select value={opFormData.step_type}
                  onChange={e => setOpFormData(p => ({ ...p, step_type: e.target.value }))}>
                  <option value="machine">Machine Operation</option>
                  <option value="service">Service</option>
                  <option value="external">External Part</option>
                </select>
              </div>

              {opFormData.step_type === 'machine' && (
                <div className="form-group">
                  <label>Machine</label>
                  <select value={opFormData.id_machine}
                    onChange={e => setOpFormData(p => ({ ...p, id_machine: e.target.value }))}>
                    <option value="">— Select —</option>
                    {machinesList.map(m => <option key={m.id_machine} value={m.id_machine}>{m.nom}</option>)}
                  </select>
                </div>
              )}
              {opFormData.step_type === 'service' && (
                <div className="form-group">
                  <label>Service</label>
                  <select value={opFormData.id_service}
                    onChange={e => setOpFormData(p => ({ ...p, id_service: e.target.value }))}>
                    <option value="">— Select —</option>
                    {servicesList.map(s => <option key={s.id_service} value={s.id_service}>{s.nom}</option>)}
                  </select>
                </div>
              )}
              {opFormData.step_type === 'external' && (
                <div className="form-group">
                  <label>External Part</label>
                  <select value={opFormData.id_piece_externe}
                    onChange={e => setOpFormData(p => ({ ...p, id_piece_externe: e.target.value }))}>
                    <option value="">— Select —</option>
                    {extPartsList.map(x => <option key={x.id_piece_externe} value={x.id_piece_externe}>{x.nom}</option>)}
                  </select>
                </div>
              )}

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowOpForm(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={opSaving}>
                  {opSaving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Layout>
  )
}
