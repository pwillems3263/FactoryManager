import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import api from '../api/client'
import './modules.css'

const STATUT_COLORS = {
  available:    '#27ae60',
  disponible:   '#27ae60',
  maintenance:  '#e67e22',
  hors_service: '#e74c3c',
}

const EMPTY_FORM = {
  nom: '', id_type_machine: '', capacite_h_jour: '', statut: 'available',
  tarif_horaire: '', cout_operateur: '', charge_operateur: '',
  travaille_samedi: false, travaille_dimanche: false, multi_taches: false,
}

const EMPTY_EVENT = { type_arret: 'maintenance', description: '' }

export default function Machines() {
  const [items, setItems]           = useState([])
  const [total, setTotal]           = useState(0)
  const [page, setPage]             = useState(1)
  const [pages, setPages]           = useState(1)
  const [search, setSearch]         = useState('')
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState('')
  const [selected, setSelected]     = useState(null)
  const [events, setEvents]         = useState([])
  const [types, setTypes]           = useState([])
  const [showForm, setShowForm]     = useState(false)
  const [formData, setFormData]     = useState(EMPTY_FORM)
  const [formMode, setFormMode]     = useState('create')
  const [saving, setSaving]         = useState(false)
  const [formError, setFormError]   = useState('')
  const [showEvent, setShowEvent]   = useState(false)
  const [eventData, setEventData]   = useState(EMPTY_EVENT)

  const fetchMachines = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/machines', {
        params: { search: search || undefined, page, limit: 100 }
      })
      setItems(data.items)
      setTotal(data.total)
      setPages(data.pages)
      setError('')
    } catch {
      setError('Error loading machines')
    } finally {
      setLoading(false)
    }
  }, [search, page])

  const fetchTypes = useCallback(async () => {
    try {
      const { data } = await api.get('/machines/types')
      setTypes(data)
    } catch {}
  }, [])

  const fetchEvents = useCallback(async (id) => {
    try {
      const { data } = await api.get(`/machines/${id}/events`)
      setEvents(data)
    } catch {}
  }, [])

  useEffect(() => { fetchMachines(); fetchTypes() }, [fetchMachines, fetchTypes])

  useEffect(() => {
    if (selected) fetchEvents(selected.id_machine)
    else setEvents([])
  }, [selected, fetchEvents])

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
      nom:               selected.nom               || '',
      id_type_machine:   selected.id_type_machine   || '',
      capacite_h_jour:   selected.capacite_h_jour   || '',
      statut:            selected.statut             || 'available',
      tarif_horaire:     selected.tarif_horaire      || '',
      cout_operateur:    selected.cout_operateur     || '',
      charge_operateur:  selected.charge_operateur   || '',
      travaille_samedi:  selected.travaille_samedi   || false,
      travaille_dimanche: selected.travaille_dimanche || false,
      multi_taches:      selected.multi_taches       || false,
    })
    setFormMode('edit')
    setFormError('')
    setShowForm(true)
  }

  const handleDelete = async () => {
    if (!selected) return
    if (!window.confirm(`Delete "${selected.nom}"?`)) return
    try {
      await api.delete(`/machines/${selected.id_machine}`)
      setSelected(null)
      fetchMachines()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error deleting machine')
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setFormError('')
    const payload = {
      nom:               formData.nom,
      id_type_machine:   formData.id_type_machine   ? parseInt(formData.id_type_machine)   : null,
      capacite_h_jour:   formData.capacite_h_jour   !== '' ? parseFloat(formData.capacite_h_jour)   : null,
      statut:            formData.statut,
      tarif_horaire:     formData.tarif_horaire      !== '' ? parseFloat(formData.tarif_horaire)      : null,
      cout_operateur:    formData.cout_operateur     !== '' ? parseFloat(formData.cout_operateur)     : null,
      charge_operateur:  formData.charge_operateur   !== '' ? parseFloat(formData.charge_operateur)   : null,
      travaille_samedi:  formData.travaille_samedi,
      travaille_dimanche: formData.travaille_dimanche,
      multi_taches:      formData.multi_taches,
    }
    try {
      if (formMode === 'create') {
        await api.post('/machines', payload)
      } else {
        await api.put(`/machines/${selected.id_machine}`, payload)
      }
      setShowForm(false)
      setSelected(null)
      fetchMachines()
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Error saving machine')
    } finally {
      setSaving(false)
    }
  }

  const handleChange = (e) => {
    const val = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setFormData(prev => ({ ...prev, [e.target.name]: val }))
  }

  const handleEventSubmit = async (e) => {
    e.preventDefault()
    try {
      await api.post(`/machines/${selected.id_machine}/events`, eventData)
      setShowEvent(false)
      fetchEvents(selected.id_machine)
      fetchMachines()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error creating event')
    }
  }

  const closeEvent = async (id_arret) => {
    if (!window.confirm('Close this event?')) return
    try {
      await api.put(`/machines/${selected.id_machine}/events/${id_arret}/close`)
      fetchEvents(selected.id_machine)
      fetchMachines()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error closing event')
    }
  }

  return (
    <Layout>
      <div className="module-header">
        <div>
          <h2>🏗️ Machines</h2>
          <span className="module-count">{total} machine{total > 1 ? 's' : ''}</span>
        </div>
        <div className="module-actions">
          <button className="btn btn-primary" onClick={openCreate}>+ New</button>
          <button className="btn btn-secondary" onClick={openEdit} disabled={!selected}>✏ Edit</button>
          <button className="btn btn-danger" onClick={handleDelete} disabled={!selected}>🗑 Delete</button>
          <button className="btn btn-success" onClick={() => { setEventData(EMPTY_EVENT); setShowEvent(true) }} disabled={!selected}>⚠ New Event</button>
        </div>
      </div>

      <div className="search-bar">
        <input type="text" placeholder="🔍 Search by name..." value={search} onChange={handleSearch} className="search-input" />
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Capacity (h/d)</th>
              <th>Machine Rate (€/h)</th>
              <th>Operator Cost (€/h)</th>
              <th>Multi-task</th>
              <th>Status</th>
              <th>Active Events</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="table-loading">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={8} className="table-empty">No machines found</td></tr>
            ) : items.map((m) => (
              <tr
                key={m.id_machine}
                className={selected?.id_machine === m.id_machine ? 'selected' : ''}
                onClick={() => setSelected(m)}
                onDoubleClick={openEdit}
              >
                <td className="td-nom">{m.nom}</td>
                <td>{m.type_nom || '—'}</td>
                <td className="td-center">{m.capacite_h_jour != null ? `${m.capacite_h_jour}h` : '—'}</td>
                <td className="td-prix">{m.tarif_horaire != null ? `${parseFloat(m.tarif_horaire).toFixed(2)} €` : '—'}</td>
                <td className="td-prix">{m.cout_operateur != null ? `${parseFloat(m.cout_operateur).toFixed(2)} €` : '—'}</td>
                <td className="td-center">{m.multi_taches ? '✅' : '—'}</td>
                <td>
                  <span className="statut-dot" style={{ background: STATUT_COLORS[m.statut] || '#95a5a6' }}>
                    {m.statut_label}
                  </span>
                </td>
                <td className="td-center">
                  {m.nb_arrets_actifs > 0
                    ? <span className="badge badge-red">{m.nb_arrets_actifs}</span>
                    : <span className="badge badge-green">0</span>}
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
              <div><label>Type</label><span>{selected.type_nom || '—'}</span></div>
              <div><label>Status</label>
                <span style={{ color: STATUT_COLORS[selected.statut] || '#95a5a6', fontWeight: 700 }}>
                  {selected.statut_label}
                </span>
              </div>
              <div><label>Capacity</label><span>{selected.capacite_h_jour != null ? `${selected.capacite_h_jour} h/day` : '—'}</span></div>
              <div><label>Machine Rate</label><span>{selected.tarif_horaire != null ? `${parseFloat(selected.tarif_horaire).toFixed(2)} €/h` : '—'}</span></div>
              <div><label>Operator Cost</label><span>{selected.cout_operateur != null ? `${parseFloat(selected.cout_operateur).toFixed(2)} €/h` : '—'}</span></div>
              <div><label>Operator Load</label><span>{selected.charge_operateur != null ? `${selected.charge_operateur}%` : '—'}</span></div>
              <div><label>Works Saturday</label><span>{selected.travaille_samedi ? 'Yes' : 'No'}</span></div>
              <div><label>Works Sunday</label><span>{selected.travaille_dimanche ? 'Yes' : 'No'}</span></div>
              <div><label>Multi-task</label><span>{selected.multi_taches ? 'Yes' : 'No'}</span></div>
            </div>
          </div>

          {events.length > 0 && (
            <div className="detail-card">
              <h3>⚠️ Machine Events</h3>
              <table className="data-table">
                <thead>
                  <tr><th>Type</th><th>Description</th><th>Start</th><th>End</th><th>Status</th><th></th></tr>
                </thead>
                <tbody>
                  {events.map((ev) => (
                    <tr key={ev.id_arret}>
                      <td>{ev.type_arret}</td>
                      <td>{ev.description || '—'}</td>
                      <td>{ev.date_debut || '—'}</td>
                      <td>{ev.date_fin || '—'}</td>
                      <td>
                        <span className={`badge ${ev.en_cours ? 'badge-red' : 'badge-green'}`}>
                          {ev.en_cours ? 'Ongoing' : 'Closed'}
                        </span>
                      </td>
                      <td>
                        {ev.en_cours && (
                          <button className="btn btn-success" style={{ padding: '4px 10px', fontSize: '12px' }}
                            onClick={() => closeEvent(ev.id_arret)}>
                            Close
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Machine Form Modal */}
      {showForm && (
        <div className="modal-overlay" onClick={() => setShowForm(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{formMode === 'create' ? '+ New Machine' : '✏ Edit Machine'}</h3>
              <button className="modal-close" onClick={() => setShowForm(false)}>✕</button>
            </div>
            <form onSubmit={handleSubmit} className="modal-form">
              {formError && <div className="alert alert-error">{formError}</div>}

              <div className="form-row">
                <div className="form-group">
                  <label>Name *</label>
                  <input name="nom" value={formData.nom} onChange={handleChange} required placeholder="Machine name" />
                </div>
                <div className="form-group">
                  <label>Type</label>
                  <select name="id_type_machine" value={formData.id_type_machine} onChange={handleChange}>
                    <option value="">— Select type —</option>
                    {types.map(t => <option key={t.id_type} value={t.id_type}>{t.nom}</option>)}
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Status</label>
                  <select name="statut" value={formData.statut} onChange={handleChange}>
                    <option value="available">Available</option>
                    <option value="maintenance">Maintenance</option>
                    <option value="hors_service">Out of Service</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Capacity (h/day)</label>
                  <input type="number" step="0.5" name="capacite_h_jour" value={formData.capacite_h_jour} onChange={handleChange} placeholder="8" />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Machine Rate (€/h)</label>
                  <input type="number" step="0.01" name="tarif_horaire" value={formData.tarif_horaire} onChange={handleChange} />
                </div>
                <div className="form-group">
                  <label>Operator Cost (€/h)</label>
                  <input type="number" step="0.01" name="cout_operateur" value={formData.cout_operateur} onChange={handleChange} />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Operator Load (%)</label>
                  <input type="number" step="1" min="0" max="100" name="charge_operateur" value={formData.charge_operateur} onChange={handleChange} />
                </div>
              </div>

              <div className="form-row" style={{ gap: '24px' }}>
                {[['travaille_samedi','Works Saturday'],['travaille_dimanche','Works Sunday'],['multi_taches','Multi-task']].map(([name, label]) => (
                  <div key={name} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <input type="checkbox" name={name} id={name} checked={formData[name]} onChange={handleChange} />
                    <label htmlFor={name} style={{ cursor: 'pointer', fontSize: '13px' }}>{label}</label>
                  </div>
                ))}
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Event Form Modal */}
      {showEvent && selected && (
        <div className="modal-overlay" onClick={() => setShowEvent(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>⚠ New Event — {selected.nom}</h3>
              <button className="modal-close" onClick={() => setShowEvent(false)}>✕</button>
            </div>
            <form onSubmit={handleEventSubmit} className="modal-form">
              <div className="form-group">
                <label>Event Type *</label>
                <select name="type_arret" value={eventData.type_arret}
                  onChange={e => setEventData(prev => ({ ...prev, type_arret: e.target.value }))}>
                  <option value="maintenance">Maintenance</option>
                  <option value="breakdown">Breakdown</option>
                  <option value="scheduled">Scheduled Stop</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea rows={3} value={eventData.description}
                  onChange={e => setEventData(prev => ({ ...prev, description: e.target.value }))} />
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowEvent(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Create Event</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Layout>
  )
}
