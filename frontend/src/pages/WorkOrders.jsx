import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import api from '../api/client'
import './modules.css'
import { useDraggable } from '../hooks/useDraggable'

const PRIORITY_COLORS = { 1: '#e74c3c', 2: '#e67e22', 3: '#f39c12', 4: '#f39c12', 5: '#27ae60' }
const PRIORITY_LABELS = { 1: 'Urgent', 2: 'High', 3: 'Elevated', 4: 'Elevated', 5: 'Normal' }
const STATUT_COLORS = {
  a_planifier: '#e67e22', planifie: '#3498db', en_cours: '#8e44ad',
  termine: '#27ae60', terminee: '#27ae60', annule: '#95a5a6', rebutee: '#e74c3c',
}
const STATUT_LABELS = {
  a_planifier: 'To Schedule', planifie: 'Planned', en_cours: 'In Progress',
  termine: 'Completed', terminee: 'Completed', annule: 'Cancelled', rebutee: 'Scrapped',
}

const STATUT_FILTER_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'a_planifier', label: 'To Schedule' },
  { value: 'planifie', label: 'Planned' },
  { value: 'en_cours', label: 'In Progress' },
  { value: 'termine', label: 'Completed' },
  { value: 'annule', label: 'Cancelled' },
]

export default function WorkOrders() {
  const [items, setItems]         = useState([])
  const [total, setTotal]         = useState(0)
  const [page, setPage]           = useState(1)
  const [pages, setPages]         = useState(1)
  const [search, setSearch]       = useState('')
  const [filterStatut, setFilterStatut] = useState('')
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')
  const [selected, setSelected]   = useState(null)
  const [detail, setDetail]       = useState(null)
  const [showEdit, setShowEdit]   = useState(false)
  const [editPrio, setEditPrio]   = useState(5)
  const [editStatut, setEditStatut] = useState('')
  const [saving, setSaving]       = useState(false)
  const dragEdit = useDraggable()

  const fetchWOs = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, limit: 50 }
      if (filterStatut) params.statut = filterStatut
      const { data } = await api.get('/work-orders', { params })
      setItems(data.items); setTotal(data.total); setPages(data.pages); setError('')
    } catch { setError('Error loading work orders') }
    finally { setLoading(false) }
  }, [page, filterStatut])

  const fetchDetail = useCallback(async (id) => {
    try {
      const { data } = await api.get(`/work-orders/${id}`)
      setDetail(data)
    } catch {}
  }, [])

  useEffect(() => { fetchWOs() }, [fetchWOs])
  useEffect(() => { if (selected) fetchDetail(selected.id_of_assemblage); else setDetail(null) }, [selected, fetchDetail])

  const handleSearch = (e) => { setSearch(e.target.value); setPage(1) }

  const openEdit = () => {
    if (!selected) return
    setEditPrio(selected.priorite)
    setEditStatut(selected.statut)
    setShowEdit(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put(`/work-orders/${selected.id_of_assemblage}`, {
        priorite: editPrio,
        statut:   editStatut,
      })
      setShowEdit(false); dragEdit.reset()
      fetchWOs()
      fetchDetail(selected.id_of_assemblage)
    } catch (err) {
      alert(err.response?.data?.detail || 'Error updating work order')
    } finally { setSaving(false) }
  }

  const filtered = search
    ? items.filter(i => i.assemblage_nom.toLowerCase().includes(search.toLowerCase()) ||
        (i.client || '').toLowerCase().includes(search.toLowerCase()) ||
        (i.code_commande || '').toLowerCase().includes(search.toLowerCase()))
    : items

  return (
    <Layout>
      <div className="module-header">
        <div>
          <h2>🏭 Work Orders</h2>
          <span className="module-count">{total} work order{total > 1 ? 's' : ''}</span>
        </div>
        <div className="module-actions">
          <button className="btn btn-secondary" onClick={openEdit} disabled={!selected}>✏ Edit Priority/Status</button>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '12px', flexWrap: 'wrap' }}>
        <input type="text" placeholder="🔍 Search assembly, client, order..." value={search}
          onChange={handleSearch} className="search-input" style={{ maxWidth: 320 }} />
        <select value={filterStatut} onChange={e => { setFilterStatut(e.target.value); setPage(1) }}
          style={{ padding: '8px 12px', border: '1px solid #dde', borderRadius: '8px', fontSize: '14px' }}>
          {STATUT_FILTER_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Priority</th><th>Assembly</th><th>Customer</th><th>Order</th>
              <th>Qty</th><th>Launch Date</th><th>Due Date</th><th>Status</th><th>WOs</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9} className="table-loading">Loading...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={9} className="table-empty">No work orders found</td></tr>
            ) : filtered.map((ofa) => (
              <tr key={ofa.id_of_assemblage}
                className={selected?.id_of_assemblage === ofa.id_of_assemblage ? 'selected' : ''}
                onClick={() => setSelected(ofa)} onDoubleClick={openEdit}>
                <td>
                  <span className="badge" style={{ background: PRIORITY_COLORS[ofa.priorite] || '#27ae60', color: 'white' }}>
                    {PRIORITY_LABELS[ofa.priorite] || 'Normal'}
                  </span>
                </td>
                <td className="td-nom">{ofa.assemblage_nom}</td>
                <td>{ofa.client || '—'}</td>
                <td>{ofa.code_commande || '—'}</td>
                <td className="td-center" style={{ fontWeight: 700 }}>{ofa.quantite}</td>
                <td>{ofa.date_lancement || '—'}</td>
                <td style={{ color: ofa.date_fin_prevue ? '#2c3e50' : '#95a5a6' }}>
                  {ofa.date_fin_prevue || '—'}
                </td>
                <td>
                  <span className="statut-badge" style={{ background: STATUT_COLORS[ofa.statut] || '#95a5a6' }}>
                    {STATUT_LABELS[ofa.statut] || ofa.statut_label}
                  </span>
                </td>
                <td className="td-center">
                  {ofa.nb_ofs > 0
                    ? <span className="badge badge-blue">{ofa.nb_ofs}</span>
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

      {detail && (
        <>
          <div className="detail-card">
            <h3>Work Order — {detail.assemblage_nom}</h3>
            <div className="detail-grid">
              <div><label>Customer</label><span>{detail.client || '—'}</span></div>
              <div><label>Order Code</label><span>{detail.code_commande || '—'}</span></div>
              <div><label>Quantity</label><span>{detail.quantite}</span></div>
              <div><label>Priority</label>
                <span style={{ color: PRIORITY_COLORS[detail.priorite], fontWeight: 700 }}>
                  {PRIORITY_LABELS[detail.priorite]}
                </span>
              </div>
              <div><label>Status</label>
                <span style={{ color: STATUT_COLORS[detail.statut], fontWeight: 700 }}>
                  {STATUT_LABELS[detail.statut] || detail.statut_label}
                </span>
              </div>
              <div><label>Launch Date</label><span>{detail.date_lancement || '—'}</span></div>
              <div><label>Due Date</label><span>{detail.date_fin_prevue || '—'}</span></div>
              <div><label>Manufacturing Orders</label><span>{detail.nb_ofs}</span></div>
            </div>
          </div>

          {detail.ofs && detail.ofs.length > 0 && (
            <div className="detail-card">
              <h3>📋 Manufacturing Orders</h3>
              {detail.ofs.map((of) => (
                <div key={of.id_of} style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8 }}>
                    <strong>{of.code_of || `OF #${of.id_of}`}</strong>
                    <span style={{ color: '#7f8c8d', fontSize: 13 }}>{of.composant_nom}</span>
                    <span style={{ color: '#7f8c8d', fontSize: 13 }}>× {of.quantite}</span>
                    <span className="statut-badge" style={{ background: STATUT_COLORS[of.statut] || '#95a5a6' }}>
                      {STATUT_LABELS[of.statut] || of.statut_label}
                    </span>
                  </div>
                  {of.ops && of.ops.length > 0 && (
                    <table className="data-table" style={{ fontSize: 12 }}>
                      <thead>
                        <tr><th>#</th><th>Operation</th><th>Machine</th><th>Duration</th><th>Start</th><th>End</th><th>Status</th></tr>
                      </thead>
                      <tbody>
                        {of.ops.map((op) => (
                          <tr key={op.id_op}>
                            <td>{op.ordre}</td>
                            <td>{op.nom_operation}</td>
                            <td>{op.machine_nom || '—'}</td>
                            <td>{op.duree_prevue_h != null ? `${op.duree_prevue_h}h` : '—'}</td>
                            <td>{op.date_debut || '—'}</td>
                            <td>{op.date_fin || '—'}</td>
                            <td>
                              <span className="statut-badge" style={{ background: STATUT_COLORS[op.statut] || '#95a5a6', fontSize: 11 }}>
                                {STATUT_LABELS[op.statut] || op.statut_label}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Edit Priority/Status Modal */}
      {showEdit && selected && (
        <div className="modal-overlay" onClick={() => { setShowEdit(false); dragEdit.reset() }}>
          <div className="modal" style={{ transform: `translate(${dragEdit.pos.x}px, ${dragEdit.pos.y}px)` }} onClick={e => e.stopPropagation()}>
            <div className="modal-header" onMouseDown={dragEdit.onMouseDown} style={{ cursor: 'grab', userSelect: 'none' }}>
              <h3>✏ Edit — {selected.assemblage_nom}</h3>
              <button className="modal-close" onClick={() => { setShowEdit(false); dragEdit.reset() }}>✕</button>
            </div>
            <div className="modal-form">
              <div className="form-group">
                <label>Priority</label>
                <select value={editPrio} onChange={e => setEditPrio(parseInt(e.target.value))}>
                  <option value={1}>1 — Urgent</option>
                  <option value={2}>2 — High</option>
                  <option value={3}>3 — Elevated</option>
                  <option value={4}>4 — Elevated</option>
                  <option value={5}>5 — Normal</option>
                </select>
              </div>
              <div className="form-group">
                <label>Status</label>
                <select value={editStatut} onChange={e => setEditStatut(e.target.value)}>
                  <option value="planifie">Planned</option>
                  <option value="en_cours">In Progress</option>
                  <option value="termine">Completed</option>
                  <option value="annule">Cancelled</option>
                </select>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => { setShowEdit(false); dragEdit.reset() }}>Cancel</button>
                <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                  {saving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
