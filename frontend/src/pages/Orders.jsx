import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import api from '../api/client'
import './modules.css'

const today = new Date().toISOString().split('T')[0]

const EMPTY_FORM = {
  client: '', numero_externe: '', date_commande: today,
  date_livraison: '', statut: 'planifiee',
}

const STATUT_COLORS = {
  planifiee: '#e67e22', en_cours: '#8e44ad',
  terminee: '#27ae60', annulee: '#95a5a6',
  on_hold: '#e67e22', released: '#3498db',
  completed: '#27ae60', cancelled: '#95a5a6',
}

export default function Orders() {
  const [items, setItems]           = useState([])
  const [total, setTotal]           = useState(0)
  const [page, setPage]             = useState(1)
  const [pages, setPages]           = useState(1)
  const [search, setSearch]         = useState('')
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState('')
  const [selected, setSelected]     = useState(null)
  const [orderDetail, setOrderDetail] = useState(null)
  const [showForm, setShowForm]     = useState(false)
  const [formData, setFormData]     = useState(EMPTY_FORM)
  const [formMode, setFormMode]     = useState('create')
  const [saving, setSaving]         = useState(false)
  const [formError, setFormError]   = useState('')
  const [showLineForm, setShowLineForm] = useState(false)
  const [assemblies, setAssemblies] = useState([])
  const [lineAsm, setLineAsm]       = useState('')
  const [lineQty, setLineQty]       = useState('1')

  const fetchOrders = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/orders', {
        params: { search: search || undefined, page, limit: 50 }
      })
      setItems(data.items); setTotal(data.total); setPages(data.pages); setError('')
    } catch { setError('Error loading orders') }
    finally { setLoading(false) }
  }, [search, page])

  const fetchDetail = useCallback(async (id) => {
    try {
      const { data } = await api.get(`/orders/${id}`)
      setOrderDetail(data)
    } catch {}
  }, [])

  const fetchAssemblies = useCallback(async () => {
    try {
      const { data } = await api.get('/assemblies', { params: { limit: 200 } })
      setAssemblies(data.items)
    } catch {}
  }, [])

  useEffect(() => { fetchOrders(); fetchAssemblies() }, [fetchOrders, fetchAssemblies])
  useEffect(() => { if (selected) fetchDetail(selected.id_commande); else setOrderDetail(null) }, [selected, fetchDetail])

  const handleSearch = (e) => { setSearch(e.target.value); setPage(1) }

  const openCreate = () => {
    setFormData(EMPTY_FORM); setFormMode('create'); setFormError(''); setShowForm(true)
  }

  const openEdit = () => {
    if (!selected) return
    setFormData({
      client:         selected.client         || '',
      numero_externe: selected.numero_externe  || '',
      date_commande:  selected.date_commande   || today,
      date_livraison: selected.date_livraison  || '',
      statut:         selected.statut          || 'planifiee',
    })
    setFormMode('edit'); setFormError(''); setShowForm(true)
  }

  const handleDelete = async () => {
    if (!selected) return
    if (!window.confirm(`Delete order "${selected.code_commande || selected.client}"?`)) return
    try {
      await api.delete(`/orders/${selected.id_commande}`)
      setSelected(null); setOrderDetail(null); fetchOrders()
    } catch (err) { alert(err.response?.data?.detail || 'Error deleting order') }
  }

  const handleSubmit = async (e) => {
    e.preventDefault(); setSaving(true); setFormError('')
    const payload = {
      client:         formData.client,
      numero_externe: formData.numero_externe || null,
      date_commande:  formData.date_commande,
      date_livraison: formData.date_livraison || null,
      statut:         formData.statut,
    }
    try {
      if (formMode === 'create') await api.post('/orders', payload)
      else await api.put(`/orders/${selected.id_commande}`, payload)
      setShowForm(false); setSelected(null); fetchOrders()
    } catch (err) { setFormError(err.response?.data?.detail || 'Error saving order') }
    finally { setSaving(false) }
  }

  const handleAddLine = async () => {
    if (!lineAsm || !lineQty) return
    try {
      await api.post(`/orders/${selected.id_commande}/lines`, {
        id_assemblage: parseInt(lineAsm),
        quantite: parseInt(lineQty),
      })
      setShowLineForm(false)
      fetchDetail(selected.id_commande)
      fetchOrders()
    } catch (err) { alert(err.response?.data?.detail || 'Error adding line') }
  }

  const handleDeleteLine = async (id_ligne) => {
    if (!window.confirm('Remove this line?')) return
    try {
      await api.delete(`/orders/${selected.id_commande}/lines/${id_ligne}`)
      fetchDetail(selected.id_commande); fetchOrders()
    } catch (err) { alert(err.response?.data?.detail || 'Error removing line') }
  }

  const [releasing, setReleasing] = useState(null)
  const handleReleaseLine = async (id_ligne) => {
    if (!window.confirm('Generate Production Orders for this line?')) return
    setReleasing(id_ligne)
    try {
      const { data } = await api.post(`/orders/${selected.id_commande}/lines/${id_ligne}/release`)
      alert(`${data.message} (${data.nb_ofs} work order${data.nb_ofs > 1 ? 's' : ''} created)`)
      fetchDetail(selected.id_commande); fetchOrders()
    } catch (err) { alert(err.response?.data?.detail || 'Error releasing line') }
    finally { setReleasing(null) }
  }

  return (
    <Layout>
      <div className="module-header">
        <div>
          <h2>📋 Orders</h2>
          <span className="module-count">{total} order{total > 1 ? 's' : ''}</span>
        </div>
        <div className="module-actions">
          <button className="btn btn-primary" onClick={openCreate}>+ New</button>
          <button className="btn btn-secondary" onClick={openEdit} disabled={!selected}>✏ Edit</button>
          <button className="btn btn-danger" onClick={handleDelete} disabled={!selected}>🗑 Delete</button>
        </div>
      </div>

      <div className="search-bar">
        <input type="text" placeholder="🔍 Search by client, code or external ref..." value={search} onChange={handleSearch} className="search-input" />
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Code</th><th>Ext. Ref.</th><th>Customer</th>
              <th>Order Date</th><th>Delivery Date</th><th>Status</th><th>Lines</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="table-loading">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={7} className="table-empty">No orders found</td></tr>
            ) : items.map((c) => (
              <tr key={c.id_commande}
                className={selected?.id_commande === c.id_commande ? 'selected' : ''}
                onClick={() => setSelected(c)} onDoubleClick={openEdit}>
                <td style={{ fontWeight: 700 }}>{c.code_commande || '—'}</td>
                <td>{c.numero_externe || '—'}</td>
                <td className="td-nom">{c.client}</td>
                <td>{c.date_commande}</td>
                <td style={{ color: c.date_livraison ? '#2c3e50' : '#95a5a6' }}>
                  {c.date_livraison || '—'}
                </td>
                <td>
                  <span className="statut-badge" style={{ background: STATUT_COLORS[c.statut] || '#95a5a6' }}>
                    {c.statut_label}
                  </span>
                </td>
                <td className="td-center">
                  {c.nb_lignes > 0
                    ? <span className="badge badge-blue">{c.nb_lignes}</span>
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

      {orderDetail && (
        <>
          <div className="detail-card">
            <h3>Order — {orderDetail.code_commande || orderDetail.client}</h3>
            <div className="detail-grid">
              <div><label>Code</label><span>{orderDetail.code_commande || '—'}</span></div>
              <div><label>Customer</label><span>{orderDetail.client}</span></div>
              <div><label>External Ref.</label><span>{orderDetail.numero_externe || '—'}</span></div>
              <div><label>Order Date</label><span>{orderDetail.date_commande}</span></div>
              <div><label>Delivery Date</label><span>{orderDetail.date_livraison || '—'}</span></div>
              <div><label>Status</label>
                <span style={{ color: STATUT_COLORS[orderDetail.statut], fontWeight: 700 }}>
                  {orderDetail.statut_label}
                </span>
              </div>
            </div>
          </div>

          <div className="detail-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <h3>📦 Order Lines</h3>
              <button className="btn btn-primary" style={{ padding: '6px 12px', fontSize: '12px' }}
                onClick={() => { setLineAsm(''); setLineQty('1'); setShowLineForm(true) }}>
                + Add Line
              </button>
            </div>
            {orderDetail.lignes.length === 0
              ? <p className="empty">No order lines — add assemblies to this order</p>
              : (
                <table className="data-table">
                  <thead>
                    <tr><th>Line Code</th><th>Assembly</th><th>Quantity</th><th>Status</th><th>Cost Snapshot</th><th></th></tr>
                  </thead>
                  <tbody>
                    {orderDetail.lignes.map((l) => (
                      <tr key={l.id_ligne}>
                        <td>{l.code_ligne || '—'}</td>
                        <td className="td-nom">{l.assemblage_nom}</td>
                        <td className="td-center" style={{ fontWeight: 700 }}>{l.quantite}</td>
                        <td>
                          <span className="statut-badge" style={{ background: l.statut_color }}>
                            {l.statut_label}
                          </span>
                        </td>
                        <td className="td-prix">
                          {l.prix_revient_snapshot != null ? `${parseFloat(l.prix_revient_snapshot).toFixed(2)} €` : '—'}
                        </td>
                        <td style={{ display: 'flex', gap: 6 }}>
                          {l.statut === 'on_hold' && (
                            <>
                              <button className="btn btn-primary" style={{ padding: '3px 8px', fontSize: '11px' }}
                                disabled={releasing === l.id_ligne}
                                onClick={() => handleReleaseLine(l.id_ligne)}>
                                {releasing === l.id_ligne ? '⏳...' : '🚀 Release'}
                              </button>
                              <button className="btn btn-danger" style={{ padding: '3px 8px', fontSize: '11px' }}
                                onClick={() => handleDeleteLine(l.id_ligne)}>✕</button>
                            </>
                          )}
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

      {/* Order Form Modal */}
      {showForm && (
        <div className="modal-overlay" onClick={() => setShowForm(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{formMode === 'create' ? '+ New Order' : '✏ Edit Order'}</h3>
              <button className="modal-close" onClick={() => setShowForm(false)}>✕</button>
            </div>
            <form onSubmit={handleSubmit} className="modal-form">
              {formError && <div className="alert alert-error">{formError}</div>}
              <div className="form-row">
                <div className="form-group">
                  <label>Customer *</label>
                  <input name="client" value={formData.client}
                    onChange={e => setFormData(p => ({ ...p, client: e.target.value }))}
                    required placeholder="Customer name" />
                </div>
                <div className="form-group">
                  <label>External Reference</label>
                  <input value={formData.numero_externe}
                    onChange={e => setFormData(p => ({ ...p, numero_externe: e.target.value }))}
                    placeholder="Customer PO number" />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Order Date *</label>
                  <input type="date" value={formData.date_commande}
                    onChange={e => setFormData(p => ({ ...p, date_commande: e.target.value }))} required />
                </div>
                <div className="form-group">
                  <label>Delivery Date</label>
                  <input type="date" value={formData.date_livraison}
                    onChange={e => setFormData(p => ({ ...p, date_livraison: e.target.value }))} />
                </div>
              </div>
              <div className="form-group">
                <label>Status</label>
                <select value={formData.statut}
                  onChange={e => setFormData(p => ({ ...p, statut: e.target.value }))}>
                  <option value="planifiee">Planned</option>
                  <option value="en_cours">In Progress</option>
                  <option value="terminee">Completed</option>
                  <option value="annulee">Cancelled</option>
                </select>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Line Modal */}
      {showLineForm && selected && (
        <div className="modal-overlay" onClick={() => setShowLineForm(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>+ Add Order Line</h3>
              <button className="modal-close" onClick={() => setShowLineForm(false)}>✕</button>
            </div>
            <div className="modal-form">
              <div className="form-group">
                <label>Assembly *</label>
                <select value={lineAsm} onChange={e => setLineAsm(e.target.value)}>
                  <option value="">— Select assembly —</option>
                  {assemblies.map(a => (
                    <option key={a.id_assemblage} value={a.id_assemblage}>
                      {a.reference ? `${a.reference} — ` : ''}{a.nom}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Quantity *</label>
                <input type="number" step="1" min="1"
                  value={lineQty}
                  onChange={e => {
                    const v = e.target.value
                    setLineQty(v === '' ? '' : String(parseInt(v, 10)))
                  }} />
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowLineForm(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={handleAddLine} disabled={!lineAsm}>Add Line</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
