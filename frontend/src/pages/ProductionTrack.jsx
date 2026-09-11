import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import api from '../api/client'
import './modules.css'

const STATUT_COLORS = {
  a_planifier: '#e67e22', planifie: '#3498db', en_cours: '#8e44ad',
  termine: '#27ae60', terminee: '#27ae60', annule: '#95a5a6', rebutee: '#e74c3c',
}
const STATUT_LABELS = {
  a_planifier: 'To Schedule', planifie: 'Planned', en_cours: 'In Progress',
  termine: 'Completed', terminee: 'Completed', annule: 'Cancelled', rebutee: 'Scrapped',
}

const FILTER_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'a_planifier', label: 'To Schedule' },
  { value: 'planifie', label: 'Planned' },
  { value: 'en_cours', label: 'In Progress' },
  { value: 'termine', label: 'Completed' },
]

export default function ProductionTrack() {
  const [items, setItems]         = useState([])
  const [total, setTotal]         = useState(0)
  const [page, setPage]           = useState(1)
  const [pages, setPages]         = useState(1)
  const [search, setSearch]       = useState('')
  const [filterStatut, setFilter] = useState('')
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')
  const [selected, setSelected]   = useState(null)
  const [detail, setDetail]       = useState(null)

  const fetchItems = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, limit: 50 }
      if (filterStatut) params.statut = filterStatut
      if (search) params.search = search
      const { data } = await api.get('/production-track', { params })
      setItems(data.items); setTotal(data.total); setPages(data.pages); setError('')
    } catch { setError('Error loading production data') }
    finally { setLoading(false) }
  }, [page, filterStatut, search])

  const fetchDetail = useCallback(async (id) => {
    try {
      const { data } = await api.get(`/production-track/${id}`)
      setDetail(data)
    } catch {}
  }, [])

  useEffect(() => { fetchItems() }, [fetchItems])
  useEffect(() => {
    if (selected) fetchDetail(selected.id_of)
    else setDetail(null)
  }, [selected, fetchDetail])

  return (
    <Layout>
      <div className="module-header">
        <div>
          <h2>📈 Production Tracking</h2>
          <span className="module-count">{total} manufacturing order{total > 1 ? 's' : ''}</span>
        </div>
        <div className="module-actions">
          <button className="btn btn-primary" onClick={fetchItems}>🔄 Refresh</button>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
        <input type="text" placeholder="🔍 Search WO code or component..."
          value={search} onChange={e => { setSearch(e.target.value); setPage(1) }}
          className="search-input" style={{ maxWidth: 300 }} />
        <div style={{ display: 'flex', gap: '6px' }}>
          {FILTER_OPTIONS.map(opt => (
            <button key={opt.value}
              className={`btn ${filterStatut === opt.value ? 'btn-primary' : ''}`}
              style={{ padding: '6px 14px', fontSize: '12px',
                background: filterStatut === opt.value ? STATUT_COLORS[opt.value] || '#3498db' : '#f0f2f5',
                color: filterStatut === opt.value ? 'white' : '#2c3e50',
                border: '1px solid #dde' }}
              onClick={() => { setFilter(opt.value); setPage(1) }}>
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>WO Code</th><th>Order</th><th>Assembly</th><th>Component</th>
              <th>Qty</th><th>Due Date</th><th>Status</th><th>Progress</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="table-loading">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={8} className="table-empty">No manufacturing orders found</td></tr>
            ) : items.map((of) => (
              <tr key={of.id_of}
                className={selected?.id_of === of.id_of ? 'selected' : ''}
                onClick={() => setSelected(of)}>
                <td style={{ fontWeight: 700 }}>{of.code_of || '—'}</td>
                <td>{of.order_code || '—'}</td>
                <td>{of.assembly_nom}</td>
                <td className="td-nom">{of.composant_nom}</td>
                <td className="td-center">{of.quantite}</td>
                <td style={{ color: of.date_fin_prevue ? '#2c3e50' : '#95a5a6' }}>
                  {of.date_fin_prevue || '—'}
                </td>
                <td>
                  <span className="statut-badge" style={{ background: STATUT_COLORS[of.statut] || '#95a5a6' }}>
                    {STATUT_LABELS[of.statut] || of.statut_label}
                  </span>
                </td>
                <td style={{ minWidth: 120 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ flex: 1, height: 8, background: '#f0f2f5', borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{
                        height: '100%', width: `${of.progress_pct}%`,
                        background: of.progress_pct === 100 ? '#27ae60' : '#3498db',
                        borderRadius: 4, transition: 'width 0.3s'
                      }} />
                    </div>
                    <span style={{ fontSize: 11, color: '#7f8c8d', minWidth: 32 }}>{of.progress_pct}%</span>
                  </div>
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
            <h3>Manufacturing Order — {detail.code_of || `#${detail.id_of}`}</h3>
            <div className="detail-grid">
              <div><label>Order</label><span>{detail.order_code || '—'}</span></div>
              <div><label>Customer</label><span>{detail.client || '—'}</span></div>
              <div><label>Assembly</label><span>{detail.assembly_nom}</span></div>
              <div><label>Component</label><span>{detail.composant_nom}</span></div>
              <div><label>Quantity</label><span>{detail.quantite}</span></div>
              <div><label>Status</label>
                <span style={{ color: STATUT_COLORS[detail.statut], fontWeight: 700 }}>
                  {STATUT_LABELS[detail.statut] || detail.statut_label}
                </span>
              </div>
              <div><label>Launch Date</label><span>{detail.date_lancement || '—'}</span></div>
              <div><label>Due Date</label><span>{detail.date_fin_prevue || '—'}</span></div>
              <div><label>Completion Date</label><span>{detail.date_fin_reelle || '—'}</span></div>
              <div><label>Delivery Date</label><span>{detail.date_livraison || '—'}</span></div>
              <div><label>Progress</label>
                <span>{detail.nb_ops_done} / {detail.nb_ops_total} operations ({detail.progress_pct}%)</span>
              </div>
            </div>
          </div>

          {detail.operations && detail.operations.length > 0 && (
            <div className="detail-card">
              <h3>🔧 Operations</h3>
              <table className="data-table">
                <thead>
                  <tr><th>#</th><th>Operation</th><th>Machine</th><th>Duration</th><th>Start</th><th>End</th><th>Status</th></tr>
                </thead>
                <tbody>
                  {detail.operations.map((op) => (
                    <tr key={op.id_op}>
                      <td className="td-center">{op.ordre}</td>
                      <td>{op.nom_operation}</td>
                      <td>{op.machine_nom || '—'}</td>
                      <td>{op.duree_prevue_h != null ? `${op.duree_prevue_h}h` : '—'}</td>
                      <td>{op.date_debut || '—'}</td>
                      <td>{op.date_fin || '—'}</td>
                      <td>
                        <span className="statut-badge" style={{ background: STATUT_COLORS[op.statut] || '#95a5a6' }}>
                          {STATUT_LABELS[op.statut] || op.statut_label}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </Layout>
  )
}
