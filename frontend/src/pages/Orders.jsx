import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import api from '../api/client'
import './modules.css'
import { useDraggable } from '../hooks/useDraggable'

const today = new Date().toISOString().split('T')[0]

const EMPTY_FORM = {
  client: '', numero_externe: '', date_commande: today,
  date_livraison: '', date_livraison_reelle: '', statut: 'estimation',
}

// Order-level status. Each one gates real behavior (see backend):
//   estimation      -> can be freely edited and deleted
//   part_confirmed  -> delivery date is frozen
//   confirmed       -> delivery date is frozen
//   finished        -> a delivery date is required
const ORDER_STATUS_LOCKS_DELIVERY = ['part_confirmed', 'confirmed']

const STATUT_COLORS = {
  estimation: '#95a5a6', part_confirmed: '#e67e22',
  confirmed: '#3498db', finished: '#27ae60',
  on_hold: '#e67e22', released: '#3498db', completed: '#27ae60',
}

const STATUT_LABELS = {
  estimation: 'Estimation', part_confirmed: 'Part. Confirmed',
  confirmed: 'Confirmed', finished: 'Finished',
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
  const [customers, setCustomers]   = useState([])
  const [lineAsm, setLineAsm]       = useState('')
  const [lineQty, setLineQty]       = useState('1')
  const dragForm = useDraggable()
  const dragLineForm = useDraggable()

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

  const fetchCustomers = useCallback(async () => {
    try {
      const { data } = await api.get('/orders/customers')
      setCustomers(data)
    } catch {}
  }, [])

  useEffect(() => { fetchOrders(); fetchAssemblies(); fetchCustomers() }, [fetchOrders, fetchAssemblies, fetchCustomers])
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
      date_livraison_reelle: selected.date_livraison_reelle || '',
      statut:         selected.statut          || 'estimation',
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
      date_livraison_reelle: formData.date_livraison_reelle || null,
      statut:         formData.statut,
    }
    try {
      if (formMode === 'create') await api.post('/orders', payload)
      else await api.put(`/orders/${selected.id_commande}`, payload)
      setShowForm(false); dragForm.reset(); setSelected(null); fetchOrders(); fetchCustomers()
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
      setShowLineForm(false); dragLineForm.reset()
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

  const [lineQtyEdits, setLineQtyEdits] = useState({}) // { [id_ligne]: string being typed }
  const [lineQtySaving, setLineQtySaving] = useState(null)

  const handleLineQtyChange = (id_ligne, value) => {
    setLineQtyEdits(prev => ({ ...prev, [id_ligne]: value }))
  }

  const handleLineQtyCommit = async (line) => {
    const raw = lineQtyEdits[line.id_ligne]
    if (raw === undefined) return // untouched
    setLineQtyEdits(prev => { const n = { ...prev }; delete n[line.id_ligne]; return n })
    const value = parseInt(raw, 10)
    if (!Number.isInteger(value) || String(value) !== raw.trim() || value <= 0) {
      if (raw.trim() !== '' && parseFloat(raw) !== line.quantite) {
        alert('Quantity must be a whole number.')
      }
      return
    }
    if (value === line.quantite) return
    setLineQtySaving(line.id_ligne)
    try {
      await api.put(`/orders/${selected.id_commande}/lines/${line.id_ligne}`, { quantite: value })
      fetchDetail(selected.id_commande)
      fetchOrders()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error updating quantity')
    } finally {
      setLineQtySaving(null)
    }
  }

  const [releasing, setReleasing] = useState(null)
  const [showReleaseForm, setShowReleaseForm] = useState(false)
  const [releaseLine, setReleaseLine] = useState(null)
  const [releaseSpecialPrice, setReleaseSpecialPrice] = useState('')
  const dragReleaseForm = useDraggable()

  const openReleaseModal = (line) => {
    setReleaseLine(line)
    setReleaseSpecialPrice('')
    setShowReleaseForm(true)
  }

  const handleConfirmRelease = async () => {
    if (!releaseLine) return
    if (!window.confirm('Generate Production Orders for this line?')) return
    setReleasing(releaseLine.id_ligne)
    try {
      const body = releaseSpecialPrice.trim() !== '' ? { prix_special: parseFloat(releaseSpecialPrice) } : {}
      const { data } = await api.post(`/orders/${selected.id_commande}/lines/${releaseLine.id_ligne}/release`, body)
      alert(`${data.message} (${data.nb_ofs} work order${data.nb_ofs > 1 ? 's' : ''} created)`)
      setShowReleaseForm(false); dragReleaseForm.reset()
      fetchDetail(selected.id_commande); fetchOrders()
    } catch (err) { alert(err.response?.data?.detail || 'Error releasing line') }
    finally { setReleasing(null) }
  }

  // Delivery date is frozen while the order stays Part. Confirmed / Confirmed
  // (mirrors the backend rule in update_order). If the Status dropdown is
  // changed to something else in the same edit (e.g. Finished, to record
  // the actual date), it unlocks immediately.
  const deliveryLocked = formMode === 'edit'
    && ORDER_STATUS_LOCKS_DELIVERY.includes(selected?.statut)
    && ORDER_STATUS_LOCKS_DELIVERY.includes(formData.statut)

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
          <button className="btn btn-danger" onClick={handleDelete}
            disabled={!selected || selected.statut !== 'estimation'}
            title={selected && selected.statut !== 'estimation' ? 'Only orders still in Estimation can be deleted' : undefined}>
            🗑 Delete
          </button>
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
              <th>Order Date</th><th>Est. Delivery</th><th>Actual Delivery</th><th>Status</th><th>Lines</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="table-loading">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={8} className="table-empty">No orders found</td></tr>
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
                <td style={{ color: c.date_livraison_reelle ? '#2c3e50' : '#95a5a6' }}>
                  {c.date_livraison_reelle || '—'}
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
              <div><label>Est. Delivery Date</label><span>{orderDetail.date_livraison || '—'}</span></div>
              <div><label>Actual Delivery Date</label><span>{orderDetail.date_livraison_reelle || '—'}</span></div>
              <div><label>Status</label>
                <span style={{ color: STATUT_COLORS[orderDetail.statut], fontWeight: 700 }}>
                  {orderDetail.statut_label}
                </span>
              </div>
              <div><label>Current Total</label>
                <span style={{ color: '#7f8c8d' }}>
                  {orderDetail.total_prix_actuel != null ? `${orderDetail.total_prix_actuel.toFixed(2)} €` : '—'}
                </span>
              </div>
              <div><label>Final Price</label>
                <span style={{ fontWeight: 700 }}>
                  {orderDetail.total_prix_snapshot != null ? `${orderDetail.total_prix_snapshot.toFixed(2)} €` : '—'}
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
                    <tr><th>Line Code</th><th>Assembly</th><th>Quantity</th><th>Status</th><th>Current Price</th><th>Final Price</th><th></th></tr>
                  </thead>
                  <tbody>
                    {orderDetail.lignes.map((l) => (
                      <tr key={l.id_ligne}>
                        <td>{l.code_ligne || '—'}</td>
                        <td className="td-nom">{l.assemblage_nom}</td>
                        <td className="td-center">
                          {l.statut === 'on_hold' ? (
                            <input
                              type="number"
                              min="1"
                              step="1"
                              value={lineQtyEdits[l.id_ligne] ?? l.quantite}
                              disabled={lineQtySaving === l.id_ligne}
                              onChange={e => handleLineQtyChange(l.id_ligne, e.target.value)}
                              onBlur={() => handleLineQtyCommit(l)}
                              onKeyDown={e => { if (e.key === 'Enter') e.target.blur() }}
                              style={{ width: 70, textAlign: 'center', fontWeight: 700, padding: '4px 6px' }}
                            />
                          ) : (
                            <span style={{ fontWeight: 700 }}>{l.quantite}</span>
                          )}
                        </td>
                        <td>
                          <span className="statut-badge" style={{ background: l.statut_color }}>
                            {l.statut_label}
                          </span>
                        </td>
                        <td className="td-prix" style={{ color: '#7f8c8d' }}>
                          {l.prix_revient_actuel != null ? `${parseFloat(l.prix_revient_actuel).toFixed(2)} €` : '—'}
                        </td>
                        <td className="td-prix">
                          {l.prix_revient_snapshot != null ? `${parseFloat(l.prix_revient_snapshot).toFixed(2)} €` : '—'}
                        </td>
                        <td style={{ display: 'flex', gap: 6 }}>
                          {l.statut === 'on_hold' && (
                            <>
                              <button className="btn btn-primary" style={{ padding: '3px 8px', fontSize: '11px' }}
                                disabled={releasing === l.id_ligne}
                                onClick={() => openReleaseModal(l)}>
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
        <div className="modal-overlay" onClick={() => { setShowForm(false); dragForm.reset() }}>
          <div className="modal" style={{ transform: `translate(${dragForm.pos.x}px, ${dragForm.pos.y}px)` }} onClick={e => e.stopPropagation()}>
            <div className="modal-header" onMouseDown={dragForm.onMouseDown} style={{ cursor: 'grab', userSelect: 'none' }}>
              <h3>{formMode === 'create' ? '+ New Order' : '✏ Edit Order'}</h3>
              <button className="modal-close" onClick={() => { setShowForm(false); dragForm.reset() }}>✕</button>
            </div>
            <form onSubmit={handleSubmit} className="modal-form">
              {formError && <div className="alert alert-error">{formError}</div>}
              <div className="form-row">
                <div className="form-group">
                  <label>Customer *</label>
                  <input name="client" value={formData.client}
                    onChange={e => setFormData(p => ({ ...p, client: e.target.value }))}
                    required placeholder="Customer name" list="order-customers" autoComplete="off" />
                  <datalist id="order-customers">
                    {customers.map(name => <option key={name} value={name} />)}
                  </datalist>
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
                  <label>
                    Est. Delivery Date
                    {deliveryLocked && <span style={{ fontWeight: 400, color: '#7f8c8d' }}> (locked — order is {STATUT_LABELS[formData.statut]})</span>}
                  </label>
                  <input type="date" value={formData.date_livraison}
                    disabled={deliveryLocked}
                    onChange={e => setFormData(p => ({ ...p, date_livraison: e.target.value }))} />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>
                    Actual Delivery Date
                    {formData.statut === 'finished' && <span style={{ color: '#e74c3c' }}> *</span>}
                  </label>
                  <input type="date" value={formData.date_livraison_reelle}
                    required={formData.statut === 'finished'}
                    onChange={e => setFormData(p => ({ ...p, date_livraison_reelle: e.target.value }))} />
                  <p style={{ color: '#7f8c8d', fontSize: 12, marginTop: 4 }}>
                    Kept separate from the estimated date above, so the two can be compared later.
                  </p>
                </div>
              </div>
              <div className="form-group">
                <label>Status</label>
                <select value={formData.statut}
                  onChange={e => setFormData(p => ({ ...p, statut: e.target.value }))}>
                  <option value="estimation">Estimation</option>
                  <option value="part_confirmed">Part. Confirmed</option>
                  <option value="confirmed">Confirmed</option>
                  <option value="finished">Finished</option>
                </select>
                {formData.statut === 'finished' && !formData.date_livraison_reelle && (
                  <p style={{ color: '#e74c3c', fontSize: 12, marginTop: 4 }}>
                    An actual delivery date must be recorded before this order can be marked Finished.
                  </p>
                )}
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => { setShowForm(false); dragForm.reset() }}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Line Modal */}
      {showLineForm && selected && (
        <div className="modal-overlay" onClick={() => { setShowLineForm(false); dragLineForm.reset() }}>
          <div className="modal" style={{ transform: `translate(${dragLineForm.pos.x}px, ${dragLineForm.pos.y}px)` }} onClick={e => e.stopPropagation()}>
            <div className="modal-header" onMouseDown={dragLineForm.onMouseDown} style={{ cursor: 'grab', userSelect: 'none' }}>
              <h3>+ Add Order Line</h3>
              <button className="modal-close" onClick={() => { setShowLineForm(false); dragLineForm.reset() }}>✕</button>
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
                <button type="button" className="btn btn-secondary" onClick={() => { setShowLineForm(false); dragLineForm.reset() }}>Cancel</button>
                <button className="btn btn-primary" onClick={handleAddLine} disabled={!lineAsm}>Add Line</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Release Line Modal */}
      {showReleaseForm && releaseLine && (
        <div className="modal-overlay" onClick={() => { setShowReleaseForm(false); dragReleaseForm.reset() }}>
          <div className="modal" style={{ transform: `translate(${dragReleaseForm.pos.x}px, ${dragReleaseForm.pos.y}px)` }} onClick={e => e.stopPropagation()}>
            <div className="modal-header" onMouseDown={dragReleaseForm.onMouseDown} style={{ cursor: 'grab', userSelect: 'none' }}>
              <h3>🚀 Release — {releaseLine.assemblage_nom}</h3>
              <button className="modal-close" onClick={() => { setShowReleaseForm(false); dragReleaseForm.reset() }}>✕</button>
            </div>
            <div className="modal-form">
              <div className="detail-grid" style={{ marginBottom: 4 }}>
                <div><label>Quantity</label><span>{releaseLine.quantite}</span></div>
                <div><label>Current calculated price</label>
                  <span>{releaseLine.prix_revient_actuel != null ? `${parseFloat(releaseLine.prix_revient_actuel).toFixed(2)} €` : '—'}</span>
                </div>
              </div>
              <div className="form-group">
                <label>Special price (optional)</label>
                <input type="number" step="0.01" min="0.01" value={releaseSpecialPrice}
                  placeholder={releaseLine.prix_revient_actuel != null ? parseFloat(releaseLine.prix_revient_actuel).toFixed(2) : '0.00'}
                  onChange={e => setReleaseSpecialPrice(e.target.value)} />
                <p style={{ color: '#7f8c8d', fontSize: 12, marginTop: 4 }}>
                  Leave empty to freeze the calculated price above. Enter a value only if a special
                  deal was negotiated with the customer for this line — it will be frozen instead.
                </p>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary"
                  onClick={() => { setShowReleaseForm(false); dragReleaseForm.reset() }}>Cancel</button>
                <button className="btn btn-primary" disabled={releasing === releaseLine.id_ligne}
                  onClick={handleConfirmRelease}>
                  {releasing === releaseLine.id_ligne ? 'Releasing...' : '🚀 Release'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
