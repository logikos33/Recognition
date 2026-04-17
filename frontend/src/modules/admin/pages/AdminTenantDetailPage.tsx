import { ArrowLeft, Ban, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { adminService } from '../services/adminService'
import { WorkerStatusBadge } from '../components/WorkerStatusBadge'
import { UserRoleBadge } from '../components/UserRoleBadge'
import * as s from '../components/admin.css'
import type { Tenant } from '../types/admin'

type Tab = 'overview' | 'users' | 'worker' | 'modules' | 'flags' | 'history'

export function AdminTenantDetailPage() {
  const { id } = useParams<{ id: string }>()
  const nav = useNavigate()
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('overview')
  const [busy, setBusy] = useState(false)

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
        <div className={s.card}>
          <div className={s.cardTitle}>Usuários do tenant</div>
          {tenant.users && tenant.users.length > 0 ? (
            <table className={s.table}>
              <thead><tr><th className={s.th}>Email</th><th className={s.th}>Role</th><th className={s.th}>Último login</th><th className={s.th}>Status</th></tr></thead>
              <tbody>
                {tenant.users.map((u) => (
                  <tr key={u.id} className={s.trHover}>
                    <td className={s.td}>{u.email}</td>
                    <td className={s.td}><UserRoleBadge role={u.role} /></td>
                    <td className={s.td}><span className={s.muted}>{u.last_login_at ? new Date(u.last_login_at).toLocaleDateString('pt-BR') : '—'}</span></td>
                    <td className={s.td}><span className={s.dot[u.is_active ? 'healthy' : 'critical']} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <span className={s.muted}>Nenhum usuário carregado. Acesse a página de Usuários e filtre por tenant.</span>}
        </div>
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
        <div className={s.card}>
          <div className={s.cardTitle}>Módulos</div>
          {(tenant.modules_enabled ?? []).map((m) => (
            <div key={m} className={s.flex} style={{ padding: '6px 0', borderBottom: '1px solid rgba(0,0,0,.05)' }}>
              <span style={{ flex: 1 }}>{m}</span>
              <span className={s.dot.healthy} />
            </div>
          ))}
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

function TenantFlagsTab({ tenantId }: { tenantId: string }) {
  const [flags, setFlags] = useState<Record<string, boolean> | null>(null)
  useEffect(() => {
    adminService.getTenantFeatureFlags(tenantId).then(setFlags).catch(() => {})
  }, [tenantId])
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
      {Object.keys(flags).length === 0 && <span className={s.muted}>Nenhuma flag configurada.</span>}
    </>
  )
}

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
            <td className={s.td}><span className={s.mono}>{h.changed_at ? new Date(h.changed_at).toLocaleDateString('pt-BR') : '—'}</span></td>
            <td className={s.td}>{h.from_plan ?? '—'}</td>
            <td className={s.td}>{h.to_plan ?? '—'}</td>
            <td className={s.td}><span className={s.muted}>{h.changed_by_email ?? '—'}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
