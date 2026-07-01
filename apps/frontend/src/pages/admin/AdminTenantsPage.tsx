/**
 * AdminTenantsPage — CRUD de clientes (tenants).
 * Criar / editar / ativar / desativar tenants.
 * Acessível apenas para superadmin.
 */
import { useEffect, useState } from 'react'
import { api } from '../../services/api'

interface Tenant {
  id: string
  slug: string
  name: string
  plan: string
  schema_name: string
  is_active: boolean
  modules_enabled: string[]
}

type R<T> = { status: string; data: T }

const ALL_MODULES = ['epi', 'counting', 'quality', 'basic', 'analytics']
const PLANS = ['standard', 'professional', 'internal']

export function AdminTenantsPage() {
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    name: '', slug: '', plan: 'standard', modules_enabled: ['epi', 'counting', 'basic'],
  })
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    api.get<R<{ tenants: Tenant[] }>>('/v1/admin/tenants')
      .then((res) => setTenants(res.data?.tenants ?? []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleCreate = async () => {
    setSaving(true)
    setError(null)
    try {
      await api.post('/v1/admin/tenants', form)
      setShowModal(false)
      setForm({ name: '', slug: '', plan: 'standard', modules_enabled: ['epi', 'counting', 'basic'] })
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro')
    } finally {
      setSaving(false)
    }
  }

  const toggleActive = async (t: Tenant) => {
    try {
      await api.patch(`/v1/admin/tenants/${t.id}`, { active: !t.is_active })
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro')
    }
  }

  const toggleModule = (mod: string) => {
    setForm((f) => ({
      ...f,
      modules_enabled: f.modules_enabled.includes(mod)
        ? f.modules_enabled.filter((m) => m !== mod)
        : [...f.modules_enabled, mod],
    }))
  }

  return (
    <div style={{ padding: 24, maxWidth: 900 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1>Gerenciar Clientes</h1>
        <button
          onClick={() => setShowModal(true)}
          style={{ padding: '8px 16px', background: '#0070f3', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}
        >
          + Novo Cliente
        </button>
      </div>

      {error && <div style={{ background: '#fff3f3', border: '1px solid #f00', borderRadius: 6, padding: 12, marginBottom: 16, color: 'red' }}>{error}</div>}
      {loading && <p>Carregando...</p>}

      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
        <thead>
          <tr style={{ background: '#f5f5f5', textAlign: 'left' }}>
            <th style={th}>Nome</th>
            <th style={th}>Slug</th>
            <th style={th}>Schema</th>
            <th style={th}>Plano</th>
            <th style={th}>Módulos</th>
            <th style={th}>Status</th>
            <th style={th}>Ações</th>
          </tr>
        </thead>
        <tbody>
          {tenants.map((t) => (
            <tr key={t.id} style={{ borderBottom: '1px solid #eee' }}>
              <td style={td}>{t.name}</td>
              <td style={td}><code>{t.slug}</code></td>
              <td style={td}><code>{t.schema_name}</code></td>
              <td style={td}>{t.plan}</td>
              <td style={td} title={(t.modules_enabled ?? []).join(', ')}>
                {(t.modules_enabled ?? []).slice(0, 3).join(', ')}
                {(t.modules_enabled ?? []).length > 3 && ' ...'}
              </td>
              <td style={td}>
                <span style={{ color: t.is_active ? 'green' : 'gray' }}>
                  {t.is_active ? '● Ativo' : '○ Inativo'}
                </span>
              </td>
              <td style={td}>
                <button onClick={() => toggleActive(t)} style={btnSmall}>
                  {t.is_active ? 'Desativar' : 'Ativar'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Modal de criação */}
      {showModal && (
        <div style={modalOverlay}>
          <div style={modalBox}>
            <h2 style={{ marginBottom: 16 }}>Novo Cliente</h2>

            <label style={labelStyle}>Nome da empresa</label>
            <input style={inputStyle} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />

            <label style={labelStyle}>Slug (identificador único)</label>
            <input style={inputStyle} value={form.slug} placeholder="ex: empresa-abc" onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-') }))} />

            <label style={labelStyle}>Plano</label>
            <select style={inputStyle} value={form.plan} onChange={(e) => setForm((f) => ({ ...f, plan: e.target.value }))}>
              {PLANS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>

            <label style={labelStyle}>Módulos habilitados</label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
              {ALL_MODULES.map((mod) => (
                <label key={mod} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
                  <input type="checkbox" checked={form.modules_enabled.includes(mod)} onChange={() => toggleModule(mod)} />
                  {mod}
                </label>
              ))}
            </div>

            {error && <div style={{ color: 'red', marginBottom: 8 }}>{error}</div>}

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowModal(false)} style={btnCancel}>Cancelar</button>
              <button onClick={handleCreate} disabled={saving || !form.name || !form.slug} style={btnPrimary}>
                {saving ? 'Criando...' : 'Criar Cliente'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const th: React.CSSProperties = { padding: '8px 12px', fontWeight: 600 }
const td: React.CSSProperties = { padding: '8px 12px' }
const btnSmall: React.CSSProperties = { padding: '4px 10px', fontSize: 12, cursor: 'pointer', border: '1px solid #ccc', borderRadius: 4, background: '#fff' }
const modalOverlay: React.CSSProperties = { position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }
const modalBox: React.CSSProperties = { background: '#fff', borderRadius: 12, padding: 32, minWidth: 440, maxWidth: 560 }
const labelStyle: React.CSSProperties = { display: 'block', fontWeight: 600, marginBottom: 4, fontSize: 13 }
const inputStyle: React.CSSProperties = { width: '100%', padding: '8px 10px', border: '1px solid #ccc', borderRadius: 6, marginBottom: 12, fontSize: 14, boxSizing: 'border-box' }
const btnPrimary: React.CSSProperties = { padding: '8px 20px', background: '#0070f3', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
const btnCancel: React.CSSProperties = { padding: '8px 20px', background: '#f5f5f5', border: '1px solid #ccc', borderRadius: 6, cursor: 'pointer' }
