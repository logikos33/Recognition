/**
 * AdminTestConsolePage — Console de Teste E2E (task-056)
 *
 * Permite ao superadmin disparar e acompanhar um teste ponta a ponta
 * diretamente pela plataforma, sem terminal.
 *
 * Contrato de Operabilidade (task-056):
 *   - Chave Vast.ai: configurada em Integrações (banner se ausente)
 *   - Nº de câmeras simuladas: seletor 1–28
 *   - Seleção de modelo: dropdown do registry
 *   - Config cenário: classes EPI + limiar + zona/ROI (texto descritivo)
 *   - Ações: Start / Stop com estados loading/erro/sucesso
 *   - Métricas ao vivo: detecções/s, latência ms, throughput, % VRAM
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, Play, Square, Terminal, Zap } from 'lucide-react'
import { adminService } from '../services/adminService'
import type { TestConsoleStatus, Integration } from '../types/admin'
import * as s from '../components/admin.css'
import { vars } from '../../../styles/theme.css'

// ── Types ───────────────────────────────────────────────────────────────────

interface ScenarioConfig {
  classes: string[]
  confidence_threshold: number
  zone_description: string
}

const DEFAULT_SCENARIO: ScenarioConfig = {
  classes: ['helmet', 'no_helmet', 'vest', 'no_vest'],
  confidence_threshold: 0.5,
  zone_description: '',
}

const EPI_CLASSES = [
  'helmet', 'no_helmet',
  'vest', 'no_vest',
  'gloves', 'no_gloves',
  'glasses', 'no_glasses',
]

// ── Component ────────────────────────────────────────────────────────────────

export function AdminTestConsolePage() {
  // Config state
  const [cameraCount, setCameraCount] = useState(1)
  const [modelId, setModelId] = useState('pretrained')
  const [scenario, setScenario] = useState<ScenarioConfig>(DEFAULT_SCENARIO)
  const [availableModels, setAvailableModels] = useState<{ id: string; name: string }[]>([])

  // Console session state
  const [status, setStatus] = useState<TestConsoleStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [vastConfigured, setVastConfigured] = useState(false)

  // Integrations UI
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [intLoading, setIntLoading] = useState(false)
  const [showIntForm, setShowIntForm] = useState(false)
  const [intKey, setIntKey] = useState('vast_ai')
  const [intValue, setIntValue] = useState('')
  const [intTenantId, setIntTenantId] = useState('')
  const [intSaving, setIntSaving] = useState(false)
  const [intError, setIntError] = useState<string | null>(null)
  const [intSuccess, setIntSuccess] = useState(false)

  // Polling ref
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)

  // ── Load initial data ───────────────────────────────────────────────────

  const loadStatus = useCallback(async () => {
    try {
      const st = await adminService.getTestConsoleStatus()
      setStatus(st)
      setVastConfigured(st.vast_ai_configured)
    } catch {
      // silencioso no polling
    }
  }, [])

  const loadModels = useCallback(async () => {
    try {
      const models = await adminService.getModelsForConsole()
      setAvailableModels(models)
      if (models.length > 0) setModelId(models[0].id)
    } catch {
      // fallback: manter "pretrained"
      setAvailableModels([{ id: 'pretrained', name: 'Pré-treinado (YOLOv8n base)' }])
    }
  }, [])

  const loadIntegrations = useCallback(async () => {
    setIntLoading(true)
    try {
      const data = await adminService.getIntegrations()
      setIntegrations(data)
    } catch {
      // silencioso
    } finally {
      setIntLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadStatus()
    void loadModels()
    void loadIntegrations()
  }, [loadStatus, loadModels, loadIntegrations])

  // ── Polling quando em andamento ─────────────────────────────────────────

  useEffect(() => {
    if (status?.status === 'running') {
      pollRef.current = setInterval(() => {
        void loadStatus()
      }, 3000)
    } else {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [status?.status, loadStatus])

  // Auto-scroll log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [status?.log_lines])

  // ── Actions ─────────────────────────────────────────────────────────────

  const handleStart = async () => {
    setLoading(true)
    setActionError(null)
    try {
      await adminService.startTestConsole({
        camera_count: cameraCount,
        model_id: modelId,
        scenario_config: scenario as unknown as Record<string, unknown>,
      })
      await loadStatus()
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Erro ao iniciar teste')
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    setLoading(true)
    setActionError(null)
    try {
      await adminService.stopTestConsole()
      await loadStatus()
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Erro ao parar teste')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveIntegration = async () => {
    if (!intValue.trim()) {
      setIntError('Valor é obrigatório')
      return
    }
    setIntSaving(true)
    setIntError(null)
    setIntSuccess(false)
    try {
      await adminService.upsertIntegration(intKey, intValue, intTenantId || undefined)
      setIntSuccess(true)
      setIntValue('')
      setShowIntForm(false)
      await loadIntegrations()
      await loadStatus()
    } catch (e: unknown) {
      setIntError(e instanceof Error ? e.message : 'Erro ao salvar integração')
    } finally {
      setIntSaving(false)
    }
  }

  const toggleClass = (cls: string) => {
    setScenario((prev) => ({
      ...prev,
      classes: prev.classes.includes(cls)
        ? prev.classes.filter((c) => c !== cls)
        : [...prev.classes, cls],
    }))
  }

  const isRunning = status?.status === 'running'
  const metrics = status?.metrics

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className={s.pageRoot}>
      {/* Header */}
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Console de Teste E2E</div>
          <div className={s.pageSubtitle}>
            Dispara e acompanha o teste ponta a ponta pela plataforma, sem terminal
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span
            style={{
              padding: '4px 10px',
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 600,
              background: isRunning ? 'rgba(34,197,94,0.15)' : 'rgba(100,116,139,0.15)',
              color: isRunning ? vars.color.success : vars.color.textMuted,
            }}
          >
            {isRunning ? '● Em andamento' : status?.status === 'stopped' ? '◼ Parado' : '○ Idle'}
          </span>
        </div>
      </div>

      {/* Banner: Vast.ai não configurado */}
      {!vastConfigured && (
        <div
          className={s.alertBanner.warning}
          style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}
        >
          <AlertTriangle size={16} />
          <span>
            Configure sua chave Vast.ai em{' '}
            <button
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'inherit', textDecoration: 'underline', padding: 0,
                fontWeight: 600,
              }}
              onClick={() => setShowIntForm(true)}
            >
              Administração → Integrações
            </button>{' '}
            para habilitar instâncias de GPU cloud.
          </span>
        </div>
      )}

      {/* Action error */}
      {actionError && (
        <div className={s.alertBanner.danger} style={{ marginBottom: 16 }}>
          {actionError}
        </div>
      )}

      <div className={s.twoColumn} style={{ gap: 24 }}>
        {/* ── LEFT: Config ─────────────────────────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Câmeras simuladas */}
          <div className={s.card}>
            <div className={s.cardTitle}>Câmeras Simuladas</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <input
                type="range"
                min={1}
                max={28}
                value={cameraCount}
                disabled={isRunning}
                onChange={(e) => setCameraCount(Number(e.target.value))}
                style={{ flex: 1 }}
              />
              <span style={{ fontSize: 24, fontWeight: 700, minWidth: 40, textAlign: 'right' }}>
                {cameraCount}
              </span>
            </div>
            <div className={s.muted} style={{ fontSize: 11, marginTop: 4 }}>
              1 a 28 câmeras simultâneas
            </div>
          </div>

          {/* Seleção de modelo */}
          <div className={s.card}>
            <div className={s.cardTitle}>Modelo</div>
            <select
              value={modelId}
              disabled={isRunning}
              onChange={(e) => setModelId(e.target.value)}
              style={{
                width: '100%', padding: '8px 10px', borderRadius: 6,
                background: vars.color.bgElevated,
                color: vars.color.textPrimary,
                border: `1px solid ${vars.color.borderSubtle}`,
                fontSize: 13,
              }}
            >
              {availableModels.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
              <option value="pretrained">Pré-treinado (YOLOv8n base)</option>
            </select>
          </div>

          {/* Config de cenário */}
          <div className={s.card}>
            <div className={s.cardTitle}>Configuração de Cenário</div>

            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: vars.color.textSecondary }}>
                Classes detectadas
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {EPI_CLASSES.map((cls) => (
                  <button
                    key={cls}
                    disabled={isRunning}
                    onClick={() => toggleClass(cls)}
                    style={{
                      padding: '3px 10px', borderRadius: 12, fontSize: 11, cursor: 'pointer',
                      border: '1px solid',
                      borderColor: scenario.classes.includes(cls) ? vars.color.primary : vars.color.borderSubtle,
                      background: scenario.classes.includes(cls) ? 'rgba(59,130,246,0.15)' : 'transparent',
                      color: scenario.classes.includes(cls) ? vars.color.primary : vars.color.textMuted,
                    }}
                  >
                    {cls}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: vars.color.textSecondary }}>
                Limiar de confiança: {(scenario.confidence_threshold * 100).toFixed(0)}%
              </div>
              <input
                type="range" min={10} max={95} step={5}
                value={scenario.confidence_threshold * 100}
                disabled={isRunning}
                onChange={(e) => setScenario((p) => ({ ...p, confidence_threshold: Number(e.target.value) / 100 }))}
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: vars.color.textSecondary }}>
                Zona / ROI (descrição)
              </div>
              <input
                type="text"
                value={scenario.zone_description}
                disabled={isRunning}
                placeholder="ex: portão norte, linha de produção A..."
                onChange={(e) => setScenario((p) => ({ ...p, zone_description: e.target.value }))}
                style={{
                  width: '100%', padding: '6px 10px', borderRadius: 6, fontSize: 12,
                  background: vars.color.bgElevated,
                  color: vars.color.textPrimary,
                  border: `1px solid ${vars.color.borderSubtle}`,
                }}
              />
            </div>
          </div>

          {/* Botões Start / Stop */}
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              className={s.btnPrimary}
              style={{ flex: 1 }}
              disabled={loading || isRunning}
              onClick={() => void handleStart()}
            >
              <Play size={14} />
              {loading && !isRunning ? 'Iniciando...' : 'Iniciar Teste'}
            </button>
            <button
              className={s.btnDanger}
              style={{ flex: 1 }}
              disabled={loading || !isRunning}
              onClick={() => void handleStop()}
            >
              <Square size={14} />
              {loading && isRunning ? 'Parando...' : 'Parar'}
            </button>
          </div>
        </div>

        {/* ── RIGHT: Métricas + Log ─────────────────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Métricas ao vivo */}
          <div className={s.metricsGrid} style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
            <MetricBox
              label="Detecções/s"
              value={metrics?.detections_per_sec?.toFixed(1) ?? '—'}
              icon={<Zap size={14} />}
              active={isRunning}
            />
            <MetricBox
              label="Latência ms"
              value={metrics?.latency_ms?.toFixed(0) ?? '—'}
              icon={<Terminal size={14} />}
              active={isRunning}
            />
            <MetricBox
              label="Throughput inf/s"
              value={metrics?.throughput_infs?.toFixed(1) ?? '—'}
              icon={<Zap size={14} />}
              active={isRunning}
            />
            <MetricBox
              label="VRAM %"
              value={metrics?.vram_pct != null ? `${metrics.vram_pct.toFixed(0)}%` : '—'}
              icon={<Terminal size={14} />}
              active={isRunning}
              warn={metrics?.vram_pct != null && metrics.vram_pct > 85}
            />
          </div>

          {/* Log ao vivo */}
          <div className={s.card} style={{ flex: 1 }}>
            <div className={s.cardTitle} style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Log da Sessão</span>
              {status?.session_id && (
                <span className={s.mono} style={{ fontSize: 10 }}>
                  {status.session_id.slice(0, 8)}
                </span>
              )}
            </div>
            <div
              style={{
                background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: 12,
                fontFamily: 'monospace', fontSize: 11, lineHeight: 1.6,
                maxHeight: 260, overflowY: 'auto',
                color: vars.color.textMuted,
              }}
            >
              {(status?.log_lines ?? []).length === 0 ? (
                <span style={{ color: vars.color.textMuted }}>Nenhuma sessão iniciada.</span>
              ) : (
                (status?.log_lines ?? []).map((line, i) => (
                  <div key={i} style={{ marginBottom: 2 }}>{line}</div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>
      </div>

      {/* ── Integrações / Segredos ─────────────────────────────────────────── */}
      <div className={s.card} style={{ marginTop: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div className={s.cardTitle}>Integrações Configuradas</div>
          <button
            className={s.btnGhost}
            style={{ fontSize: 12 }}
            onClick={() => { setShowIntForm((v) => !v); setIntError(null); setIntSuccess(false) }}
          >
            {showIntForm ? 'Cancelar' : '+ Adicionar / Atualizar'}
          </button>
        </div>

        {intSuccess && (
          <div className={s.alertBanner.info} style={{ marginBottom: 12, borderColor: vars.color.success, background: 'rgba(34,197,94,0.1)' }}>
            Integração salva com sucesso.
          </div>
        )}
        {intError && (
          <div className={s.alertBanner.danger} style={{ marginBottom: 12 }}>
            {intError}
          </div>
        )}

        {/* Form de nova integração */}
        {showIntForm && (
          <div
            style={{
              background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 16,
              marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 10,
            }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div>
                <label style={{ fontSize: 11, color: vars.color.textMuted, display: 'block', marginBottom: 4 }}>
                  Chave (ex: vast_ai)
                </label>
                <input
                  type="text"
                  value={intKey}
                  onChange={(e) => setIntKey(e.target.value)}
                  placeholder="vast_ai"
                  style={{
                    width: '100%', padding: '6px 10px', borderRadius: 6, fontSize: 12,
                    background: vars.color.bgElevated,
                    color: vars.color.textPrimary,
                    border: `1px solid ${vars.color.borderSubtle}`,
                  }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: vars.color.textMuted, display: 'block', marginBottom: 4 }}>
                  Valor (cifrado ao salvar)
                </label>
                <input
                  type="password"
                  value={intValue}
                  onChange={(e) => setIntValue(e.target.value)}
                  placeholder="sk-..."
                  style={{
                    width: '100%', padding: '6px 10px', borderRadius: 6, fontSize: 12,
                    background: vars.color.bgElevated,
                    color: vars.color.textPrimary,
                    border: `1px solid ${vars.color.borderSubtle}`,
                  }}
                />
              </div>
            </div>
            <div>
              <label style={{ fontSize: 11, color: vars.color.textMuted, display: 'block', marginBottom: 4 }}>
                Tenant ID (deixe em branco para usar o tenant do seu JWT)
              </label>
              <input
                type="text"
                value={intTenantId}
                onChange={(e) => setIntTenantId(e.target.value)}
                placeholder="UUID do tenant..."
                style={{
                  width: '100%', padding: '6px 10px', borderRadius: 6, fontSize: 12,
                  background: vars.color.bgElevated,
                  color: vars.color.textPrimary,
                  border: `1px solid ${vars.color.borderSubtle}`,
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className={s.btnPrimary}
                disabled={intSaving}
                onClick={() => void handleSaveIntegration()}
              >
                {intSaving ? 'Salvando...' : 'Salvar (cifrado)'}
              </button>
              <span className={s.muted} style={{ fontSize: 11, alignSelf: 'center' }}>
                O valor nunca é retornado após salvar.
              </span>
            </div>
          </div>
        )}

        {/* Tabela de integrações */}
        {intLoading ? (
          <div className={s.muted}>Carregando...</div>
        ) : integrations.length === 0 ? (
          <div className={s.muted} style={{ padding: '12px 0' }}>
            Nenhuma integração configurada.
          </div>
        ) : (
          <table className={s.table}>
            <thead>
              <tr>
                <th className={s.th}>Chave</th>
                <th className={s.th}>Tenant</th>
                <th className={s.th}>Atualizado</th>
                <th className={s.th}>Status</th>
              </tr>
            </thead>
            <tbody>
              {integrations.map((int) => (
                <tr key={int.id} className={s.trHover}>
                  <td className={s.td}><span className={s.mono}>{int.key}</span></td>
                  <td className={s.td}>
                    <span className={s.muted}>{int.tenant_name ?? int.tenant_id}</span>
                  </td>
                  <td className={s.td}>
                    <span className={s.muted}>
                      {int.updated_at ? new Date(int.updated_at).toLocaleDateString('pt-BR') : '—'}
                    </span>
                  </td>
                  <td className={s.td}>
                    <span style={{ color: vars.color.success, fontSize: 11, fontWeight: 600 }}>
                      ● configurada
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ── Sub-component: MetricBox ─────────────────────────────────────────────────

function MetricBox({
  label, value, icon, active, warn,
}: {
  label: string
  value: string
  icon: React.ReactNode
  active: boolean
  warn?: boolean
}) {
  return (
    <div
      className={s.metricCard}
      style={{
        borderColor: warn ? 'rgba(239,68,68,0.4)' : undefined,
        opacity: active ? 1 : 0.5,
      }}
    >
      <div className={s.metricIcon}>{icon}</div>
      <div>
        <div
          style={{
            fontSize: 22, fontWeight: 700,
            color: warn ? vars.color.danger : vars.color.textPrimary,
          }}
        >
          {value}
        </div>
        <div className={s.metricLabel}>{label}</div>
      </div>
    </div>
  )
}
