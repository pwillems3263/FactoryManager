import { useState, useEffect, useCallback, useRef } from 'react'
import Layout from '../components/Layout'
import api from '../api/client'
import './modules.css'
import './TimeTracking.css'

const STATUT_COLORS = {
  planifiee: '#3498db', en_cours: '#8e44ad',
  terminee: '#27ae60', rebutee: '#e74c3c',
}
const STATUT_LABELS = {
  planifiee: 'Planned', en_cours: 'In Progress',
  terminee: 'Completed', rebutee: 'Scrapped',
}
const PAUSE_MOTIFS = [
  { value: 'repas', label: 'Meal break' },
  { value: 'panne', label: 'Machine breakdown' },
  { value: 'attente_matiere', label: 'Waiting for material' },
  { value: 'formation', label: 'Training / meeting' },
  { value: 'autre', label: 'Other' },
]

function ElapsedTimer({ startTime }) {
  const [elapsed, setElapsed] = useState('00:00:00')
  useEffect(() => {
    if (!startTime) return
    const start = new Date(startTime)
    const update = () => {
      const now = new Date()
      const diff = Math.floor((now - start) / 1000)
      const h = Math.floor(diff / 3600).toString().padStart(2, '0')
      const m = Math.floor((diff % 3600) / 60).toString().padStart(2, '0')
      const s = (diff % 60).toString().padStart(2, '0')
      setElapsed(`${h}:${m}:${s}`)
    }
    update()
    const interval = setInterval(update, 1000)
    return () => clearInterval(interval)
  }, [startTime])
  return <span className="elapsed-timer">{elapsed}</span>
}

export default function TimeTracking() {
  const [ops, setOps]               = useState([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState('')
  const [selected, setSelected]     = useState(null)
  const [showPauseModal, setShowPauseModal] = useState(false)
  const [pauseMotif, setPauseMotif] = useState('autre')
  const [filterMachine, setFilterMachine] = useState('')
  const [machines, setMachines]     = useState([])
  const [actionLoading, setActionLoading] = useState(false)
  const intervalRef = useRef(null)

  const fetchOps = useCallback(async () => {
    try {
      const params = {}
      if (filterMachine) params.id_machine = filterMachine
      const { data } = await api.get('/time-tracking/ops', { params })
      setOps(data)
      setError('')
      // Update selected if exists
      if (selected) {
        const updated = data.find(o => o.id_op === selected.id_op)
        if (updated) setSelected(updated)
      }
    } catch { setError('Error loading operations') }
    finally { setLoading(false) }
  }, [filterMachine, selected])

  const fetchMachines = useCallback(async () => {
    try {
      const { data } = await api.get('/machines', { params: { limit: 200 } })
      setMachines(data.items)
    } catch {}
  }, [])

  useEffect(() => {
    fetchOps(); fetchMachines()
    intervalRef.current = setInterval(fetchOps, 30000)
    return () => clearInterval(intervalRef.current)
  }, [fetchOps, fetchMachines])

  const doAction = async (action, extra = {}) => {
    if (!selected) return
    setActionLoading(true)
    try {
      let res
      if (action === 'pause') {
        res = await api.post(`/time-tracking/ops/${selected.id_op}/pause`, { motif: pauseMotif })
        setShowPauseModal(false)
      } else {
        res = await api.post(`/time-tracking/ops/${selected.id_op}/${action}`)
      }
      setSelected(res.data)
      fetchOps()
    } catch (err) {
      alert(err.response?.data?.detail || `Error: ${action}`)
    } finally { setActionLoading(false) }
  }

  const inProgress = ops.filter(o => o.statut === 'en_cours')
  const planned    = ops.filter(o => o.statut === 'planifiee')

  return (
    <Layout>
      <div className="module-header">
        <div>
          <h2>⏱️ Time Tracking</h2>
          <span className="module-count">
            {inProgress.length} in progress · {planned.length} planned
          </span>
        </div>
        <div className="module-actions">
          <select value={filterMachine} onChange={e => setFilterMachine(e.target.value)}
            style={{ padding: '8px 12px', border: '1px solid #dde', borderRadius: '8px', fontSize: '13px' }}>
            <option value="">All machines</option>
            {machines.map(m => <option key={m.id_machine} value={m.id_machine}>{m.nom}</option>)}
          </select>
          <button className="btn btn-primary" onClick={fetchOps}>🔄 Refresh</button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="tt-layout">
        {/* Operations list */}
        <div className="tt-list">
          {loading ? (
            <div className="table-loading">Loading...</div>
          ) : ops.length === 0 ? (
            <div className="table-empty">No operations for today</div>
          ) : (
            <>
              {inProgress.length > 0 && (
                <>
                  <div className="tt-section-title">🟣 In Progress</div>
                  {inProgress.map(op => (
                    <OpCard key={op.id_op} op={op} selected={selected}
                      onClick={() => setSelected(op)} />
                  ))}
                </>
              )}
              {planned.length > 0 && (
                <>
                  <div className="tt-section-title">🔵 Planned</div>
                  {planned.map(op => (
                    <OpCard key={op.id_op} op={op} selected={selected}
                      onClick={() => setSelected(op)} />
                  ))}
                </>
              )}
            </>
          )}
        </div>

        {/* Action panel */}
        <div className="tt-panel">
          {!selected ? (
            <div className="tt-panel-empty">
              <p>← Select an operation to track time</p>
            </div>
          ) : (
            <div className="tt-panel-content">
              <div className="tt-panel-header">
                <span className="statut-badge" style={{ background: STATUT_COLORS[selected.statut] }}>
                  {STATUT_LABELS[selected.statut]}
                </span>
                {selected.en_pause && <span className="badge badge-orange">⏸ On pause</span>}
              </div>

              <h3>{selected.nom_operation}</h3>
              <div className="tt-info">
                <div><label>Assembly</label><span>{selected.assembly_nom}</span></div>
                <div><label>Component</label><span>{selected.composant_nom}</span></div>
                <div><label>WO Code</label><span>{selected.code_of || '—'}</span></div>
                <div><label>Machine</label><span>{selected.machine_nom || '—'}</span></div>
                <div><label>Planned Duration</label>
                  <span>{selected.duree_prevue_h != null ? `${selected.duree_prevue_h}h` : '—'}</span>
                </div>
                <div><label>Planned Start</label><span>{selected.date_debut || '—'}</span></div>
              </div>

              {selected.statut === 'en_cours' && selected.date_debut_reelle && (
                <div className="tt-timer-box">
                  <label>Elapsed time</label>
                  <ElapsedTimer startTime={selected.date_debut_reelle} />
                </div>
              )}

              {/* Pauses */}
              {selected.pauses && selected.pauses.length > 0 && (
                <div className="tt-pauses">
                  <label>Pauses</label>
                  {selected.pauses.map(p => (
                    <div key={p.id_pause} className="tt-pause-item">
                      <span>{p.debut_pause} → {p.fin_pause || '...'}</span>
                      <span className="badge badge-orange">{p.motif}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Action buttons */}
              <div className="tt-actions">
                {selected.statut === 'planifiee' && (
                  <button className="btn btn-success tt-btn"
                    onClick={() => doAction('start')} disabled={actionLoading}>
                    ▶ Start Operation
                  </button>
                )}
                {selected.statut === 'en_cours' && !selected.en_pause && (
                  <>
                    <button className="btn btn-secondary tt-btn"
                      onClick={() => setShowPauseModal(true)} disabled={actionLoading}>
                      ⏸ Pause
                    </button>
                    <button className="btn btn-success tt-btn"
                      onClick={() => doAction('finish')} disabled={actionLoading}>
                      ✅ Finish Operation
                    </button>
                  </>
                )}
                {selected.statut === 'en_cours' && selected.en_pause && (
                  <button className="btn btn-primary tt-btn"
                    onClick={() => doAction('resume')} disabled={actionLoading}>
                    ▶ Resume
                  </button>
                )}
                {selected.statut === 'terminee' && (
                  <div className="tt-done">✅ Operation completed at {selected.date_fin_reelle}</div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Pause Modal */}
      {showPauseModal && (
        <div className="modal-overlay" onClick={() => setShowPauseModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>⏸ Start Pause</h3>
              <button className="modal-close" onClick={() => setShowPauseModal(false)}>✕</button>
            </div>
            <div className="modal-form">
              <div className="form-group">
                <label>Reason *</label>
                <select value={pauseMotif} onChange={e => setPauseMotif(e.target.value)}>
                  {PAUSE_MOTIFS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                </select>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowPauseModal(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={() => doAction('pause')}>Start Pause</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}

function OpCard({ op, selected, onClick }) {
  return (
    <div className={`tt-op-card ${selected?.id_op === op.id_op ? 'selected' : ''}`} onClick={onClick}>
      <div className="tt-op-card-header">
        <span className="statut-dot" style={{ background: STATUT_COLORS[op.statut] }}>
          {STATUT_LABELS[op.statut]}
        </span>
        {op.en_pause && <span className="badge badge-orange" style={{ fontSize: 11 }}>⏸ Paused</span>}
      </div>
      <div className="tt-op-name">{op.nom_operation}</div>
      <div className="tt-op-meta">
        <span>{op.composant_nom}</span>
        {op.machine_nom && <span>· {op.machine_nom}</span>}
        {op.duree_prevue_h && <span>· {op.duree_prevue_h}h</span>}
      </div>
    </div>
  )
}
