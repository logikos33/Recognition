/**
 * EpiDashboard — KPI row + 4-quadrant monitoring layout.
 */
import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import { KPIRow } from '../../components/dashboard/KPIRow'
import { CameraGrid } from '../../components/camera-grid/CameraGrid'
import { api } from '../../services/api'
import {
  container,
  cameraSection,
  quadrantGrid,
  quadrant,
  quadrantTitle,
  alertRow,
  alertRowCamera,
  alertRowViolation,
  alertRowTime,
  viewAllLink,
  eventTable,
  eventTh,
  eventTd,
  chartWrap,
  emptyQuadrant,
} from './EpiDashboard.css'

/* ── Types ──────────────────────────────────────────────────────── */

interface Violation {
  class: string
  confidence: number
}

interface Alert {
  id: string
  camera_id: string
  camera_name?: string
  violations: Violation[]
  acknowledged: boolean
  created_at: string
}

interface AlertsApiResponse {
  alerts: Alert[]
  total: number
  page: number
  pages: number
}

/* ── Constants ──────────────────────────────────────────────────── */

const VIOLATION_LABELS: Record<string, string> = {
  no_helmet: 'Sem capacete',
  no_vest: 'Sem colete',
  no_gloves: 'Sem luvas',
  no_safety_glasses: 'Sem óculos',
  no_glasses: 'Sem óculos',
}

const CHART_COLORS = ['#06b6d4', '#f97316', '#a855f7', '#10b981', '#f59e0b']

/* ── Helpers ────────────────────────────────────────────────────── */

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'agora'
  if (mins < 60) return `há ${mins}min`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `há ${hrs}h`
  return `há ${Math.floor(hrs / 24)}d`
}

function violationLabel(v: Violation): string {
  return VIOLATION_LABELS[v.class] ?? v.class
}

/* ── Component ──────────────────────────────────────────────────── */

export function EpiDashboard() {
  const { data: queryData } = useQuery({
    queryKey: ['dashboard-alerts'],
    queryFn: () =>
      api.get<{ data?: AlertsApiResponse }>('/alerts?per_page=50&page=1'),
    staleTime: 30000,
    refetchInterval: 60000,
  })

  const raw = queryData?.data ?? (queryData as unknown as AlertsApiResponse)
  const alerts: Alert[] = raw?.alerts ?? []

  /* Q4 — aggregate by violation label */
  const violationCounts = alerts.reduce<Record<string, number>>((acc, alert) => {
    alert.violations.forEach(v => {
      const label = violationLabel(v)
      acc[label] = (acc[label] ?? 0) + 1
    })
    return acc
  }, {})
  const pieData = Object.entries(violationCounts).map(([name, value]) => ({
    name,
    value,
  }))

  const recentAlerts = alerts.slice(0, 5)
  const eventAlerts = alerts.slice(0, 8)

  return (
    <div className={container}>
      <KPIRow />

      <div className={quadrantGrid}>
        {/* Q1: Camera Grid */}
        <div className={cameraSection}>
          <CameraGrid module="epi" />
        </div>

        {/* Q2: Latest Alerts */}
        <div className={quadrant}>
          <div className={quadrantTitle}>Últimos Alertas</div>

          {recentAlerts.length === 0 ? (
            <div className={emptyQuadrant}>Nenhum alerta recente</div>
          ) : (
            recentAlerts.map(alert => (
              <div key={alert.id} className={alertRow}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className={alertRowCamera}>
                    {alert.camera_name ?? alert.camera_id}
                  </div>
                  <div className={alertRowViolation}>
                    {alert.violations.map(violationLabel).join(', ') || '—'}
                  </div>
                </div>
                <div className={alertRowTime}>{timeAgo(alert.created_at)}</div>
              </div>
            ))
          )}

          <NavLink to="/epi/alerts" className={viewAllLink}>
            Ver todos →
          </NavLink>
        </div>

        {/* Q3: Event Log */}
        <div className={quadrant}>
          <div className={quadrantTitle}>Registro de Eventos</div>

          {eventAlerts.length === 0 ? (
            <div className={emptyQuadrant}>Nenhum evento registrado</div>
          ) : (
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
              <table className={eventTable}>
                <thead>
                  <tr>
                    <th className={eventTh}>Câmera</th>
                    <th className={eventTh}>Violação</th>
                    <th className={eventTh}>Confiança</th>
                    <th className={eventTh}>Horário</th>
                  </tr>
                </thead>
                <tbody>
                  {eventAlerts.map(alert => {
                    const firstViolation = alert.violations[0]
                    const muted = alert.acknowledged
                    return (
                      <tr
                        key={alert.id}
                        style={{ opacity: muted ? 0.5 : 1 }}
                      >
                        <td className={eventTd}>
                          {alert.camera_name ?? alert.camera_id}
                        </td>
                        <td className={eventTd}>
                          {firstViolation
                            ? violationLabel(firstViolation)
                            : '—'}
                        </td>
                        <td className={eventTd}>
                          {firstViolation
                            ? `${Math.round(firstViolation.confidence * 100)}%`
                            : '—'}
                        </td>
                        <td className={eventTd}>
                          {timeAgo(alert.created_at)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          <NavLink to="/epi/alerts" className={viewAllLink}>
            Ver histórico completo →
          </NavLink>
        </div>

        {/* Q4: Statistics */}
        <div className={quadrant}>
          <div className={quadrantTitle}>Distribuição de Violações</div>

          {pieData.length === 0 ? (
            <div className={emptyQuadrant}>Sem dados no período</div>
          ) : (
            <div className={chartWrap}>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    dataKey="value"
                    paddingAngle={2}
                  >
                    {pieData.map((_entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={CHART_COLORS[index % CHART_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => [value ?? 0, 'ocorrências']}
                  />
                </PieChart>
              </ResponsiveContainer>

              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                  marginTop: '8px',
                }}
              >
                {pieData.map((entry, index) => (
                  <div
                    key={entry.name}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      fontSize: '12px',
                    }}
                  >
                    <span
                      style={{
                        width: '10px',
                        height: '10px',
                        borderRadius: '50%',
                        background: CHART_COLORS[index % CHART_COLORS.length],
                        flexShrink: 0,
                      }}
                    />
                    <span style={{ flex: 1 }}>{entry.name}</span>
                    <span style={{ fontWeight: 600 }}>{entry.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default EpiDashboard
