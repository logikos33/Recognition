import { ArrowLeft, Ban, Eye, HelpCircle, Plus, RefreshCw, ToggleLeft, ToggleRight } from 'lucide-react'
import { Skeleton } from '../../../components/ui/Skeleton/Skeleton'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { adminService } from '../services/adminService'
import { WorkerStatusBadge } from '../components/WorkerStatusBadge'
import { UserRoleBadge } from '../components/UserRoleBadge'
import { UserPermissionsDrawer, type DrawerUser } from '../components/UserPermissionsDrawer'
import { IntegrationsPanel } from '../components/IntegrationsPanel'
import { Badge } from '../../../components/ui/Badge/Badge'
import { ConfirmDialog } from '../../../components/ui/ConfirmDialog/ConfirmDialog'
import { Tooltip } from '../../../components/ui/Tooltip/Tooltip'
import { useToast } from '../../../components/ui/Toast/useToast'
import { startImpersonation } from '../../../services/impersonation'
import * as s from '../components/admin.css'
import type { AdminUser, ModuleCatalogEntry, Tenant } from '../types/admin'
import { vars } from '../../../styles/theme.css'

// Fallback local caso o catálogo dinâmico falhe (fonte única: backend)
const FALLBACK_MODULES: ModuleCatalogEntry[] = [
  'epi', 'counting', 'quality', 'basic', 'analytics', 'fueling',
].map((code) => ({ code, label: code, description: '', status: 'active' as const }))
const ROLES = ['admin', 'operator', 'analyst', 'trainer', 'viewer']
const RETENTION_TIERS = [1, 7, 30, 90]

type Tab = 'overview' | 'users' | 'worker' | 'modules' | 'config' | 'integrations' | 'flags' | 'history'

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

  if (loading) return (
    <div style={{ padding: 32, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Skeleton variant="title" width={260} />
      <div style={{ display: 'flex', gap: 8 }}>
        {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} variant="rect" width={90} height={32} />)}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} variant="text" width={`${60 + i * 5}%`} />)}
      </div>
    </div>
  )
  if (error || !tenant) return <div style={{ padding: 32 }}><div className={s.alertBanner.danger}>{error ?? 'Tenant não encontrado'}</div></div>

  const tabs: { key: Tab; label: string }[] = [
    { key: 'overview',     label: 'Visão Geral' },
    { key: 'users',        label: 'Usuários' },
    { key: 'worker',       label: 'Worker' },
    { key: 'modules',      label: 'Módulos' },
    { key: 'config',       label: 'Configurações' },
    { key: 'integrations', label: 'Armazenamento & Integrações' },
    { key: 'flags',        label: 'Feature Flags' },
    { key: 'history',      label: 'Histórico de Plano' },
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
              borderBottom: tab === t.key ? `2px solid ${vars.color.primary}` : '2px solid transparent',
              color: tab === t.key ? vars.color.primary : 'inherit',
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
                <span key={m} className={s.badge} style={{ background: 'rgba(59,130,246,0.1)', color: vars.color.primary }}>{m}</span>
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

      {tab === 'config' && (
        <TenantConfigTab tenantId={id!} tenant={tenant} onSaved={reload} />
      )}

      {tab === 'integrations' && (
        <div className={s.card}>
          <div className={s.cardTitle}>Armazenamento &amp; Integrações do tenant</div>
          <div className={s.muted} style={{ marginBottom: 16, fontSize: 12 }}>
            Credenciais próprias do cliente (ex.: bucket R2), cifradas no backend.
            O secret nunca é reexibido — apenas os últimos 4 caracteres.
          </div>
          <IntegrationsPanel tenantId={id!} />
        </div>
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

/** Usuário com role customizada e/ou overrides granulares (badge WS7). */
function isCustomizedUser(u: AdminUser): boolean {
  return Boolean(u.custom_role_id) || (u.permission_override_count ?? 0) > 0
}

function UsersTab({ tenantId, tenant, onReload }: { tenantId: string; tenant: Tenant; onReload: () => void }) {
  const toast = useToast()
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ email: '', role: 'operator' })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [permissionsUser, setPermissionsUser] = useState<DrawerUser | null>(null)
  const [impersonateTarget, setImpersonateTarget] = useState<AdminUser | null>(null)
  const [impersonating, setImpersonating] = useState(false)

  const handleImpersonate = async () => {
    if (!impersonateTarget) return
    setImpersonating(true)
    try {
      await startImpersonation(impersonateTarget.id)
      // startImpersonation redireciona — nada a fazer aqui
    } catch (e: unknown) {
      toast.error(
        'Erro ao iniciar visualização',
        e instanceof Error ? e.message : 'Tente novamente.',
      )
      setImpersonating(false)
      setImpersonateTarget(null)
    }
  }

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
        <div style={{
          background: 'rgba(0,0,0,.03)', // allow: realce sutil translúcido
          borderRadius: 8, padding: 16, marginBottom: 16,
        }}>
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
                <td className={s.td}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <UserRoleBadge role={u.role} />
                    {isCustomizedUser(u) && <Badge variant="accent">Customizado</Badge>}
                  </span>
                </td>
                <td className={s.td}><span className={s.muted}>{u.last_login_at ? new Date(u.last_login_at).toLocaleDateString('pt-BR') : '—'}</span></td>
                <td className={s.td}><span className={s.dot[u.is_active ? 'healthy' : 'critical']} /></td>
                <td className={s.td}>
                  <span style={{ display: 'inline-flex', gap: 4 }}>
                    {u.role !== 'superadmin' && (
                      <button
                        className={s.btnGhost}
                        style={{ padding: '2px 8px', fontSize: 12 }}
                        onClick={() => setPermissionsUser({ id: u.id, email: u.email, role: u.role, tenant_id: tenantId })}
                      >
                        Permissões
                      </button>
                    )}
                    {u.role !== 'superadmin' && u.is_active && (
                      <Tooltip label="Ver a plataforma como este usuário (30 min, com registro de auditoria)">
                        <button
                          className={s.btnGhost}
                          style={{ padding: '2px 8px', fontSize: 12 }}
                          onClick={() => setImpersonateTarget(u)}
                        >
                          <Eye size={12} /> Ver como
                        </button>
                      </Tooltip>
                    )}
                    <button
                      className={u.is_active ? s.btnDanger : s.btnSuccess}
                      style={{ padding: '2px 8px', fontSize: 12 }}
                      onClick={() => handleToggleUser(u.id, u.is_active)}
                    >
                      {u.is_active ? 'Desativar' : 'Reativar'}
                    </button>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <span className={s.muted}>Nenhum usuário cadastrado neste tenant.</span>}

      <UserPermissionsDrawer
        open={permissionsUser !== null}
        onClose={() => setPermissionsUser(null)}
        user={permissionsUser}
        onChanged={onReload}
      />

      <ConfirmDialog
        open={impersonateTarget !== null}
        onClose={() => { if (!impersonating) setImpersonateTarget(null) }}
        onConfirm={handleImpersonate}
        title="Ver como usuário"
        description={`Você vai visualizar a plataforma como ${impersonateTarget?.email ?? ''} por até 30 minutos. A ação fica registrada na auditoria e você pode sair a qualquer momento pelo banner no topo.`}
        confirmLabel="Iniciar visualização"
        variant="primary"
        loading={impersonating}
      />
    </div>
  )
}

// ── Modules Tab ───────────────────────────────────────────────────────────────

const MODULE_STATUS_LABEL: Record<ModuleCatalogEntry['status'], string> = {
  active: 'Ativo',
  beta: 'Beta',
  coming_soon: 'Em breve',
}

function ModulesTab({ tenantId, tenant, onUpdate }: { tenantId: string; tenant: Tenant; onUpdate: (t: Tenant) => void }) {
  const [saving, setSaving] = useState<string | null>(null)
  const [catalog, setCatalog] = useState<ModuleCatalogEntry[]>(FALLBACK_MODULES)
  const enabled = new Set(tenant.modules_enabled ?? [])

  useEffect(() => {
    adminService.getModulesCatalog().then(setCatalog).catch(() => {})
  }, [])

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
      {catalog.map((mod) => {
        const active = enabled.has(mod.code)
        return (
          <div key={mod.code} className={s.flex} style={{ padding: '10px 0', borderBottom: '1px solid rgba(0,0,0,.05)' }}>
            <span style={{ flex: 1, fontWeight: active ? 600 : 400, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              {mod.label}
              {mod.description && (
                <Tooltip label={mod.description}>
                  <HelpCircle size={13} style={{ color: vars.color.textMuted, cursor: 'help' }} aria-label={`Sobre ${mod.label}`} />
                </Tooltip>
              )}
              {mod.status !== 'active' && (
                <Badge variant="neutral">{MODULE_STATUS_LABEL[mod.status]}</Badge>
              )}
            </span>
            <span className={s.muted} style={{ marginRight: 12, fontSize: 12 }}>{active ? 'Ativo' : 'Inativo'}</span>
            <button
              onClick={() => toggleModule(mod.code)}
              disabled={saving === mod.code}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: active ? vars.color.primary : vars.color.textMuted, padding: 0 }}
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

// ── Configurações (WS6 — políticas de plataforma) ─────────────────────────────

function TenantConfigTab({ tenantId, tenant, onSaved }: { tenantId: string; tenant: Tenant; onSaved: () => void }) {
  const toast = useToast()
  const [maxSeats, setMaxSeats] = useState<string>(tenant.max_seats != null ? String(tenant.max_seats) : '')
  const [singleSession, setSingleSession] = useState<boolean>(Boolean(tenant.single_session))
  const [rateLimit, setRateLimit] = useState<string>(tenant.rate_limit_per_minute != null ? String(tenant.rate_limit_per_minute) : '')
  const [retention, setRetention] = useState<string>(tenant.default_retention_days != null ? String(tenant.default_retention_days) : '')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const seatsInUse = tenant.seats_in_use ?? tenant.users?.filter((u) => u.is_active).length ?? 0
  const planRate = tenant.plan_rate_limit_per_minute
  const planRetention = tenant.plan_retention_days

  const handleSave = async () => {
    setErr(null)

    const parsedSeats = maxSeats.trim() === '' ? null : Number(maxSeats)
    if (parsedSeats !== null && (!Number.isInteger(parsedSeats) || parsedSeats < 1)) {
      setErr('Máx. de assentos deve ser um número inteiro maior que zero ou vazio (ilimitado).')
      return
    }
    const parsedRate = rateLimit.trim() === '' ? null : Number(rateLimit)
    if (parsedRate !== null && (!Number.isInteger(parsedRate) || parsedRate < 1)) {
      setErr('Rate limit deve ser um número inteiro maior que zero ou vazio (herda do plano).')
      return
    }
    const parsedRetention = retention === '' ? null : Number(retention)

    setSaving(true)
    try {
      await adminService.updateTenant(tenantId, {
        max_seats: parsedSeats,
        single_session: singleSession,
        rate_limit_per_minute: parsedRate,
        default_retention_days: parsedRetention,
      })
      toast.success('Configurações salvas', 'As políticas do tenant foram atualizadas.')
      onSaved()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erro ao salvar configurações'
      setErr(msg)
      toast.error('Erro ao salvar', msg)
    } finally { setSaving(false) }
  }

  const fieldRow: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: 12,
    padding: '12px 0', borderBottom: `1px solid ${vars.color.borderSubtle}`,
  }
  const fieldLabel: React.CSSProperties = {
    width: 220, flexShrink: 0, fontSize: 13, fontWeight: 500,
    display: 'inline-flex', alignItems: 'center', gap: 6,
  }

  return (
    <div className={s.card}>
      <div className={s.cardTitle}>Políticas de plataforma</div>
      <div className={s.muted} style={{ marginBottom: 8, fontSize: 12 }}>
        Limites e comportamento de sessão deste tenant. Campos vazios herdam o padrão do plano.
      </div>

      <div style={fieldRow}>
        <span style={fieldLabel}>
          Máx. de assentos
          <Tooltip label="Quantidade máxima de usuários ativos simultâneos permitidos neste tenant. Vazio = ilimitado.">
            <HelpCircle size={13} style={{ color: vars.color.textMuted, cursor: 'help' }} aria-label="Sobre máx. de assentos" />
          </Tooltip>
        </span>
        <input
          className={s.input}
          type="number"
          min={1}
          style={{ width: 120 }}
          placeholder="Ilimitado"
          value={maxSeats}
          onChange={(e) => setMaxSeats(e.target.value)}
        />
        <span className={s.muted} style={{ fontSize: 12 }}>{seatsInUse} em uso</span>
      </div>

      <div style={fieldRow}>
        <span style={fieldLabel}>
          Sessão única
          <Tooltip label="Quando ativado, um novo login derruba a sessão anterior do mesmo usuário (última sessão ganha).">
            <HelpCircle size={13} style={{ color: vars.color.textMuted, cursor: 'help' }} aria-label="Sobre sessão única" />
          </Tooltip>
        </span>
        <button
          onClick={() => setSingleSession((v) => !v)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: singleSession ? vars.color.primary : vars.color.textMuted, padding: 0 }}
          aria-pressed={singleSession}
          aria-label="Alternar sessão única"
        >
          {singleSession ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}
        </button>
        <span className={s.muted} style={{ fontSize: 12 }}>{singleSession ? 'Ativada' : 'Desativada'}</span>
      </div>

      <div style={fieldRow}>
        <span style={fieldLabel}>
          Rate limit (req/min)
          <Tooltip label="Limite de requisições por minuto na API para este tenant. Vazio = herda o limite do plano.">
            <HelpCircle size={13} style={{ color: vars.color.textMuted, cursor: 'help' }} aria-label="Sobre rate limit" />
          </Tooltip>
        </span>
        <input
          className={s.input}
          type="number"
          min={1}
          style={{ width: 120 }}
          placeholder={planRate != null ? `Plano: ${planRate}` : 'Herda do plano'}
          value={rateLimit}
          onChange={(e) => setRateLimit(e.target.value)}
        />
        {planRate != null && (
          <span className={s.muted} style={{ fontSize: 12 }}>efetivo do plano: {planRate}/min</span>
        )}
      </div>

      <div style={fieldRow}>
        <span style={fieldLabel}>
          Retenção padrão (dias)
          <Tooltip label="Por quantos dias evidências e gravações ficam armazenadas por padrão. Vazio = herda a retenção do plano.">
            <HelpCircle size={13} style={{ color: vars.color.textMuted, cursor: 'help' }} aria-label="Sobre retenção padrão" />
          </Tooltip>
        </span>
        <select
          className={s.select}
          style={{ width: 200 }}
          value={retention}
          onChange={(e) => setRetention(e.target.value)}
        >
          <option value="">
            {planRetention != null ? `Herdar do plano (${planRetention} dias)` : 'Herdar do plano'}
          </option>
          {RETENTION_TIERS.map((t) => (
            <option key={t} value={String(t)}>{t} {t === 1 ? 'dia' : 'dias'}</option>
          ))}
        </select>
      </div>

      {err && <div className={s.alertBanner.danger} style={{ marginTop: 12 }}>{err}</div>}

      <div className={s.flex} style={{ justifyContent: 'flex-end', marginTop: 16 }}>
        <button className={s.btnPrimary} onClick={handleSave} disabled={saving}>
          {saving ? 'Salvando...' : 'Salvar configurações'}
        </button>
      </div>
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
