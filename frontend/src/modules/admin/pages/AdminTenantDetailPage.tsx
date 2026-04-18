import { ArrowLeft, Ban, Plus, RefreshCw, ToggleLeft, ToggleRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { adminService } from '../services/adminService'
import { WorkerStatusBadge } from '../components/WorkerStatusBadge'
import { UserRoleBadge } from '../components/UserRoleBadge'
import * as s from '../components/admin.css'
import type { Tenant } from '../types/admin'

const ALL_MODULES = ['epi', 'counting', 'quality', 'basic', 'analytics', 'fueling']
const ROLES = ['admin', 'operator', 'analyst', 'trainer', 'viewer']

type Tab = 'overview' | 'users' | 'worker' | 'modules' | 'flags' | 'history'

export function AdminTenantDetailPage() {
  const { id } = useParams<{ id: string }>()
  const nav = useNavigate()
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('overview')
  const [busy, setBusy] = useState(false)

  const reload = () => {
    if (!id) return
    adminService.getTenant(id).then(setTenant).catch((e) => setError(e.message))
  }

  useEffect(() => {
    if (!id) return
    adminService.getTenant(id)
      .then((t) => setTenant(t))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  const handleSuspend = async () => {
    if (!id || !tenant) return
    const reason = prompt('Motivo da suspensão:')
    if (!reason) return
    setBusy(true)
    try {
      await adminService.suspendTenant(id, reason)
      setTenant({ ...tenant, is_active: false })
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Erro')
    } finally { setBusy(false) }
  }

  const handleReactivate = async () => {
    if (!id || !tenant) return
    setBusy(true)
    try {
      await adminService.reactivateTenant(id)
      setTenant({ ...tenant, is_active: true })
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Erro')
    } finally { setBusy(false) }
  }

  if (loading) return <div style={{ padding: 32 }}>Carregando...</div>
  if (error || !tenant) return <div style={{ padding: 32 }}><div className={s.alertBanner.danger}>{error ?? 'Tenant não encontrado'}</div></div>

  const tabs: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Visão Geral' },
    { key: 'users',    label: 'Usuários' },
    { key: 'worker',   label: 'Worker' },
    { key: 'modules',  label: 'Módulos' },
    { key: 'flags',    label: 'Feature Flags' },
    { key: 'history',  label: 'Histórico de Plano' },
  ]

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <button className={s.btnGhost} style={{ marginBottom: 8 }} onClick={() => nav('/admin/tenants')}>
            <ArrowLeft size={14} /> Tenants
          </button>
          <div className={s.pageTitle}>{tenant.name}</div>
          <div className={s.pageSubtitle}>
            <span className={s.mono}>{tenant.slug}</span>
            {' · '}
            <span className={s.planBadge[tenant.plan]}>{tenant.plan}</span>
            {' · '}
            {tenant.worker_status && <WorkerStatusBadge status={tenant.worker_status} />}
          </div>
        </div>
        <div className={s.flex}>
          {tenant.is_active
            ? <button className={s.btnDanger} disabled={busy} onClick={handleSuspend}><Ban size={14} /> Suspender</button>
            : <button className={s.btnSuccess} disabled={busy} onClick={handleReactivate}><RefreshCw size={14} /> Reativar</button>}
        </div>
      </div>

      {!tenant.is_active && <div className={s.alertBanner.danger} style={{ marginBottom: 16 }}>Tenant suspenso</div>}

      {/* Tabs */}
      <div className={s.flex} style={{ borderBottom: '1px solid var(--border-subtle)', marginBottom: 24, gap: 0 }}>
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: '8px 16px', background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 13, fontWeight: tab === t.key ? 600 : 400,
              borderBottom: tab === t.key ? '2px solid var(--color-accent, #2563eb)' : '2px solid transparent',
              color: tab === t.key ? 'var(--color-accent, #2563eb)' : 'inherit',
            }}
          >{t.label}</button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className={s.twoColumn}>
          <div className={s.card}>
            <div className={s.cardTitle}>Informações</div>
            <Row label="Schema" value={<span className={s.mono}>{tenant.schema_name}</span>} />
            <Row label="Câmeras" value={tenant.contract_cameras} />
            <Row label="Criado em" value={new Date(tenant.created_at).toLocaleDateString('pt-BR')} />
            {tenant.suspended_at && <Row label="Suspenso em" value={new Date(tenant.suspended_at).toLocaleDateString('pt-BR')} />}
            {tenant.internal_notes && <Row label="Notas internas" value={tenant.internal_notes} />}
          </div>
          <div className={s.card}>
            <div className={s.cardTitle}>Módulos habilitados</div>
            <div className={s.flex} style={{ flexWrap: 'wrap' }}>
              {(tenant.modules_enabled ?? []).map((m) => (
                <span key={m} className={s.badge} style={{ background: 'rgba(59,130,246,0.1)', color: '#2563eb' }}>{m}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === 'users' && (
        <UsersTab tenantId={id!} tenant={tenant} onReload={reload} />
      )}

      {tab === 'worker' && (
        <div className={s.card}>
          <div className={s.cardTitle}>Worker On-Premise</div>
          {tenant.worker_status
            ? <>
                <Row label="Status" value={<WorkerStatusBadge status={tenant.worker_status} />} />
                {tenant.worker_metrics && <>
                  <Row label="GPU" value={`${tenant.worker_metrics.gpu_pct.toFixed(1)}%`} />
                  <Row label="VRAM" value={`${tenant.worker_metrics.vram_used_gb.toFixed(1)} GB`} />
                  <Row label="FPS médio" value={tenant.worker_metrics.fps_avg.toFixed(1)} />
                  <Row label="Câmeras ativas" value={tenant.worker_metrics.cameras_active} />
                </>}
              </>
            : <span className={s.muted}>Nenhum worker registrado para este tenant.</span>}
        </div>
      )}

      {tab === 'modules' && (
        <ModulesTab tenantId={id!} tenant={tenant} onUpdate={(updated) => setTenant(updated)} />
      )}

      {tab === 'flags' && (
        <div className={s.card}>
          <div className={s.cardTitle}>Feature Flags do Tenant</div>
          <TenantFlagsTab tenantId={id!} />
        </div>
      )}

      {tab === 'history' && (
        <div className={s.card}>
          <div className={s.cardTitle}>Histórico de Plano</div>
          <PlanHistoryTab tenantId={id!} />
        </div>
      )}
    </div>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className={s.flex} style={{ padding: '6px 0', borderBottom: '1px solid rgba(0,0,0,.05)' }}>
      <span className={s.muted} style={{ width: 140, flexShrink: 0 }}>{label}</span>
      <span>{value}</span>
    </div>
  )
}

// ── Users Tab ─────────────────────────────────────────────────────────────────

function UsersTab({ tenantId, tenant, onReload }: { tenantId: string; tenant: Tenant; onReload: () => void }) {
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ email: '', role: 'operator' })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const handleAdd = async () => {
    setSaving(true); setErr(null)
    try {
      const res = await adminService.createUser({ email: form.email, role: form.role, tenant_id: tenantId })
      alert(`Usuário criado!\nSenha temporária: ${res.temp_password}`)
      setShowAdd(false)
      setForm({ email: '', role: 'operator' })
      onReload()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Erro ao criar usuário')
    } finally { setSaving(false) }
  }

  const handleToggleUser = async (userId: string, active: boolean) => {
    try {
      if (active) {
        await adminService.deactivateUser(userId)
      } else {
        await adminService.reactivateUser(userId)
      }
      onReload()
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Erro')
    }
  }

  return (
    <div className={s.card}>
      <div className={s.flex} style={{ marginBottom: 12 }}>
        <div className={s.cardTitle} style={{ margin: 0, flex: 1 }}>Usuários do tenant</div>
        <button className={s.btnPrimary} onClick={() => setShowAdd(true)}><Plus size={13} /> Adicionar usuário</button>
      </div>

      {showAdd && (
        <div style={{ background: 'rgba(0,0,0,.03)', borderRadius: 8, padding: 16, marginBottom: 16 }}>
          <div className={s.flex} style={{ gap: 8, flexWrap: 'wrap' }}>
            <input
              className={s.input} placeholder="email@empresa.com" style={{ flex: 1, minWidth: 200 }}
              value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            />
            <select className={s.select} value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <button className={s.btnPrimary} onClick={handleAdd} disabled={saving || !form.email}>
              {saving ? 'Criando...' : 'Criar'}
            </button>
            <button className={s.btnGhost} onClick={() => { setShowAdd(false); setErr(null) }}>Cancelar</button>
          </div>
          {err && <div className={s.alertBanner.danger} style={{ marginTop: 8 }}>{err}</div>}
        </div>
      )}

      {tenant.users && tenant.users.length > 0 ? (
        <table className={s.table}>
          <thead>
            <tr>
              <th className={s.th}>Email</th>
              <th className={s.th}>Role</th>
              <th className={s.th}>Último login</th>
              <th className={s.th}>Status</th>
              <th className={s.th}>Ações</th>
            </tr>
          </thead>
          <tbody>
            {tenant.users.map((u) => (
              <tr key={u.id} className={s.trHover}>
                <td className={s.td}>{u.email}</td>
                <td className={s.td}><UserRoleBadge role={u.role} /></td>
                <td className={s.td}><span className={s.muted}>{u.last_login_at ? new Date(u.last_login_at).toLocaleDateString('pt-BR') : '—'}</span></td>
                <td className={s.td}><span className={s.dot[u.is_active ? 'healthy' : 'critical']} /></td>
                <td className={s.td}>
                  <button
                    className={u.is_active ? s.btnDanger : s.btnSuccess}
                    style={{ padding: '2px 8px', fontSize: 12 }}
                    onClick={() => handleToggleUser(u.id, u.is_active)}
                  >
                    {u.is_active ? 'Desativar' : 'Reativar'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <span className={s.muted}>Nenhum usuário cadastrado neste tenant.</span>}
    </div>
  )
}

// ── Modules Tab ───────────────────────────────────────────────────────────────

function ModulesTab({ tenantId, tenant, onUpdate }: { tenantId: string; tenant: Tenant; onUpdate: (t: Tenant) => void }) {
  const [saving, setSaving] = useState<string | null>(null)
  const enabled = new Set(tenant.modules_enabled ?? [])

  const toggleModule = async (mod: string) => {
    setSaving(mod)
    const next = enabled.has(mod)
      ? (tenant.modules_enabled ?? []).filter((m) => m !== mod)
      : [...(tenant.modules_enabled ?? []), mod]
    try {
      await adminService.updateTenant(tenantId, { modules_enabled: next })
      onUpdate({ ...tenant, modules_enabled: next })
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Erro ao atualizar módulos')
    } finally { setSaving(null) }
  }

  return (
    <div className={s.card}>
      <div className={s.cardTitle}>Módulos disponíveis</div>
      <div className={s.muted} style={{ marginBottom: 16, fontSize: 12 }}>
        Ative ou desative módulos para este tenant. Mudanças entram em vigor imediatamente.
      </div>
      {ALL_MODULES.map((mod) => {
        const active = enabled.has(mod)
        return (
          <div key={mod} className={s.flex} style={{ padding: '10px 0', borderBottom: '1px solid rgba(0,0,0,.05)' }}>
            <span style={{ flex: 1, fontWeight: active ? 600 : 400 }}>{mod}</span>
            <span className={s.muted} style={{ marginRight: 12, fontSize: 12 }}>{active ? 'Ativo' : 'Inativo'}</span>
            <button
              onClick={() => toggleModule(mod)}
              disabled={saving === mod}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: active ? '#2563eb' : '#9ca3af', padding: 0 }}
            >
              {active
                ? <ToggleRight size={24} />
                : <ToggleLeft size={24} />}
            </button>
          </div>
        )
      })}
    </div>
  )
}

// ── Feature Flags Tab ─────────────────────────────────────────────────────────

function TenantFlagsTab({ tenantId }: { tenantId: string }) {
  const [flags, setFlags] = useState<Record<string, boolean> | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    adminService.getTenantFeatureFlags(tenantId)
      .then(setFlags)
      .catch((e) => setErr(e instanceof Error ? e.message : 'Erro ao carregar flags'))
  }, [tenantId])

  if (err) return <div className={s.alertBanner.danger}>{err}</div>
  if (!flags) return <span className={s.muted}>Carregando...</span>
  return (
    <>
      {Object.entries(flags).map(([key, val]) => (
        <div key={key} className={s.flex} style={{ padding: '6px 0', borderBottom: '1px solid rgba(0,0,0,.05)' }}>
          <span className={s.mono} style={{ flex: 1 }}>{key}</span>
          <input type="checkbox" checked={val} onChange={(e) => {
            adminService.updateTenantFeatureFlag(tenantId, key, e.target.checked)
              .then(() => setFlags((f) => f ? { ...f, [key]: e.target.checked } : f))
              .catch(() => {})
          }} />
        </div>
      ))}
      {Object.keys(flags).length === 0 && <span className={s.muted}>Nenhuma flag configurada para este tenant.</span>}
    </>
  )
}

// ── Plan History Tab ──────────────────────────────────────────────────────────

function PlanHistoryTab({ tenantId }: { tenantId: string }) {
  const [history, setHistory] = useState<unknown[] | null>(null)
  useEffect(() => {
    adminService.getTenantPlanHistory(tenantId).then(setHistory).catch(() => {})
  }, [tenantId])
  if (!history) return <span className={s.muted}>Carregando...</span>
  if (history.length === 0) return <span className={s.muted}>Nenhuma mudança de plano registrada.</span>
  return (
    <table className={s.table}>
      <thead><tr><th className={s.th}>Data</th><th className={s.th}>De</th><th className={s.th}>Para</th><th className={s.th}>Por</th></tr></thead>
      <tbody>
        {(history as Record<string, string>[]).map((h, i) => (
          <tr key={i}>
            <td className={s.td}><span className={s.mono}>{h.created_at ? new Date(h.created_at).toLocaleDateString('pt-BR') : '—'}</span></td>
            <td className={s.td}>{h.old_plan ?? '—'}</td>
            <td className={s.td}>{h.new_plan ?? '—'}</td>
            <td className={s.td}><span className={s.muted}>{h.changed_by_email ?? '—'}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
