/**
 * AdminDashboard — Painel global Logikos (superadmin only).
 * Cards: total tenants, câmeras online, alertas 24h, jobs em andamento.
 * Tabela de tenants com status, plano, módulos.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../services/api'

interface TenantRow {
  id: string
  slug: string
  name: string
  plan: string
  schema_name: string
  is_active: boolean
  modules_enabled: string[]
  user_count: number
}

interface DashboardData {
  tenants_total: number
  tenants_active: number
  users_total: number
  tenants: TenantRow[]
}

type R<T> = { status: string; data: T }

export function AdminDashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.get<R<DashboardData>>('/v1/admin/dashboard')
      .then((res) => setData(res.data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ padding: 32 }}>Carregando painel admin...</div>
  if (error) return <div style={{ padding: 32, color: 'red' }}>Erro: {error}</div>
  if (!data) return null

  return (
    <div style={{ padding: 24, maxWidth: 1100 }}>
      <h1 style={{ marginBottom: 24 }}>Painel Logikos — Admin</h1>

      {/* Cards de resumo */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 32, flexWrap: 'wrap' }}>
        <StatCard label="Clientes Ativos" value={data.tenants_active} />
        <StatCard label="Clientes Total" value={data.tenants_total} />
        <StatCard label="Usuários" value={data.users_total} />
      </div>

      {/* Tabela de tenants */}
      <h2 style={{ marginBottom: 12 }}>Clientes</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
        <thead>
          <tr style={{ background: '#f5f5f5', textAlign: 'left' }}>
            <th style={th}>Cliente</th>
            <th style={th}>Slug</th>
            <th style={th}>Plano</th>
            <th style={th}>Módulos</th>
            <th style={th}>Usuários</th>
            <th style={th}>Status</th>
            <th style={th}>Ações</th>
          </tr>
        </thead>
        <tbody>
          {data.tenants.map((t) => (
            <tr key={t.id} style={{ borderBottom: '1px solid #eee' }}>
              <td style={td}>{t.name}</td>
              <td style={td}><code>{t.slug}</code></td>
              <td style={td}>{t.plan}</td>
              <td style={td}>{(t.modules_enabled ?? []).join(', ')}</td>
              <td style={td}>{t.user_count}</td>
              <td style={td}>
                <span style={{ color: t.is_active ? 'green' : 'gray' }}>
                  {t.is_active ? '● Ativo' : '○ Inativo'}
                </span>
              </td>
              <td style={td}>
                <Link to={`/admin/tenant/${t.id}`} style={{ color: '#0070f3' }}>
                  Ver
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div style={{
      background: '#fff', border: '1px solid #eee', borderRadius: 8,
      padding: '16px 24px', minWidth: 140, boxShadow: '0 1px 4px rgba(0,0,0,.06)',
    }}>
      <div style={{ fontSize: 28, fontWeight: 700 }}>{value}</div>
      <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>{label}</div>
    </div>
  )
}

const th: React.CSSProperties = { padding: '8px 12px', fontWeight: 600 }
const td: React.CSSProperties = { padding: '8px 12px' }
