import { vars } from '../../../styles/theme.css'
import { Plus, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminService } from '../services/adminService'
import { WorkerStatusBadge } from '../components/WorkerStatusBadge'
import * as s from '../components/admin.css'
import type { Tenant } from '../types/admin'

const ALL_MODULES = ['epi', 'counting', 'quality', 'basic', 'analytics']
const PLANS = ['basic', 'standard', 'premium', 'enterprise']

export function AdminTenantsPage() {
  const nav = useNavigate()
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({ name: '', slug: '', plan: 'standard', modules_enabled: ['epi', 'basic'] })

  const load = () => {
    setLoading(true)
    adminService.getTenants()
      .then(setTenants)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleCreate = async () => {
    setSaving(true); setError(null)
    try {
      const res = await adminService.createTenant({ name: form.name, slug: form.slug, plan: form.plan as Tenant['plan'], modules_enabled: form.modules_enabled } as Parameters<typeof adminService.createTenant>[0])
      alert(`Tenant criado!\nAdmin: ${res.admin_email}\nSenha temporária: ${res.temp_password}`)
      setShowModal(false)
      setForm({ name: '', slug: '', plan: 'standard', modules_enabled: ['epi', 'basic'] })
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao criar tenant')
    } finally { setSaving(false) }
  }

  const toggleModule = (mod: string) =>
    setForm((f) => ({
      ...f,
      modules_enabled: f.modules_enabled.includes(mod)
        ? f.modules_enabled.filter((m) => m !== mod)
        : [...f.modules_enabled, mod],
    }))

  const filtered = tenants.filter((t) =>
    !search || t.name.toLowerCase().includes(search.toLowerCase()) || t.slug.includes(search)
  )

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Tenants</div>
          <div className={s.pageSubtitle}>{tenants.length} clientes cadastrados</div>
        </div>
        <button className={s.btnPrimary} onClick={() => setShowModal(true)}><Plus size={14} /> Novo Tenant</button>
      </div>

      {error && <div className={s.alertBanner.danger}>{error}</div>}

      <div className={s.card} style={{ marginBottom: 16 }}>
        <div className={s.flex}>
          <Search size={15} />
          <input className={s.input} style={{ flex: 1 }} placeholder="Buscar por nome ou slug..." value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>

      <div className={s.card}>
        {loading ? <div className={s.muted}>Carregando...</div> : (
          <table className={s.table}>
            <thead>
              <tr>
                <th className={s.th}>Nome</th>
                <th className={s.th}>Slug</th>
                <th className={s.th}>Plano</th>
                <th className={s.th}>Módulos</th>
                <th className={s.th}>Worker</th>
                <th className={s.th}>Usuários</th>
                <th className={s.th}>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr key={t.id} className={s.trHover} onClick={() => nav(`/admin/tenants/${t.id}`)}>
                  <td className={s.td}><strong>{t.name}</strong></td>
                  <td className={s.td}><span className={s.mono}>{t.slug}</span></td>
                  <td className={s.td}><span className={s.planBadge[t.plan]}>{t.plan}</span></td>
                  <td className={s.td}><span className={s.muted}>{(t.modules_enabled ?? []).join(', ')}</span></td>
                  <td className={s.td}>{t.worker_status ? <WorkerStatusBadge status={t.worker_status} /> : <span className={s.muted}>—</span>}</td>
                  <td className={s.td}>{t.user_count ?? '—'}</td>
                  <td className={s.td}>
                    <span className={s.dot[t.is_active ? 'healthy' : 'critical']} style={{ marginRight: 6 }} />
                    {t.is_active ? 'Ativo' : 'Suspenso'}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={7} className={s.td} style={{ textAlign: 'center' }}><span className={s.muted}>Nenhum tenant encontrado</span></td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: vars.color.overlay /* TODO-WS1: converter para Modal do kit */, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className={s.card} style={{ width: 480, maxHeight: '90vh', overflowY: 'auto' }}>
            <div className={s.pageTitle} style={{ marginBottom: 16 }}>Novo Tenant</div>

            <div style={{ marginBottom: 12 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Nome da empresa</div>
              <input className={s.input} style={{ width: '100%', boxSizing: 'border-box' }} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
            </div>
            <div style={{ marginBottom: 12 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Slug (ex: empresa-abc)</div>
              <input className={s.input} style={{ width: '100%', boxSizing: 'border-box' }} value={form.slug} onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-') }))} />
            </div>
            <div style={{ marginBottom: 12 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Plano</div>
              <select className={s.select} style={{ width: '100%', boxSizing: 'border-box' }} value={form.plan} onChange={(e) => setForm((f) => ({ ...f, plan: e.target.value }))}>
                {PLANS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div style={{ marginBottom: 16 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Módulos habilitados</div>
              <div className={s.flex} style={{ flexWrap: 'wrap' }}>
                {ALL_MODULES.map((mod) => (
                  <label key={mod} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', fontSize: 13 }}>
                    <input type="checkbox" checked={form.modules_enabled.includes(mod)} onChange={() => toggleModule(mod)} />
                    {mod}
                  </label>
                ))}
              </div>
            </div>

            {error && <div className={s.alertBanner.danger}>{error}</div>}

            <div className={s.flex} style={{ justifyContent: 'flex-end' }}>
              <button className={s.btnGhost} onClick={() => setShowModal(false)}>Cancelar</button>
              <button className={s.btnPrimary} onClick={handleCreate} disabled={saving || !form.name || !form.slug}>
                {saving ? 'Criando...' : 'Criar Tenant'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
