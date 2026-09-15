import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import api from '../api/client'
import './modules.css'
import { useDraggable } from '../hooks/useDraggable'

const EMPTY_FORM = { nom: '', reference: '', description: '', plan_url: '' }
const TYPE_LABELS = { component: '📦 Component', service: '⚙️ Service', external_part: '🔩 External Part' }
const TYPE_COLORS = { component: 'badge-blue', service: 'badge-orange', external_part: 'badge-gray' }

export default function Assemblies() {
  const [items, setItems]           = useState([])
  const [total, setTotal]           = useState(0)
  const [page, setPage]             = useState(1)
  const [pages, setPages]           = useState(1)
  const [search, setSearch]         = useState('')
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState('')
  const [selected, setSelected]     = useState(null)
  const [bom, setBom]               = useState([])
  const [showForm, setShowForm]     = useState(false)
  const [formData, setFormData]     = useState(EMPTY_FORM)
  const [formMode, setFormMode]     = useState('create')
  const [saving, setSaving]         = useState(false)
  const [formError, setFormError]   = useState('')
  const [showBomForm, setShowBomForm] = useState(false)
  const [bomType, setBomType]       = useState('component')
  const [bomItems, setBomItems]     = useState([])
  const [bomSelected, setBomSelected] = useState('')
  const [bomQty, setBomQty]         = useState('1')
  const [components, setComponents] = useState([])
  const [services, setServices]     = useState([])
  const [extParts, setExtParts]     = useState([])
  const [allRefs, setAllRefs]       = useState([]) // [{reference, nom}] across ALL assemblies, for the reference datalist + duplicate check
  const dragForm = useDraggable()
  const dragBomForm = useDraggable()

  const fetchAssemblies = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/assemblies', {
        params: { search: search || undefined, page, limit: 50 }
      })
      setItems(data.items); setTotal(data.total); setPages(data.pages); setError('')
    } catch { setError('Error loading assemblies') }
    finally { setLoading(false) }
  }, [search, page])

  const fetchBom = useCallback(async (id) => {
    try {
      const { data } = await api.get(`/assemblies/${id}/bom`)
      setBom(data)
    } catch { setBom([]) }
  }, [])

  const fetchRefData = useCallback(async () => {
    try {
      const [c, s, e] = await Promise.all([
        api.get('/composants', { params: { limit: 200 } }),
        api.get('/services', { params: { limit: 200 } }),
        api.get('/external-parts', { params: { limit: 200 } }),
      ])
      setComponents(c.data.items)
      setServices(s.data.items)
      setExtParts(e.data.items)
    } catch {}
  }, [])

  const fetchAllRefs = useCallback(async () => {
    // Backend caps "limit" at 200, so page through all results instead of
    // relying on a single oversized request (which the API rejects with a
    // 422 error, silently leaving the datalist empty).
    try {
      let all = []
      let p = 1
      let pages = 1
      do {
        const { data } = await api.get('/assemblies', { params: { page: p, limit: 200 } })
        all = all.concat(data.items)
        pages = data.pages
        p += 1
      } while (p <= pages)
      setAllRefs(all.map(a => ({ reference: a.reference || '', nom: a.nom, id_assemblage: a.id_assemblage })))
    } catch { /* non-blocking */ }
  }, [])

  useEffect(() => { fetchAssemblies(); fetchRefData(); fetchAllRefs() }, [fetchAssemblies, fetchRefData, fetchAllRefs])
  useEffect(() => { if (selected) fetchBom(selected.id_assemblage); else setBom([]) }, [selected, fetchBom])

  useEffect(() => {
    if (bomType === 'component') setBomItems(components.map(c => ({ id: c.id_composant, label: `${c.reference || ''} ${c.nom}`.trim() })))
    else if (bomType === 'service') setBomItems(services.map(s => ({ id: s.id_service, label: s.nom })))
    else setBomItems(extParts.map(p => ({ id: p.id_piece_externe, label: `${p.code_produit || ''} ${p.nom}`.trim() })))
    setBomSelected('')
  }, [bomType, components, services, extParts])

  const handleSearch = (e) => { setSearch(e.target.value); setPage(1) }

  const handleReferenceChange = (e) => {
    const value = e.target.value
    setFormData(prev => {
      const next = { ...prev, reference: value }
      // When creating, picking an existing reference from the suggestion list
      // also loads that assembly's name, so the user can see what they're
      // about to collide with before changing the reference.
      if (formMode === 'create') {
        const match = allRefs.find(r => r.reference.trim().toLowerCase() === value.trim().toLowerCase())
        if (match) next.nom = match.nom
      }
      return next
    })
  }

  const openCreate = () => { setFormData(EMPTY_FORM); setFormMode('create'); setFormError(''); setShowForm(true) }
  const openEdit = () => {
    if (!selected) return
    setFormData({ nom: selected.nom || '', reference: selected.reference || '', description: selected.description || '', plan_url: selected.plan_url || '' })
    setFormMode('edit'); setFormError(''); setShowForm(true)
  }

  const handleDelete = async () => {
    if (!selected) return
    if (!window.confirm(`Delete "${selected.nom}"?`)) return
    try { await api.delete(`/assemblies/${selected.id_assemblage}`); setSelected(null); fetchAssemblies() }
    catch (err) { alert(err.response?.data?.detail || 'Error deleting assembly') }
  }

  const handleSubmit = async (e) => {
    e.preventDefault(); setFormError('')
    if (formMode === 'create' && formData.reference.trim()) {
      const dup = allRefs.find(r => r.reference.trim().toLowerCase() === formData.reference.trim().toLowerCase())
      if (dup) {
        setFormError(`Reference "${formData.reference}" is already used by "${dup.nom}". Please change the reference.`)
        return
      }
    }
    setSaving(true)
    const payload = { nom: formData.nom, reference: formData.reference || null, description: formData.description || null, plan_url: formData.plan_url || null }
    try {
      if (formMode === 'create') await api.post('/assemblies', payload)
      else await api.put(`/assemblies/${selected.id_assemblage}`, payload)
      setShowForm(false); dragForm.reset(); setSelected(null); fetchAssemblies(); fetchAllRefs()
    } catch (err) { setFormError(err.response?.data?.detail || 'Error saving assembly') }
    finally { setSaving(false) }
  }

  const refreshSelected = useCallback(async (id_assemblage) => {
    if (!id_assemblage) return
    try {
      const { data } = await api.get(`/assemblies/${id_assemblage}`)
      setSelected(data)
    } catch { /* keep stale selection rather than clearing it */ }
  }, [])

  const [recalculating, setRecalculating] = useState(false)
  const handleRecalculate = async () => {
    if (!selected) return
    setRecalculating(true)
    try {
      await api.post(`/assemblies/${selected.id_assemblage}/recalculate`)
      refreshSelected(selected.id_assemblage)
      fetchAssemblies()
    } catch (err) { alert(err.response?.data?.detail || 'Error recalculating cost') }
    finally { setRecalculating(false) }
  }

  const handleAddBom = async () => {
    if (!bomSelected || !bomQty) return
    const payload = {
      quantite: parseInt(bomQty),
      id_composant: bomType === 'component' ? parseInt(bomSelected) : null,
      id_service: bomType === 'service' ? parseInt(bomSelected) : null,
      id_piece_externe: bomType === 'external_part' ? parseInt(bomSelected) : null,
    }
    try {
      await api.post(`/assemblies/${selected.id_assemblage}/bom`, payload)
      setShowBomForm(false); dragBomForm.reset()
      fetchBom(selected.id_assemblage)
      fetchAssemblies()
      refreshSelected(selected.id_assemblage)
    } catch (err) { alert(err.response?.data?.detail || 'Error adding BOM item') }
  }

  const handleRemoveBom = async (id_nomenclature) => {
    if (!window.confirm('Remove this item from BOM?')) return
    try {
      await api.delete(`/assemblies/${selected.id_assemblage}/bom/${id_nomenclature}`)
      fetchBom(selected.id_assemblage)
      fetchAssemblies()
      refreshSelected(selected.id_assemblage)
    } catch (err) { alert(err.response?.data?.detail || 'Error removing BOM item') }
  }

  return (
    <Layout>
      <div className="module-header">
        <div>
          <h2>🔗 Assemblies</h2>
          <span className="module-count">{total} assembl{total > 1 ? 'ies' : 'y'}</span>
        </div>
        <div className="module-actions">
          <button className="btn btn-primary" onClick={openCreate}>+ New</button>
          <button className="btn btn-secondary" onClick={openEdit} disabled={!selected}>✏ Edit</button>
          <button className="btn btn-danger" onClick={handleDelete} disabled={!selected}>🗑 Delete</button>
        </div>
      </div>

      <div className="search-bar">
        <input type="text" placeholder="🔍 Search by name or reference..." value={search} onChange={handleSearch} className="search-input" />
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr><th>Reference</th><th>Name</th><th>Cost Price</th><th>BOM Items</th></tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} className="table-loading">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={4} className="table-empty">No assemblies found</td></tr>
            ) : items.map((a) => (
              <tr key={a.id_assemblage}
                className={selected?.id_assemblage === a.id_assemblage ? 'selected' : ''}
                onClick={() => setSelected(a)} onDoubleClick={openEdit}>
                <td>{a.reference || '—'}</td>
                <td className="td-nom">{a.nom}</td>
                <td className="td-prix">{a.prix_revient != null ? `${parseFloat(a.prix_revient).toFixed(2)} €` : '—'}</td>
                <td className="td-center">
                  {a.nb_bom_items > 0
                    ? <span className="badge badge-blue">{a.nb_bom_items}</span>
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
        <>
          <div className="detail-card">
            <h3>Details — {selected.nom}</h3>
            <div className="detail-grid">
              <div><label>Reference</label><span>{selected.reference || '—'}</span></div>
              <div><label>Cost Price</label><span>{selected.prix_revient != null ? `${parseFloat(selected.prix_revient).toFixed(2)} €` : '—'}</span></div>
              <div><label>BOM Items</label><span>{selected.nb_bom_items}</span></div>
              {selected.description && <div className="detail-full"><label>Description</label><span>{selected.description}</span></div>}
              {selected.plan_url && <div className="detail-full"><label>Drawing</label><a href={selected.plan_url} target="_blank" rel="noreferrer">🔗 Open drawing</a></div>}
            </div>
          </div>

          <div className="detail-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <h3>📋 Bill of Materials</h3>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '12px' }}
                  disabled={recalculating}
                  onClick={handleRecalculate}>
                  {recalculating ? '⏳...' : '💰 Recalculate Cost'}
                </button>
                <button className="btn btn-primary" style={{ padding: '6px 12px', fontSize: '12px' }}
                  onClick={() => { setBomType('component'); setShowBomForm(true) }}>+ Add Item</button>
              </div>
            </div>
            {bom.length === 0
              ? <p className="empty">No BOM items — add components, services or external parts</p>
              : (
                <table className="data-table">
                  <thead>
                    <tr><th>Type</th><th>Reference</th><th>Name</th><th>Qty</th><th>Unit Price</th><th></th></tr>
                  </thead>
                  <tbody>
                    {bom.map((item) => (
                      <tr key={item.id_nomenclature}>
                        <td><span className={`badge ${TYPE_COLORS[item.type_item]}`}>{TYPE_LABELS[item.type_item]}</span></td>
                        <td>{item.item_reference || '—'}</td>
                        <td>{item.item_nom}</td>
                        <td className="td-center" style={{ fontWeight: 700 }}>{item.quantite}</td>
                        <td className="td-prix">{item.item_prix != null ? `${parseFloat(item.item_prix).toFixed(2)} €` : '—'}</td>
                        <td>
                          <button className="btn btn-danger" style={{ padding: '3px 8px', fontSize: '11px' }}
                            onClick={() => handleRemoveBom(item.id_nomenclature)}>✕</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            }
          </div>
        </>
      )}

      {/* Assembly Form */}
      {showForm && (
        <div className="modal-overlay" onClick={() => { setShowForm(false); dragForm.reset() }}>
          <div className="modal" style={{ transform: `translate(${dragForm.pos.x}px, ${dragForm.pos.y}px)` }} onClick={e => e.stopPropagation()}>
            <div className="modal-header" onMouseDown={dragForm.onMouseDown} style={{ cursor: 'grab', userSelect: 'none' }}>
              <h3>{formMode === 'create' ? '+ New Assembly' : '✏ Edit Assembly'}</h3>
              <button className="modal-close" onClick={() => { setShowForm(false); dragForm.reset() }}>✕</button>
            </div>
            <form onSubmit={handleSubmit} className="modal-form">
              {formError && <div className="alert alert-error">{formError}</div>}
              <div className="form-row">
                <div className="form-group">
                  <label>Reference{formMode === 'edit' && <span style={{ fontWeight: 400, color: '#7f8c8d' }}> (locked after creation)</span>}</label>
                  <input name="reference" value={formData.reference} onChange={handleReferenceChange}
                    placeholder="e.g. ASM-001" list="assembly-references" autoComplete="off"
                    disabled={formMode === 'edit'}
                    title={formMode === 'edit' ? 'Reference cannot be changed once the assembly exists — it may already be used in orders or BOMs.' : undefined} />
                  <datalist id="assembly-references">
                    {allRefs.map(r => <option key={r.id_assemblage} value={r.reference} />)}
                  </datalist>
                </div>
                <div className="form-group">
                  <label>Name *</label>
                  <input name="nom" value={formData.nom} onChange={e => setFormData(p => ({ ...p, nom: e.target.value }))} required placeholder="Assembly name" />
                </div>
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea value={formData.description} onChange={e => setFormData(p => ({ ...p, description: e.target.value }))} rows={3} />
              </div>
              <div className="form-group">
                <label>Drawing URL</label>
                <input value={formData.plan_url} onChange={e => setFormData(p => ({ ...p, plan_url: e.target.value }))} placeholder="https://..." />
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => { setShowForm(false); dragForm.reset() }}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* BOM Add Form */}
      {showBomForm && selected && (
        <div className="modal-overlay" onClick={() => { setShowBomForm(false); dragBomForm.reset() }}>
          <div className="modal" style={{ transform: `translate(${dragBomForm.pos.x}px, ${dragBomForm.pos.y}px)` }} onClick={e => e.stopPropagation()}>
            <div className="modal-header" onMouseDown={dragBomForm.onMouseDown} style={{ cursor: 'grab', userSelect: 'none' }}>
              <h3>+ Add BOM Item</h3>
              <button className="modal-close" onClick={() => { setShowBomForm(false); dragBomForm.reset() }}>✕</button>
            </div>
            <div className="modal-form">
              <div className="form-group">
                <label>Item Type</label>
                <select value={bomType} onChange={e => setBomType(e.target.value)}>
                  <option value="component">Component</option>
                  <option value="service">Service</option>
                  <option value="external_part">External Part</option>
                </select>
              </div>
              <div className="form-group">
                <label>Item *</label>
                <select value={bomSelected} onChange={e => setBomSelected(e.target.value)}>
                  <option value="">— Select —</option>
                  {bomItems.map(i => <option key={i.id} value={i.id}>{i.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Quantity *</label>
                <input type="number" step="1" min="1"
                  value={bomQty}
                  onChange={e => {
                    const v = e.target.value
                    setBomQty(v === '' ? '' : String(parseInt(v, 10)))
                  }} />
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => { setShowBomForm(false); dragBomForm.reset() }}>Cancel</button>
                <button className="btn btn-primary" onClick={handleAddBom} disabled={!bomSelected}>Add</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
