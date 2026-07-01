/**
 * AdminIntegrationsPage — Integrações self-service (superadmin only).
 *
 * Cards: Storage (R2), Provedor GPU (Vast.ai), GPU Genérico, Notificação.
 * Regras:
 *   - Secret nunca no DOM como plaintext
 *   - Display: ••••{last4} quando configurado
 *   - Botão "Testar" → POST /test → feedback loading/ok/erro
 *   - Botão "Salvar" → PUT /{type}
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../../hooks/useAuth'
import { api } from '../../../services/api'

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
  configFields: { key: string; label: string; placeholder: string }[]
  secretLabel: string
  secretPlaceholder: string
}

const CARD_SPECS: CardSpec[] = [
  {
    type: 'r2',
    title: 'Storage — Cloudflare R2',
    description: 'Armazenamento de frames, modelos e datasets.',
    configFields: [
      { key: 'endpoint', label: 'Endpoint', placeholder: 'https://ACCOUNT.r2.cloudflarestorage.com' },
      { key: 'bucket', label: 'Bucket', placeholder: 'recognition-prod' },
    ],
    secretLabel: 'Secret Access Key',
    secretPlaceholder: 'Deixe vazio para manter atual',
  },
  {
    type: 'vast_ai',
    title: 'Provedor GPU — Vast.ai',
    description: 'Treinamento de modelos YOLO em GPUs sob demanda.',
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
]

// ── Component ─────────────────────────────────────────────────────────────────

export function AdminIntegrationsPage() {
  const { isSuperAdmin } = useAuth()
  const navigate = useNavigate()

  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState<string | null>(null)

  useEffect(() => {
    if (!isSuperAdmin) {
      navigate('/admin', { replace: true })
      return
    }
    fetchAll()
  }, [isSuperAdmin]) // eslint-disable-line react-hooks/exhaustive-deps

  function fetchAll() {
    setLoading(true)
    api.get<ApiEnvelope<{ integrations: Integration[] }>>('/v1/admin/integrations/')
      .then((res) => setIntegrations(res.data?.integrations ?? []))
      .catch((e: Error) => setPageError(e.message))
      .finally(() => setLoading(false))
  }

  if (!isSuperAdmin) return null
  if (loading) return <div style={styles.loading}>Carregando integrações...</div>
  if (pageError) return <div style={styles.pageError}>Erro: {pageError}</div>

  return (
    <div style={styles.root}>
      <h1 style={styles.title}>Integrações</h1>
      <p style={styles.subtitle}>
        Credenciais armazenadas cifradas (Fernet). O plaintext nunca é exibido.
      </p>
      <div style={styles.grid}>
        {CARD_SPECS.map((spec) => {
          const current = integrations.find((i) => i.integration_type === spec.type) ?? null
          return (
            <IntegrationCard
              key={spec.type}
              spec={spec}
              current={current}
              onSaved={fetchAll}
            />
          )
        })}
      </div>
    </div>
  )
}

// ── Card ──────────────────────────────────────────────────────────────────────

interface CardProps {
  spec: CardSpec
  current: Integration | null
  onSaved: () => void
}

function IntegrationCard({ spec, current, onSaved }: CardProps) {
  const [label, setLabel] = useState(current?.label ?? spec.type)
  const [config, setConfig] = useState<Record<string, string>>(current?.config ?? {})
  const [secret, setSecret] = useState('')  // sempre vazio no load — user digita para alterar
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
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

  async function handleSave() {
    setSaving(true)
    setSaveMsg(null)
    try {
      const body: Record<string, unknown> = { label, config }
      if (secret) body.secret = secret
      await api.put(`/v1/admin/integrations/${spec.type}`, body)
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
        `/v1/admin/integrations/${spec.type}/test`,
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

  const status = current?.status ?? 'unconfigured'
  const statusColor = status === 'ok' ? '#22c55e' : status === 'error' ? '#ef4444' : '#9ca3af'
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
            {f.label}
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
      </div>

      {/* Feedback */}
      {saveMsg && (
        <div style={{ ...styles.feedback, color: saveMsg.ok ? '#22c55e' : '#ef4444' }}>
          {saveMsg.text}
        </div>
      )}
      {testMsg && (
        <div style={{ ...styles.feedback, color: testMsg.ok ? '#22c55e' : '#ef4444' }}>
          {testMsg.text}
        </div>
      )}
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = {
  root: {
    padding: '24px 32px',
    maxWidth: 900,
  } satisfies React.CSSProperties,
  title: {
    fontSize: 24,
    fontWeight: 700,
    marginBottom: 6,
  } satisfies React.CSSProperties,
  subtitle: {
    color: '#6b7280',
    fontSize: 14,
    marginBottom: 28,
  } satisfies React.CSSProperties,
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
    gap: 20,
  } satisfies React.CSSProperties,
  card: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: 10,
    padding: '20px 24px',
    boxShadow: '0 1px 4px rgba(0,0,0,.06)',
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
    color: '#6b7280',
    marginTop: 2,
  } satisfies React.CSSProperties,
  statusBadge: {
    fontSize: 12,
    fontWeight: 600,
    whiteSpace: 'nowrap' as const,
  } satisfies React.CSSProperties,
  lastTested: {
    fontSize: 12,
    color: '#9ca3af',
  } satisfies React.CSSProperties,
  errorMsg: {
    fontSize: 12,
    color: '#ef4444',
    background: '#fef2f2',
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
    color: '#374151',
    gap: 4,
  } satisfies React.CSSProperties,
  input: {
    border: '1px solid #d1d5db',
    borderRadius: 6,
    padding: '7px 10px',
    fontSize: 13,
    outline: 'none',
  } satisfies React.CSSProperties,
  currentSecret: {
    fontSize: 11,
    color: '#9ca3af',
    fontWeight: 400,
    marginLeft: 6,
  } satisfies React.CSSProperties,
  actions: {
    display: 'flex',
    gap: 8,
    marginTop: 4,
  } satisfies React.CSSProperties,
  btnPrimary: {
    background: '#0070f3',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    padding: '8px 16px',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  } satisfies React.CSSProperties,
  btnSecondary: {
    background: '#f3f4f6',
    color: '#374151',
    border: '1px solid #d1d5db',
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
    padding: 32,
    color: '#6b7280',
  } satisfies React.CSSProperties,
  pageError: {
    padding: 32,
    color: '#ef4444',
  } satisfies React.CSSProperties,
}
