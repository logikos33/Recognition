import { Building2, Camera, AlertTriangle, Brain, Ticket, DollarSign, Server, Users } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAdminDashboard } from '../hooks/useAdminDashboard'
import { MetricCard } from '../components/MetricCard'
import { WorkerStatusBadge } from '../components/WorkerStatusBadge'
import * as s from '../components/admin.css'

export function AdminDashboard() {
  const { data, loading, error } = useAdminDashboard()
  const nav = useNavigate()

  if (loading) return <div style={{ padding: 32 }}>Carregando...</div>
  if (error) return <div style={{ padding: 32 }}><div className={s.alertBanner.danger}>{error}</div></div>
  if (!data) return null

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Dashboard Admin</div>
          <div className={s.pageSubtitle}>Visão geral da plataforma Logikos</div>
        </div>
      </div>

      {/* Métricas principais */}
      <div className={s.metricsGrid}>
        <MetricCard icon={<Building2 size={20} />} value={data.tenants_active}             label="Tenants ativos" />
        <MetricCard icon={<Users size={20} />}     value={data.users_total}                label="Usuários total" />
        <MetricCard icon={<Camera size={20} />}    value={data.cameras_online}             label="Câmeras online" />
        <MetricCard icon={<AlertTriangle size={20} />} value={data.alerts_24h}             label="Alertas 24h" />
        <MetricCard icon={<Brain size={20} />}     value={data.training_approvals_pending} label="Aprovações pendentes" deltaType={data.training_approvals_pending > 0 ? 'negative' : 'neutral'} />
        <MetricCard icon={<Ticket size={20} />}    value={data.tickets_open}               label="Tickets abertos" />
        <MetricCard icon={<DollarSign size={20} />} value={`R$ ${data.mrr_estimated.toLocaleString('pt-BR')}`} label="MRR estimado" deltaType="positive" />
      </div>

      <div className={s.twoColumn}>
        {/* Workers */}
        <div className={s.card}>
          <div className={s.cardTitle}>Workers</div>
          <div className={s.flex} style={{ gap: 24 }}>
            <div>
              <div className={s.metricValue}>{data.workers.online}</div>
              <WorkerStatusBadge status="onpremise" />
            </div>
            <div>
              <div className={s.metricValue}>{data.workers.fallback}</div>
              <WorkerStatusBadge status="railway" />
            </div>
            <div>
              <div className={s.metricValue}>{data.workers.offline}</div>
              <WorkerStatusBadge status="offline" />
            </div>
          </div>
          <button className={s.btnGhost} style={{ marginTop: 12, width: '100%' }} onClick={() => nav('/admin/workers')}>
            <Server size={14} /> Ver workers
          </button>
        </div>

        {/* Top tenants */}
        <div className={s.card}>
          <div className={s.cardTitle}>Top tenants por usuários</div>
          <table className={s.table}>
            <tbody>
              {data.top_tenants_users.map((t) => (
                <tr key={t.tenant_name}>
                  <td className={s.td}>{t.tenant_name}</td>
                  <td className={s.td} style={{ textAlign: 'right' }}><strong>{t.user_count}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Eventos críticos recentes */}
      {data.recent_critical_events.length > 0 && (
        <div className={s.card} style={{ marginTop: 24 }}>
          <div className={s.cardTitle}>Eventos críticos recentes</div>
          <table className={s.table}>
            <thead>
              <tr>
                <th className={s.th}>Quando</th>
                <th className={s.th}>Ator</th>
                <th className={s.th}>Ação</th>
                <th className={s.th}>Tenant</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_critical_events.map((e) => (
                <tr key={e.id}>
                  <td className={s.td}><span className={s.mono}>{new Date(e.created_at).toLocaleString('pt-BR')}</span></td>
                  <td className={s.td}>{e.actor_email ?? e.actor_role}</td>
                  <td className={s.td}><span className={s.mono}>{e.action}</span></td>
                  <td className={s.td}>{e.tenant_name ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
