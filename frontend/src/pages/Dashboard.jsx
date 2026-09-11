import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import api from '../api/client'
import './Dashboard.css'

const STATUT_COLORS = {
  en_cours:    '#8e44ad',
  planifie:    '#3498db',
  a_planifier: '#e67e22',
  termine:     '#27ae60',
  terminee:    '#27ae60',
  annule:      '#95a5a6',
}

export default function Dashboard() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  const fetchDashboard = useCallback(async () => {
    try {
      const { data: d } = await api.get('/dashboard')
      setData(d)
      setError('')
    } catch (err) {
      if (err.response?.status !== 401) {
        setError('Erreur lors du chargement des données')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDashboard()
    const interval = setInterval(fetchDashboard, 60000)
    return () => clearInterval(interval)
  }, [fetchDashboard])

  if (loading) return (
    <Layout>
      <div className="dashboard-loading">
        <div className="spinner" />
        <p>Chargement du dashboard...</p>
      </div>
    </Layout>
  )

  return (
    <Layout>
      <div className="dashboard-title-row">
        <h2>Dashboard</h2>
        {data && <span className="last-update">Mis à jour : {data.updated_at}</span>}
      </div>

      {error && <div className="dashboard-error">{error}</div>}

      {data && <>
        {/* KPIs */}
        <div className="kpi-grid">
          <KpiCard label="Commandes en production" value={data.kpis.commandes_en_production} color="#3498db" />
          <KpiCard label="OFs à planifier"         value={data.kpis.ofs_a_planifier}         color="#e67e22" />
          <KpiCard label="OFs en cours"            value={data.kpis.ofs_en_cours}            color="#8e44ad" />
          <KpiCard label="Rebuts ce mois"          value={data.kpis.rebuts_ce_mois}          color="#e74c3c" />
          <KpiCard label="Machines disponibles"    value={data.kpis.machines_disponibles}    color="#27ae60" />
          <KpiCard label="Machines à l'arrêt"      value={data.kpis.machines_arret}          color="#e74c3c" />
        </div>

        {/* Deux colonnes */}
        <div className="dashboard-cols">
          <div className="dashboard-card">
            <h3>🔴 OFs urgents (priorité 1-2)</h3>
            {data.ofs_urgents.length === 0
              ? <p className="empty">Aucun OF urgent</p>
              : (
                <table className="dash-table">
                  <thead>
                    <tr><th>Assemblage</th><th>Qté</th><th>Priorité</th><th>Statut</th></tr>
                  </thead>
                  <tbody>
                    {data.ofs_urgents.map((of) => (
                      <tr key={of.id_of_assemblage}>
                        <td>{of.assemblage_nom}</td>
                        <td>{of.quantite}</td>
                        <td style={{ color: '#e74c3c', fontWeight: 700 }}>{of.priorite}</td>
                        <td>
                          <span className="statut-badge" style={{ background: STATUT_COLORS[of.statut] || '#3498db' }}>
                            {of.statut_label}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            }
          </div>

          <div className="dashboard-card">
            <h3>⚠️ Événements machines</h3>
            {data.arrets_machines.length === 0
              ? <p className="empty">Aucun arrêt machine</p>
              : (
                <table className="dash-table">
                  <thead>
                    <tr><th>Machine</th><th>Type</th><th>Depuis</th><th>Durée (h)</th></tr>
                  </thead>
                  <tbody>
                    {data.arrets_machines.map((a) => (
                      <tr key={a.id_arret}>
                        <td>{a.machine_nom}</td>
                        <td>{a.type_arret}</td>
                        <td>{a.depuis}</td>
                        <td style={{ color: '#e74c3c', fontWeight: 700 }}>{a.duree_h}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            }
          </div>
        </div>

        {/* OFs en retard */}
        <div className="dashboard-card">
          <h3>⏰ OFs en retard</h3>
          {data.ofs_retard.length === 0
            ? <p className="empty">Aucun OF en retard ✅</p>
            : (
              <table className="dash-table">
                <thead>
                  <tr><th>Code OF</th><th>Composant</th><th>Qté</th><th>Date prévue</th><th>Statut</th></tr>
                </thead>
                <tbody>
                  {data.ofs_retard.map((of) => (
                    <tr key={of.id_of}>
                      <td>{of.code_of || '—'}</td>
                      <td>{of.composant_nom}</td>
                      <td>{of.quantite}</td>
                      <td style={{ color: '#e74c3c' }}>{of.date_fin_prevue}</td>
                      <td>
                        <span className="statut-badge" style={{ background: STATUT_COLORS[of.statut] || '#3498db' }}>
                          {of.statut_label}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          }
        </div>
      </>}
    </Layout>
  )
}

function KpiCard({ label, value, color }) {
  return (
    <div className="kpi-card" style={{ background: color }}>
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  )
}
