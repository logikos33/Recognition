/**
 * IntegrationsPanel — formulário de integrações reutilizável (WS6).
 *
 * Extraído de AdminIntegrationsPage para ser usado em dois contextos:
 *   - AdminIntegrationsPage (sem tenantId → tenant do JWT, comportamento
 *     original preservado)
 *   - AdminTenantDetailPage aba "Armazenamento & Integrações"
 *     (tenantId do cliente → override ?tenant_id= p/ superadmin)
 *
 * Regras:
 *   - Secret nunca no DOM como plaintext; display ••••last4
 *   - Salvar / Testar conexão / Remover com loading/erro/sucesso
 *   - Somente superadmin alcança os endpoints (403 no backend)
 */
import { useEffect, useState } from 'react'
import { api } from '../../../services/api'
import { ConfirmDialog } from '../../../components/ui/ConfirmDialog/ConfirmDialog'
import { vars } from '../../../styles/theme.css'

// ── Types ────────────────────────────────────────────────────────────────────

interface Integration {
  id: string
  integration_type: string
  label: string
  config: Record<string, string>
  secret_display: string | null   // ••••XXXX — nunca plaintext
  status: 'unconfigured' | 'ok' | 'error'
  last_tested_at: string | null
  last_error: string | null
}

type ApiEnvelope<T> = { success: boolean; data: T; message?: string }
type TestResult = { ok: boolean; error: string | null }

interface CardSpec {
  type: string
  title: string
  description: string
  configFields: { key: string; label: string; placeholder: string; required?: boolean }[]
  secretLabel: string
  secretPlaceholder: string
}

const CARD_SPECS: CardSpec[] = [
  {
    type: 'r2',
    title: 'Storage — Cloudflare R2',
    description: 'Armazenamento de frames, modelos e datasets no bucket próprio do cliente.',
    configFields: [
      { key: 'account_id', label: 'Account ID', placeholder: 'ID da conta Cloudflare', required: true },
      { key: 'access_key_id', label: 'Access Key ID', placeholder: 'Chave de acesso R2', required: true },
      { key: 'bucket', label: 'Bucket', placeholder: 'recognition-prod' },
      { key: 'endpoint', label: 'Endpoint', placeholder: 'https://ACCOUNT.r2.cloudflarestorage.com' },
    ],
    secretLabel: 'Secret Access Key',
    secretPlaceholder: 'Deixe vazio para manter atual',
  },
  {
    type: 'vast_ai',
    title: 'Provedor GPU — Vast.ai',
    description: 'Treinamento de modelos de visão em GPUs sob demanda.',
    configFields: [
      { key: 'gpu_type', label: 'GPU preferida', placeholder: 'RTX_3090' },
    ],
    secretLabel: 'API Key',
    secretPlaceholder: 'Deixe vazio para manter atual',
  },
  {
    type: 'generic_gpu',
    title: 'GPU Genérico',
    description: 'Provedor GPU alternativo (SSH/API personalizado).',
    configFields: [
      { key: 'endpoint', label: 'Endpoint SSH/API', placeholder: 'https://meu-gpu.exemplo.com' },
    ],
    secretLabel: 'Token / Senha',
    secretPlaceholder: 'Deixe vazio para manter atual',
  },
  {
    type: 'notification',
    title: 'Notificações',
    description: 'Webhook ou chave para envio de alertas externos.',
    configFields: [
      { key: 'webhook_url', label: 'Webhook URL', placeholder: 'https://hooks.exemplo.com/...' },
    ],
    secretLabel: 'Secret do Webhook',
    secretPlaceholder: 'Deixe vazio para manter atual',
  },
  {
    type: 'byo_db',
    title: 'Banco de Dados Próprio',
    description: 'Conexão PostgreSQL dedicada do tenant (BYO database).',
    configFields: [
      { key: 'host', label: 'Host', placeholder: 'db.exemplo.com' },
      { key: 'database', label: 'Database', placeholder: 'recognition' },
    ],
    secretLabel: 'Senha / Connection String',
    secretPlaceholder: 'Deixe vazio para manter atual',
  },
]

/** Query string do override de tenant (superadmin) — vazio = tenant do JWT. */
function tenantQs(tenantId?: string): string {
  return tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : ''
}

// ── Panel ─────────────────────────────────────────────────────────────────────

export function IntegrationsPanel({ tenantId }: { tenantId?: string }) {
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState<string | null>(null)

  function fetchAll() {
    setLoading(true)
    api.get<ApiEnvelope<{ integrations: Integration[] }>>(
      `/v1/admin/integrations/${tenantQs(tenantId)}`,
    )
      .then((res) => setIntegrations(res.data?.integrations ?? []))
      .catch((e: Error) => setPageError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantId])

  if (loading) return <div style={styles.loading}>Carregando integrações...</div>
  if (pageError) return <div style={styles.pageError}>Erro: {pageError}</div>

  return (
    <div style={styles.grid}>
      {CARD_SPECS.map((spec) => {
        const current = integrations.find((i) => i.integration_type === spec.type) ?? null
        return (
          <IntegrationCard
            key={spec.type}
            spec={spec}
            current={current}
            tenantId={tenantId}
            onSaved={fetchAll}
          />
        )
      })}
    </div>
  )
}

// ── Card ──────────────────────────────────────────────────────────────────────

interface CardProps {
  spec: CardSpec
  current: Integration | null
  tenantId?: string
  onSaved: () => void
}

function IntegrationCard({ spec, current, tenantId, onSaved }: CardProps) {
  const [label, setLabel] = useState(current?.label ?? spec.type)
  const [config, setConfig] = useState<Record<string, string>>(current?.config ?? {})
  const [secret, setSecret] = useState('')  // sempre vazio no load — user digita para alterar
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [confirmRemove, setConfirmRemove] = useState(false)
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [testMsg, setTestMsg] = useState<{ ok: boolean; text: string } | null>(null)

  // Re-sync when integration data changes
  useEffect(() => {
    setLabel(current?.label ?? spec.type)
    setConfig(current?.config ?? {})
    setSecret('')
    setSaveMsg(null)
    setTestMsg(null)
  }, [current, spec.type])

  function handleConfigChange(key: string, value: string) {
    setConfig((prev) => ({ ...prev, [key]: value }))
  }

  const missingRequired = spec.configFields
    .filter((f) => f.required && !(config[f.key] ?? '').trim())
    .map((f) => f.label)

  async function handleSave() {
    if (missingRequired.length > 0) {
      setSaveMsg({ ok: false, text: `Campos obrigatórios: ${missingRequired.join(', ')}` })
      return
    }
    setSaving(true)
    setSaveMsg(null)
    try {
      const body: Record<string, unknown> = { label, config }
      if (secret) body.secret = secret
      await api.put(`/v1/admin/integrations/${spec.type}${tenantQs(tenantId)}`, body)
      setSaveMsg({ ok: true, text: 'Salvo com sucesso' })
      setSecret('')
      onSaved()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erro ao salvar'
      setSaveMsg({ ok: false, text: msg })
    } finally {
      setSaving(false)
    }
  }

  async function handleTest() {
    setTesting(true)
    setTestMsg(null)
    try {
      const res = await api.post<ApiEnvelope<TestResult>>(
        `/v1/admin/integrations/${spec.type}/test${tenantQs(tenantId)}`,
        {}
      )
      const result = res.data
      setTestMsg(result.ok
        ? { ok: true, text: 'Conexão estabelecida com sucesso' }
        : { ok: false, text: result.error ?? 'Falha na conexão' }
      )
      onSaved()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erro ao testar'
      setTestMsg({ ok: false, text: msg })
    } finally {
      setTesting(false)
    }
  }

  async function handleRemove() {
    setRemoving(true)
    try {
      await api.delete(`/v1/admin/integrations/${spec.type}${tenantQs(tenantId)}`)
      setConfirmRemove(false)
      setSaveMsg({ ok: true, text: 'Integração removida' })
      onSaved()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erro ao remover'
      setSaveMsg({ ok: false, text: msg })
      setConfirmRemove(false)
    } finally {
      setRemoving(false)
    }
  }

  const status = current?.status ?? 'unconfigured'
  const statusColor = status === 'ok'
    ? vars.color.success
    : status === 'error' ? vars.color.danger : vars.color.textMuted
  const statusLabel = status === 'ok' ? '● Conectado' : status === 'error' ? '● Erro' : '○ Não configurado'

  return (
    <div style={styles.card}>
      {/* Header */}
      <div style={styles.cardHeader}>
        <div>
          <div style={styles.cardTitle}>{spec.title}</div>
          <div style={styles.cardDesc}>{spec.description}</div>
        </div>
        <span style={{ ...styles.statusBadge, color: statusColor }}>{statusLabel}</span>
      </div>

      {/* Last tested */}
      {current?.last_tested_at && (
        <div style={styles.lastTested}>
          Último teste: {new Date(current.last_tested_at).toLocaleString('pt-BR')}
        </div>
      )}
      {current?.last_error && status === 'error' && (
        <div style={styles.errorMsg}>{current.last_error}</div>
      )}

      {/* Form */}
      <div style={styles.form}>
        <label style={styles.label}>
          Label
          <input
            style={styles.input}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder={spec.type}
          />
        </label>

        {spec.configFields.map((f) => (
          <label key={f.key} style={styles.label}>
            {f.label}{f.required ? ' *' : ''}
            <input
              style={styles.input}
              value={config[f.key] ?? ''}
              onChange={(e) => handleConfigChange(f.key, e.target.value)}
              placeholder={f.placeholder}
            />
          </label>
        ))}

        <label style={styles.label}>
          {spec.secretLabel}
          {current?.secret_display && (
            <span style={styles.currentSecret}>atual: {current.secret_display}</span>
          )}
          <input
            style={styles.input}
            type="password"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            placeholder={spec.secretPlaceholder}
            autoComplete="new-password"
          />
        </label>
      </div>

      {/* Actions */}
      <div style={styles.actions}>
        <button
          style={styles.btnPrimary}
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? 'Salvando...' : 'Salvar'}
        </button>
        <button
          style={styles.btnSecondary}
          onClick={handleTest}
          disabled={testing || !current}
        >
          {testing ? 'Testando...' : 'Testar conexão'}
        </button>
        <button
          style={styles.btnDanger}
          onClick={() => setConfirmRemove(true)}
          disabled={removing || !current}
        >
          {removing ? 'Removendo...' : 'Remover'}
        </button>
      </div>

      {/* Feedback */}
      {saveMsg && (
        <div style={{ ...styles.feedback, color: saveMsg.ok ? vars.color.success : vars.color.danger }}>
          {saveMsg.text}
        </div>
      )}
      {testMsg && (
        <div style={{ ...styles.feedback, color: testMsg.ok ? vars.color.success : vars.color.danger }}>
          {testMsg.text}
        </div>
      )}

      <ConfirmDialog
        open={confirmRemove}
        onClose={() => setConfirmRemove(false)}
        onConfirm={handleRemove}
        title="Remover integração"
        description={`Remover a integração "${spec.title}"? A credencial cifrada será apagada e o recurso deixará de funcionar para este tenant.`}
        confirmLabel="Remover"
        loading={removing}
      />
    </div>
  )
}

// ── Styles (tokens do tema — zero cor hardcoded) ─────────────────────────────

const styles = {
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
    gap: 20,
  } satisfies React.CSSProperties,
  card: {
    background: vars.color.bgCard,
    border: `1px solid ${vars.color.borderDefault}`,
    borderRadius: 10,
    padding: '20px 24px',
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 12,
  } satisfies React.CSSProperties,
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 8,
  } satisfies React.CSSProperties,
  cardTitle: {
    fontSize: 16,
    fontWeight: 600,
  } satisfies React.CSSProperties,
  cardDesc: {
    fontSize: 13,
    color: vars.color.textSecondary,
    marginTop: 2,
  } satisfies React.CSSProperties,
  statusBadge: {
    fontSize: 12,
    fontWeight: 600,
    whiteSpace: 'nowrap' as const,
  } satisfies React.CSSProperties,
  lastTested: {
    fontSize: 12,
    color: vars.color.textMuted,
  } satisfies React.CSSProperties,
  errorMsg: {
    fontSize: 12,
    color: vars.color.danger,
    background: vars.color.dangerMuted,
    padding: '6px 10px',
    borderRadius: 6,
  } satisfies React.CSSProperties,
  form: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 10,
  } satisfies React.CSSProperties,
  label: {
    display: 'flex',
    flexDirection: 'column' as const,
    fontSize: 13,
    fontWeight: 500,
    color: vars.color.textPrimary,
    gap: 4,
  } satisfies React.CSSProperties,
  input: {
    border: `1px solid ${vars.color.borderDefault}`,
    borderRadius: 6,
    padding: '7px 10px',
    fontSize: 13,
    outline: 'none',
    background: vars.color.bgSurface,
    color: vars.color.textPrimary,
  } satisfies React.CSSProperties,
  currentSecret: {
    fontSize: 11,
    color: vars.color.textMuted,
    fontWeight: 400,
    marginLeft: 6,
  } satisfies React.CSSProperties,
  actions: {
    display: 'flex',
    gap: 8,
    marginTop: 4,
  } satisfies React.CSSProperties,
  btnPrimary: {
    background: vars.color.primary,
    color: vars.color.textOnPrimary,
    border: 'none',
    borderRadius: 6,
    padding: '8px 16px',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  } satisfies React.CSSProperties,
  btnSecondary: {
    background: vars.color.bgSurface,
    color: vars.color.textPrimary,
    border: `1px solid ${vars.color.borderDefault}`,
    borderRadius: 6,
    padding: '8px 16px',
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
  } satisfies React.CSSProperties,
  btnDanger: {
    background: vars.color.bgSurface,
    color: vars.color.danger,
    border: `1px solid ${vars.color.borderDefault}`,
    borderRadius: 6,
    padding: '8px 16px',
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
  } satisfies React.CSSProperties,
  feedback: {
    fontSize: 13,
    fontWeight: 500,
  } satisfies React.CSSProperties,
  loading: {
    padding: 16,
    color: vars.color.textSecondary,
  } satisfies React.CSSProperties,
  pageError: {
    padding: 16,
    color: vars.color.danger,
  } satisfies React.CSSProperties,
}
