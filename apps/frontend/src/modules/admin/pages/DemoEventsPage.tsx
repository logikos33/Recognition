/**
 * DemoEventsPage — Eventos demo para a Investigação (superadmin only).
 *
 * Permite semear/remover eventos mock (tabela apartada demo_events) para o
 * tenant escolhido. Os eventos aparecem na Investigação do tenant com selo
 * "Demo", distribuídos pelos últimos 7 dias. Alertas reais NUNCA são tocados.
 *
 * Precedente: DemoVideosPage (guard superadmin client-side) — porém com UI kit.
 */
import { useState, useEffect, useCallback } from 'react'
import { Navigate } from 'react-router-dom'
import { Sparkles, Trash2 } from 'lucide-react'
import { useAuth } from '../../../hooks/useAuth'
import { api } from '../../../services/api'
import { vars } from '../../../styles/theme.css'
import { PageHeader } from '../../../components/ui/PageHeader/PageHeader'
import { Panel } from '../../../components/ui/Panel/Panel'
import { Banner } from '../../../components/ui/Banner/Banner'
import { Button } from '../../../components/ui/Button/Button'
import { Input, Field } from '../../../components/ui/Input/Input'
import { EmptyState } from '../../../components/ui/EmptyState/EmptyState'
import { ConfirmDialog } from '../../../components/ui/ConfirmDialog/ConfirmDialog'
import { Badge } from '../../../components/ui/Badge/Badge'
import { useToast } from '../../../components/ui/Toast/useToast'

interface ApiEnvelope<T> {
  success: boolean
  data: T
  error?: string
}

interface TenantOption {
  id: string
  name: string
  slug: string
}

interface DemoModuleCount {
  module_code: string
  count: number
  last_seeded_at: string | null
}

const MODULE_OPTIONS = [
  { value: 'epi',     label: 'EPI' },
  { value: 'fueling', label: 'Abastecimento' },
] as const

const MODULE_LABELS: Record<string, string> = {
  epi: 'EPI',
  fueling: 'Abastecimento',
}

const selectStyle: React.CSSProperties = {
  padding: '8px 10px',
  background: vars.color.bgSurface,
  color: vars.color.textPrimary,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: 6,
  fontSize: '0.875rem',
  width: '100%',
  boxSizing: 'border-box',
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('pt-BR')
  } catch {
    return iso
  }
}

export function DemoEventsPage() {
  const { isSuperAdmin } = useAuth()
  const toast = useToast()

  const [tenants, setTenants]       = useState<TenantOption[]>([])
  const [tenantId, setTenantId]     = useState('')
  const [moduleCode, setModuleCode] = useState<string>('epi')
  const [countStr, setCountStr]     = useState('30')

  const [counts, setCounts]               = useState<DemoModuleCount[]>([])
  const [loadingStatus, setLoadingStatus] = useState(false)
  const [seeding, setSeeding]             = useState(false)
  const [removing, setRemoving]           = useState(false)
  const [confirmRemove, setConfirmRemove] = useState<DemoModuleCount | null>(null)

  // Proteção extra no client: redireciona se não for superadmin
  if (!isSuperAdmin) return <Navigate to="/" replace />

  const countNum = Number(countStr)
  const countError =
    countStr === '' || Number.isNaN(countNum) || countNum < 1 || countNum > 500
      ? 'Informe uma quantidade entre 1 e 500'
      : undefined

  // Tenants para o seletor (rota admin existente)
  useEffect(() => {
    api.get<ApiEnvelope<{ tenants: TenantOption[] }>>('/v1/admin/tenants')
      .then((res) => setTenants(res.data?.tenants ?? []))
      .catch(() => setTenants([]))
  }, [])

  const refreshStatus = useCallback(async (tid: string) => {
    if (!tid) {
      setCounts([])
      return
    }
    setLoadingStatus(true)
    try {
      const res = await api.get<ApiEnvelope<{ counts: DemoModuleCount[]; total: number }>>(
        `/v1/admin/demo-events?tenant_id=${encodeURIComponent(tid)}`
      )
      setCounts(res.data?.counts ?? [])
    } catch {
      setCounts([])
    } finally {
      setLoadingStatus(false)
    }
  }, [])

  useEffect(() => {
    refreshStatus(tenantId)
  }, [tenantId, refreshStatus])

  const handleSeed = async () => {
    if (!tenantId || countError) return
    setSeeding(true)
    try {
      const res = await api.post<ApiEnvelope<{ created: number; batch_id: string }>>(
        '/v1/admin/demo-events/seed',
        { tenant_id: tenantId, module_code: moduleCode, count: countNum }
      )
      toast.success(`${res.data?.created ?? countNum} eventos demo criados`)
      await refreshStatus(tenantId)
    } catch (e: unknown) {
      toast.error('Erro ao criar eventos demo', e instanceof Error ? e.message : undefined)
    } finally {
      setSeeding(false)
    }
  }

  const handleRemove = async () => {
    if (!tenantId || !confirmRemove) return
    setRemoving(true)
    try {
      const res = await api.delete<ApiEnvelope<{ deleted: number }>>(
        `/v1/admin/demo-events?tenant_id=${encodeURIComponent(tenantId)}&module_code=${encodeURIComponent(confirmRemove.module_code)}`
      )
      toast.success(`${res.data?.deleted ?? 0} eventos demo removidos`)
      setConfirmRemove(null)
      await refreshStatus(tenantId)
    } catch (e: unknown) {
      toast.error('Erro ao remover eventos demo', e instanceof Error ? e.message : undefined)
    } finally {
      setRemoving(false)
    }
  }

  return (
    <div style={{ padding: 28, maxWidth: 900, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <PageHeader
        title="Eventos Demo"
        subtitle="Semeie eventos fictícios para demonstrar a Investigação de um tenant"
        actions={<Badge variant="accent">Superadmin</Badge>}
      />

      <Banner variant="info" icon={<Sparkles size={16} />}>
        Os eventos aparecem na Investigação do tenant com o selo <strong>Demo</strong>,
        distribuídos pelos últimos 7 dias. Eles vivem em uma tabela apartada —
        alertas reais nunca são afetados pela criação ou remoção.
      </Banner>

      {/* Formulário de seed */}
      <Panel title="Incluir eventos demo" variant="card">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
          <Field label="Tenant">
            <select
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              style={selectStyle}
              aria-label="Tenant"
            >
              <option value="">Selecione o tenant</option>
              {tenants.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} ({t.slug})
                </option>
              ))}
            </select>
          </Field>

          <Field label="Módulo">
            <select
              value={moduleCode}
              onChange={(e) => setModuleCode(e.target.value)}
              style={selectStyle}
              aria-label="Módulo"
            >
              {MODULE_OPTIONS.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </Field>

          <Field label="Quantidade" error={countError}>
            <Input
              type="number"
              min={1}
              max={500}
              value={countStr}
              onChange={(e) => setCountStr(e.target.value)}
              error={countError}
              aria-label="Quantidade de eventos"
            />
          </Field>
        </div>

        <div style={{ marginTop: 14 }}>
          <Button
            variant="primary"
            onClick={handleSeed}
            loading={seeding}
            disabled={!tenantId || Boolean(countError)}
          >
            Incluir eventos demo
          </Button>
          {!tenantId && (
            <span style={{ marginLeft: 10, fontSize: '0.75rem', color: vars.color.textMuted }}>
              Selecione um tenant para habilitar
            </span>
          )}
        </div>
      </Panel>

      {/* Status por módulo */}
      <Panel
        title="Eventos demo existentes"
        variant="card"
        padding="none"
        actions={loadingStatus ? (
          <span style={{ fontSize: '0.75rem', color: vars.color.textMuted }}>Carregando…</span>
        ) : undefined}
      >
        {!tenantId ? (
          <EmptyState
            icon={<Sparkles size={28} />}
            title="Selecione um tenant"
            description="Escolha um tenant acima para ver e gerenciar os eventos demo dele."
          />
        ) : counts.length === 0 && !loadingStatus ? (
          <EmptyState
            icon={<Sparkles size={28} />}
            title="Nenhum evento demo neste tenant"
            description="Use o formulário acima para incluir eventos de demonstração."
          />
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${vars.color.borderDefault}` }}>
                {['Módulo', 'Quantidade', 'Último seed', ''].map((col) => (
                  <th
                    key={col}
                    style={{
                      padding: '9px 16px', textAlign: 'left',
                      fontSize: '0.7rem', fontWeight: 600, color: vars.color.textMuted,
                      textTransform: 'uppercase', letterSpacing: '0.05em',
                    }}
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {counts.map((c) => (
                <tr key={c.module_code} style={{ borderBottom: `1px solid ${vars.color.borderDefault}` }}>
                  <td style={{ padding: '11px 16px', fontSize: '0.85rem', color: vars.color.textPrimary, fontWeight: 500 }}>
                    {MODULE_LABELS[c.module_code] ?? c.module_code}
                  </td>
                  <td style={{ padding: '11px 16px', fontSize: '0.85rem', color: vars.color.textSecondary }}>
                    {c.count}
                  </td>
                  <td style={{ padding: '11px 16px', fontSize: '0.8rem', color: vars.color.textSecondary }}>
                    {formatDateTime(c.last_seeded_at)}
                  </td>
                  <td style={{ padding: '11px 16px', textAlign: 'right' }}>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => setConfirmRemove(c)}
                    >
                      <Trash2 size={12} /> Remover
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <ConfirmDialog
        open={Boolean(confirmRemove)}
        onClose={() => setConfirmRemove(null)}
        onConfirm={handleRemove}
        loading={removing}
        title="Remover eventos demo"
        description={
          confirmRemove
            ? `Remover ${confirmRemove.count} eventos demo do módulo ${MODULE_LABELS[confirmRemove.module_code] ?? confirmRemove.module_code}? Alertas reais não são afetados.`
            : ''
        }
        confirmLabel="Remover"
        variant="danger"
      />
    </div>
  )
}
