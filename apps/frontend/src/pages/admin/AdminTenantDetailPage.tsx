/**
 * AdminTenantDetailPage — Visão operacional de um cliente.
 * Mostra câmeras, alertas recentes, jobs de treino + badge de status do worker.
 * Polling de worker status a cada 15s.
 */
import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../../services/api'

interface TenantOverview {
  tenant: { id: string; name: string; slug: string; plan: string; schema_name: string }
  cameras: Array<{ id: string; name: string; status: string; active_module: string }>
  recent_alerts: Array<{ id: string; violation_type: string; confidence: number; created_at: string }>
  training_jobs: Array<{ id: string; name: string; status: string; module: string; created_at: string }>
}

interface WorkersStatus {
  workers: Record<string, 'onpremise' | 'railway' | 'offline'>
}

type R<T> = { status: string; data: T }

export function AdminTenantDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [overview, setOverview] = useState<TenantOverview | null>(null)
  const [workerStatus, setWorkerStatus] = useState<string>('railway')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    Promise.all([
      api.get<R<TenantOverview>>(`/v1/admin/tenants/${id}/overview`),
      api.get<R<WorkersStatus>>('/v1/admin/workers/status'),
    ])
      .then(([overviewRes, workersRes]) => {
        setOverview(overviewRes.data)
        const schema = overviewRes.data?.tenant?.schema_name
        if (schema && workersRes.data?.workers) {
          setWorkerStatus(workersRes.data.workers[schema] ?? 'railway')
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  // Polling de worker status a cada 15s
  useEffect(() => {
    if (!overview) return
    const schema = overview.tenant?.schema_name
    const interval = setInterval(() => {
      api.get<R<WorkersStatus>>('/v1/admin/workers/status')
        .then((res) => setWorkerStatus(res.data?.workers?.[schema] ?? 'railway'))
        .catch(() => {})
    }, 15000)
    return () => clearInterval(interval)
  }, [overview])

  if (loading) return <div style={{ padding: 32 }}>Carregando...</div>
  if (error) return <div style={{ padding: 32, color: 'red' }}>Erro: {error}</div>
  if (!overview) return null

  const { tenant, cameras, recent_alerts, training_jobs } = overview

  return (
    <div style={{ padding: 24, maxWidth: 1000 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <Link to="/admin/tenants" style={{ color: '#666', textDecoration: 'none' }}>← Clientes</Link>
        <h1 style={{ margin: 0 }}>{tenant.name}</h1>
        <WorkerBadge status={workerStatus as any} />
      </div>
      <p style={{ color: '#666', marginBottom: 24 }}>
        Schema: <code>{tenant.schema_name}</code> · Plano: {tenant.plan}
      </p>

      {/* Câmeras */}
      <Section title={`Câmeras (${cameras.length})`}>
        {cameras.length === 0 ? <Empty text="Nenhuma câmera cadastrada" /> : (
          <table style={{ width: '100%', fontSize: 14, borderCollapse: 'collapse' }}>
            <thead><tr style={{ background: '#f5f5f5' }}>
              <th style={th}>Nome</th><th style={th}>Status</th><th style={th}>Módulo</th>
            </tr></thead>
            <tbody>
              {cameras.map((c) => (
                <tr key={c.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={td}>{c.name}</td>
                  <td style={td}>{c.status}</td>
                  <td style={td}>{c.active_module}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      {/* Alertas recentes */}
      <Section title="Alertas Recentes (últimas 24h)">
        {recent_alerts.length === 0 ? <Empty text="Sem alertas recentes" /> : (
          <table style={{ width: '100%', fontSize: 14, borderCollapse: 'collapse' }}>
            <thead><tr style={{ background: '#f5f5f5' }}>
              <th style={th}>Violação</th><th style={th}>Confiança</th><th style={th}>Horário</th>
            </tr></thead>
            <tbody>
              {recent_alerts.map((a) => (
                <tr key={a.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={td}>{a.violation_type}</td>
                  <td style={td}>{(a.confidence * 100).toFixed(0)}%</td>
                  <td style={td}>{new Date(a.created_at).toLocaleString('pt-BR')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      {/* Treinamentos */}
      <Section title="Jobs de Treinamento">
        {training_jobs.length === 0 ? <Empty text="Nenhum job de treinamento" /> : (
          <table style={{ width: '100%', fontSize: 14, borderCollapse: 'collapse' }}>
            <thead><tr style={{ background: '#f5f5f5' }}>
              <th style={th}>Nome</th><th style={th}>Módulo</th><th style={th}>Status</th><th style={th}>Criado</th>
            </tr></thead>
            <tbody>
              {training_jobs.map((j) => (
                <tr key={j.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={td}>{j.name}</td>
                  <td style={td}>{j.module}</td>
                  <td style={td}>{j.status}</td>
                  <td style={td}>{new Date(j.created_at).toLocaleDateString('pt-BR')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      {/* Placeholders fase 2 */}
      <Section title="Dashboard Grafana">
        <div style={{ padding: 24, background: '#f9f9f9', borderRadius: 8, textAlign: 'center', color: '#999' }}>
          📊 Dashboard operacional via Grafana — disponível na Fase 2
        </div>
      </Section>
    </div>
  )
}

function WorkerBadge({ status }: { status: 'onpremise' | 'railway' | 'offline' }) {
  const config = {
    onpremise: { color: '#16a34a', bg: '#dcfce7', label: '🟢 On-Premise (GPU)' },
    railway:   { color: '#ca8a04', bg: '#fef9c3', label: '🟡 Railway (CPU)' },
    offline:   { color: '#dc2626', bg: '#fee2e2', label: '🔴 Offline' },
  }[status] ?? { color: '#666', bg: '#f5f5f5', label: '⚪ Desconhecido' }

  return (
    <span style={{ padding: '4px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600, color: config.color, background: config.bg }}>
      {config.label}
    </span>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 32 }}>
      <h2 style={{ marginBottom: 12, fontSize: 18 }}>{title}</h2>
      {children}
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <p style={{ color: '#999', fontStyle: 'italic' }}>{text}</p>
}

const th: React.CSSProperties = { padding: '8px 12px', fontWeight: 600, textAlign: 'left' }
const td: React.CSSProperties = { padding: '8px 12px' }
