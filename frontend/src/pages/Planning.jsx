import { useState, useEffect, useCallback, useRef } from 'react'
import Layout from '../components/Layout'
import api from '../api/client'
import './modules.css'
import './Planning.css'

const STATUT_COLORS = {
  planifiee: '#3498db', en_cours: '#8e44ad',
  terminee: '#27ae60', rebutee: '#e74c3c', a_planifier: '#e67e22',
}
const STATUT_LABELS = {
  planifiee: 'Planned', en_cours: 'In Progress',
  terminee: 'Completed', rebutee: 'Scrapped', a_planifier: 'To Schedule',
}
const PRIORITY_COLORS = { 1: '#e74c3c', 2: '#e67e22', 3: '#f39c12', 4: '#f39c12', 5: '#27ae60' }

const PERIODS = [
  { label: '1 Day',   days: 1 },
  { label: '3 Days',  days: 3 },
  { label: '1 Week',  days: 7 },
  { label: '2 Weeks', days: 14 },
]

function formatDate(d) {
  return d.toISOString().split('T')[0]
}

function addDays(d, n) {
  const r = new Date(d)
  r.setDate(r.getDate() + n)
  return r
}

// Hours per pixel for each period
const PERIOD_PX = { 1: 80, 3: 30, 7: 14, 14: 7 }
const ROW_H = 48
const LABEL_W = 180

export default function Planning() {
  const [data, setData]           = useState(null)
  const [summary, setSummary]     = useState(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')
  const [period, setPeriod]       = useState(7)
  const [startDate, setStartDate] = useState(() => addDays(new Date(), -1))
  const [tooltip, setTooltip]     = useState(null)
  const [selectedOp, setSelectedOp] = useState(null)
  const [drag, setDrag]           = useState(null) // { op, startClientX, origX }
  const [moving, setMoving]       = useState(false)
  const [optimizing, setOptimizing] = useState(false)
  const canvasRef = useRef(null)

  const fetchPlanning = useCallback(async () => {
    setLoading(true)
    try {
      const endDate = addDays(startDate, period)
      const [planRes, sumRes] = await Promise.all([
        api.get('/planning', { params: { date_debut: formatDate(startDate), date_fin: formatDate(endDate) } }),
        api.get('/planning/summary'),
      ])
      setData(planRes.data)
      setSummary(sumRes.data)
      setError('')
    } catch { setError('Error loading planning data') }
    finally { setLoading(false) }
  }, [startDate, period])

  useEffect(() => { fetchPlanning() }, [fetchPlanning])

  const handleOptimize = async () => {
    if (!window.confirm('Re-schedule every planned operation at the earliest possible time? This may move existing tasks on the Gantt.')) return
    setOptimizing(true)
    try {
      const { data } = await api.post('/planning/recalculate-global')
      await fetchPlanning()
      alert(`Schedule optimized: ${data.nb_ops} operation${data.nb_ops > 1 ? 's' : ''} across ${data.nb_ofs} work order${data.nb_ofs > 1 ? 's' : ''}.`)
    } catch (err) {
      alert(err.response?.data?.detail || 'Error optimizing schedule')
    } finally { setOptimizing(false) }
  }

  const pxPerHour = PERIOD_PX[period] || 14
  const totalHours = period * 24
  const totalW = totalHours * pxPerHour

  // Convert date string to X position. Can be negative if the operation
  // starts before the visible window — the lane container clips it (see
  // overflow: 'hidden' below) so it doesn't get falsely collapsed to 0,
  // which used to stack unrelated operations on top of each other.
  const dateToX = (dateStr) => {
    if (!dateStr) return null
    const d = new Date(dateStr)
    const diffH = (d - startDate) / 3600000
    return diffH * pxPerHour
  }

  const durationToW = (h) => h ? h * pxPerHour : 20

  // Snap a raw pixel delta to the nearest 30-minute increment
  const snapDeltaX = (deltaPx, pxH) => {
    const stepPx = pxH / 2 // 30 min
    return Math.round(deltaPx / stepPx) * stepPx
  }

  const dragMovedRef = useRef(false)
  const dragInfoRef  = useRef(null)   // { op, startClientX } — stable across the whole drag
  const pxPerHourRef = useRef(pxPerHour)
  const fetchPlanningRef = useRef(fetchPlanning)
  pxPerHourRef.current = pxPerHour
  fetchPlanningRef.current = fetchPlanning

  const handleDragStart = (e, op) => {
    if (op.statut === 'terminee' || op.statut === 'rebutee') return
    e.preventDefault()
    console.log('[gantt drag] mousedown on op', op.id_op, 'button=', e.button)
    dragMovedRef.current = false
    setSelectedOp(op)
    dragInfoRef.current = { op, startClientX: e.clientX }
    setDrag({ op, deltaX: 0 })
  }

  // Attach the window listeners exactly once — they read the live drag info
  // via refs, so per-pixel mousemove updates never tear down/recreate them.
  useEffect(() => {
    const onMove = (e) => {
      const info = dragInfoRef.current
      if (!info) return
      const deltaX = e.clientX - info.startClientX
      if (Math.abs(deltaX) > 4 && !dragMovedRef.current) {
        console.log('[gantt drag] first move detected, deltaX=', deltaX)
      }
      if (Math.abs(deltaX) > 4) dragMovedRef.current = true
      setDrag({ op: info.op, deltaX })
    }
    const onUp = async (e) => {
      const info = dragInfoRef.current
      if (!info) return
      dragInfoRef.current = null
      const deltaX = e.clientX - info.startClientX
      const pxH = pxPerHourRef.current
      const snapped = snapDeltaX(deltaX, pxH)
      console.log('[gantt drag] mouseup', { deltaX, pxH, snapped, threshold: pxH / 2 })
      setDrag(null)
      if (Math.abs(snapped) < pxH / 2) {
        console.log('[gantt drag] ignored — below threshold')
        return
      }
      const deltaHours = snapped / pxH
      const newStart = new Date(new Date(info.op.date_debut).getTime() + deltaHours * 3600000)
      console.log('[gantt drag] sending move', { id_op: info.op.id_op, newStart: newStart.toISOString() })
      setMoving(true)
      try {
        const res = await api.put(`/planning/ops/${info.op.id_op}/move`, { new_date_debut: newStart.toISOString() })
        console.log('[gantt drag] move OK', res.data)
        await fetchPlanningRef.current()
      } catch (err) {
        console.log('[gantt drag] move FAILED', err.response?.status, err.response?.data)
        alert(err.response?.data?.detail || 'Error moving operation')
      } finally { setMoving(false) }
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [])

  // Generate hour ticks
  const ticks = []
  const tickStep = period <= 1 ? 1 : period <= 3 ? 3 : period <= 7 ? 6 : 12
  for (let h = 0; h <= totalHours; h += tickStep) {
    const d = new Date(startDate.getTime() + h * 3600000)
    ticks.push({ x: h * pxPerHour, label: d.toLocaleString('en-GB', { month: 'short', day: 'numeric', hour: '2-digit', hour12: false }) })
  }

  return (
    <Layout>
      <div className="module-header">
        <div>
          <h2>📅 Planning</h2>
          {summary && (
            <span className="module-count">
              {summary.planifiees} planned · {summary.en_cours} in progress
              {summary.unassigned > 0 && <span style={{ color: '#e74c3c' }}> · {summary.unassigned} unassigned</span>}
            </span>
          )}
        </div>
        <div className="module-actions">
          <button className="btn btn-secondary" onClick={() => setStartDate(d => addDays(d, -period))}>◀ Prev</button>
          <button className="btn btn-primary" onClick={() => setStartDate(addDays(new Date(), -1))}>Today</button>
          <button className="btn btn-secondary" onClick={() => setStartDate(d => addDays(d, period))}>Next ▶</button>
          <div style={{ display: 'flex', gap: 4 }}>
            {PERIODS.map(p => (
              <button key={p.days}
                style={{ padding: '6px 12px', fontSize: 12, border: '1px solid #dde',
                  borderRadius: 6, cursor: 'pointer',
                  background: period === p.days ? '#2c3e50' : 'white',
                  color: period === p.days ? 'white' : '#2c3e50' }}
                onClick={() => setPeriod(p.days)}>{p.label}</button>
            ))}
          </div>
          <button className="btn btn-primary" onClick={fetchPlanning}>🔄</button>
          <button className="btn btn-secondary" disabled={optimizing} onClick={handleOptimize}>
            {optimizing ? '⏳ Optimizing…' : '🧠 Optimize Schedule'}
          </button>
          {moving && <span style={{ fontSize: 12, color: '#7f8c8d' }}>Moving…</span>}
        </div>
      </div>

      {/* Summary KPIs */}
      {summary && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          {[
            { label: 'Total Ops', value: summary.total, color: '#2c3e50' },
            { label: 'Planned',   value: summary.planifiees, color: '#3498db' },
            { label: 'In Progress', value: summary.en_cours, color: '#8e44ad' },
            { label: 'Completed', value: summary.terminees, color: '#27ae60' },
            { label: 'Unassigned', value: summary.unassigned, color: '#e74c3c' },
          ].map(k => (
            <div key={k.label} style={{ background: 'white', borderRadius: 8, padding: '10px 16px',
              boxShadow: '0 1px 4px rgba(0,0,0,0.06)', minWidth: 100, textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 700, color: k.color }}>{k.value}</div>
              <div style={{ fontSize: 11, color: '#7f8c8d' }}>{k.label}</div>
            </div>
          ))}
        </div>
      )}

      {error && <div className="alert alert-error">{error}</div>}

      {/* Gantt */}
      <div className="gantt-container">
        {loading ? (
          <div className="table-loading">Loading planning...</div>
        ) : !data || data.machines.length === 0 ? (
          <div className="table-empty">No operations in this period</div>
        ) : (
          <div style={{ display: 'flex' }}>
            {/* Fixed label column — lives OUTSIDE the horizontal scroll area,
                so it never moves regardless of how far the timeline scrolls. */}
            <div style={{ flexShrink: 0, width: LABEL_W }}>
              <div style={{ height: 36, padding: '8px 12px', display: 'flex', alignItems: 'center',
                background: '#2c3e50', color: 'white', fontWeight: 700, fontSize: 13,
                borderTopLeftRadius: 10 }}>
                Machine
              </div>
              {data.machines.map((machine) => (
                <div key={machine.id_machine} style={{ padding: '0 12px',
                  background: 'white', borderRight: '1px solid #f0f2f5', borderBottom: '1px solid #f0f2f5',
                  display: 'flex', alignItems: 'center',
                  height: Math.max(ROW_H, machine.operations.length * (ROW_H + 4)) }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#2c3e50' }}>{machine.nom}</div>
                    <div style={{ fontSize: 11, color: '#95a5a6' }}>{machine.operations.length} op{machine.operations.length > 1 ? 's' : ''}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Scrollable timeline — header ticks and every machine's lane live
                together in ONE scroll container, so they always move in sync. */}
            <div style={{ overflowX: 'auto', flex: 1, minWidth: 0 }}>
              <div style={{ width: totalW, minWidth: totalW }}>
                {/* Header ticks */}
                <div style={{ position: 'relative', height: 36, background: '#2c3e50',
                  borderTopRightRadius: 10 }}>
                  {ticks.map((t, i) => (
                    <div key={i} style={{ position: 'absolute', left: t.x, top: 0,
                      fontSize: 10, color: 'rgba(255,255,255,0.8)', paddingTop: 4,
                      borderLeft: '1px solid rgba(255,255,255,0.2)', paddingLeft: 3,
                      whiteSpace: 'nowrap' }}>
                      {t.label}
                    </div>
                  ))}
                </div>

                {/* Rows */}
                {data.machines.map((machine) => (
                  <div key={machine.id_machine} style={{ position: 'relative',
                    height: Math.max(ROW_H, machine.operations.length * (ROW_H + 4)),
                    borderBottom: '1px solid #f0f2f5', background: 'white', overflow: 'hidden' }}>
                    {/* Grid lines */}
                    {ticks.map((t, i) => (
                      <div key={i} style={{ position: 'absolute', left: t.x, top: 0, bottom: 0,
                        width: 1, background: '#f0f2f5' }} />
                    ))}

                    {/* Today line */}
                    {(() => {
                      const todayX = dateToX(new Date().toISOString())
                      return todayX >= 0 && todayX <= totalW ? (
                        <div style={{ position: 'absolute', left: todayX, top: 0, bottom: 0,
                          width: 2, background: '#e74c3c', zIndex: 5, opacity: 0.7 }} />
                      ) : null
                    })()}

                    {/* Operation blocks */}
                    {machine.operations.map((op, idx) => {
                      const x = dateToX(op.date_debut)
                      const realW = durationToW(op.duree_prevue_h) // true duration, no padding
                      if (x === null) return null
                      const barW = Math.max(realW, 10) // small clickable sliver floor only
                      const showLabel = barW >= 42
                      const isDraggingThis = drag?.op.id_op === op.id_op
                      const dragOffset = isDraggingThis ? snapDeltaX(drag.deltaX || 0, pxPerHour) : 0
                      const isSelected = selectedOp?.id_op === op.id_op
                      const isSamePiece = selectedOp && !isSelected && selectedOp.id_of === op.id_of
                      const movable = op.statut !== 'terminee' && op.statut !== 'rebutee'
                      return (
                        <div key={op.id_op}
                          style={{
                            position: 'absolute',
                            left: x + dragOffset,
                            top: idx * (ROW_H + 4) + 6,
                            width: barW,
                            height: ROW_H - 12,
                            background: STATUT_COLORS[op.statut] || '#95a5a6',
                            border: '1px solid rgba(255,255,255,0.7)',
                            borderRadius: 4,
                            cursor: isDraggingThis ? 'grabbing' : movable ? 'grab' : 'pointer',
                            overflow: 'hidden',
                            boxShadow: isSelected ? '0 0 0 2px #2c3e50'
                              : isSamePiece ? '0 0 0 2px #f39c12'
                              : '0 1px 3px rgba(0,0,0,0.2)',
                            outline: isSamePiece ? '2px solid #f39c12' : 'none',
                            opacity: isDraggingThis ? 0.85 : (selectedOp && !isSelected && !isSamePiece ? 0.55 : 1),
                            transition: isDraggingThis ? 'none' : 'box-shadow 0.15s, opacity 0.15s',
                            zIndex: isDraggingThis ? 6 : 4,
                          }}
                          onMouseDown={(e) => handleDragStart(e, op)}
                          onClick={() => {
                            if (dragMovedRef.current) return // was a drag, not a click
                            setSelectedOp(sel => sel?.id_op === op.id_op ? null : op)
                          }}
                          onMouseEnter={(e) => setTooltip({ op, x: e.clientX, y: e.clientY })}
                          onMouseLeave={() => setTooltip(null)}
                        >
                          {showLabel && (
                            <>
                              <div style={{ padding: '2px 6px', color: 'white', fontSize: 11,
                                fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {op.nom_operation}
                              </div>
                              <div style={{ padding: '0 6px', color: 'rgba(255,255,255,0.85)', fontSize: 10,
                                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {op.composant_nom}
                              </div>
                            </>
                          )}
                        </div>
                      )
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div className="gantt-tooltip" style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>{tooltip.op.nom_operation}</div>
          <div>Component: {tooltip.op.composant_nom}</div>
          <div>Assembly: {tooltip.op.assembly_nom}</div>
          <div>WO: {tooltip.op.code_of || '—'}</div>
          <div>Duration: {tooltip.op.duree_prevue_h != null ? `${tooltip.op.duree_prevue_h}h` : '—'}</div>
          <div>Start: {tooltip.op.date_debut || '—'}</div>
          <div>End: {tooltip.op.date_fin || '—'}</div>
          <div style={{ marginTop: 4 }}>
            <span style={{ background: STATUT_COLORS[tooltip.op.statut], color: 'white',
              padding: '1px 8px', borderRadius: 10, fontSize: 11 }}>
              {STATUT_LABELS[tooltip.op.statut]}
            </span>
            <span style={{ marginLeft: 6, color: PRIORITY_COLORS[tooltip.op.priorite], fontWeight: 700, fontSize: 11 }}>
              P{tooltip.op.priorite}
            </span>
          </div>
        </div>
      )}

      {/* Selected op detail */}
      {selectedOp && (
        <div className="detail-card" style={{ marginTop: 16 }}>
          <h3>Operation Details — {selectedOp.nom_operation}</h3>
          <div className="detail-grid">
            <div><label>WO Code</label><span>{selectedOp.code_of || '—'}</span></div>
            <div><label>Component</label><span>{selectedOp.composant_nom}</span></div>
            <div><label>Assembly</label><span>{selectedOp.assembly_nom}</span></div>
            <div><label>Machine</label><span>{selectedOp.machine_nom || '—'}</span></div>
            <div><label>Duration</label><span>{selectedOp.duree_prevue_h != null ? `${selectedOp.duree_prevue_h}h` : '—'}</span></div>
            <div><label>Priority</label>
              <span style={{ color: PRIORITY_COLORS[selectedOp.priorite], fontWeight: 700 }}>P{selectedOp.priorite}</span>
            </div>
            <div><label>Start</label><span>{selectedOp.date_debut || '—'}</span></div>
            <div><label>End</label><span>{selectedOp.date_fin || '—'}</span></div>
            <div><label>Status</label>
              <span style={{ color: STATUT_COLORS[selectedOp.statut], fontWeight: 700 }}>
                {STATUT_LABELS[selectedOp.statut]}
              </span>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
