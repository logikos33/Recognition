/**
 * AdminTestConsolePage — Console de Teste E2E (task-056, WS5)
 *
 * Permite ao superadmin disparar e acompanhar um teste ponta a ponta
 * diretamente pela plataforma, sem terminal.
 *
 * Contrato de Operabilidade (task-056 + WS5):
 *   - Chave Vast.ai: configurada em Integrações (banner com deep link)
 *   - Nº de câmeras simuladas: seletor 1–28
 *   - FPS: padrão (1–30) + ajuste individual por câmera (default_fps/camera_fps)
 *   - Seleção de modelo: dropdown dos modelos treinados reais do tenant
 *   - Config cenário: classes EPI (rótulos pt-BR) + limiar + zona/ROI +
 *     botão "Carregar cenário do modelo" (GET /training/scenarios/{id}/config)
 *   - Ações: Start / Stop com estados loading/erro/sucesso
 *   - Métricas ao vivo com tooltips explicativos em pt-BR
 *   - Integrações: superfície read-only com status REAL (ok/error/unconfigured)
 *     e deep link para /admin/integrations (fonte única de gestão)
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Play, Square, Terminal, Zap } from 'lucide-react'
import { adminService } from '../services/adminService'
import type { TestConsoleStatus, Integration } from '../types/admin'
import * as s from '../components/admin.css'
import { vars } from '../../../styles/theme.css'
import { Tooltip } from '../../../components/ui/Tooltip/Tooltip'
import { Badge } from '../../../components/ui/Badge/Badge'
import { EPI_CLASS_OPTIONS } from '../../../constants/epiClasses'
import { integrationSpec } from '../constants/integrationCatalog'

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

const FPS_MIN = 1
const FPS_MAX = 30
const FPS_DEFAULT = 5

const clampFps = (v: number): number =>
  Math.min(FPS_MAX, Math.max(FPS_MIN, Math.round(Number.isFinite(v) ? v : FPS_DEFAULT)))

// Tooltips pt-BR das métricas ao vivo (WS5)
const METRIC_HELP = {
  detections: 'Objetos detectados por segundo somando todas as câmeras do teste',
  latency: 'Tempo médio entre o frame chegar e a detecção sair — alvo < 3000 ms',
  throughput: 'Inferências do modelo por segundo (capacidade de processamento da GPU)',
  vram: 'Memória de vídeo da GPU em uso — acima de 85% há risco de degradação',
} as const

// ── Component ────────────────────────────────────────────────────────────────

export function AdminTestConsolePage() {
  const navigate = useNavigate()

  // Config state
  const [cameraCount, setCameraCount] = useState(1)
  const [modelId, setModelId] = useState('pretrained')
  const [scenario, setScenario] = useState<ScenarioConfig>(DEFAULT_SCENARIO)
  const [availableModels, setAvailableModels] = useState<{ id: string; name: string }[]>([])

  // FPS state (WS5 — default_fps / camera_fps, alinhado ao WS10)
  const [defaultFps, setDefaultFps] = useState(FPS_DEFAULT)
  const [perCameraFps, setPerCameraFps] = useState(false)
  const [cameraFps, setCameraFps] = useState<number[]>([FPS_DEFAULT])

  // Cenário do modelo (carregado da aba Modelo do Treino)
  const [scenarioLoading, setScenarioLoading] = useState(false)
  const [scenarioLoadMsg, setScenarioLoadMsg] = useState<
    { kind: 'success' | 'warning' | 'error'; text: string } | null
  >(null)

  // Console session state
  const [status, setStatus] = useState<TestConsoleStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [vastConfigured, setVastConfigured] = useState(false)

  // Integrations (read-only — gestão em /admin/integrations)
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [intLoading, setIntLoading] = useState(false)

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
      setAvailableModels([])
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

  // Ressincroniza cameraFps quando cameraCount muda (novos índices = defaultFps)
  useEffect(() => {
    setCameraFps((prev) => {
      if (prev.length === cameraCount) return prev
      if (prev.length > cameraCount) return prev.slice(0, cameraCount)
      return [...prev, ...Array(cameraCount - prev.length).fill(defaultFps)]
    })
  }, [cameraCount, defaultFps])

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
        default_fps: defaultFps,
        ...(perCameraFps
          ? { camera_fps: cameraFps.slice(0, cameraCount).map(clampFps) }
          : {}),
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

  /** Pré-preenche o cenário com a config salva do modelo selecionado. */
  const handleLoadModelScenario = async () => {
    setScenarioLoading(true)
    setScenarioLoadMsg(null)
    try {
      const res = await adminService.getModelScenarioConfig(modelId)
      const cfg = res.scenario_config
      if (!cfg) {
        setScenarioLoadMsg({
          kind: 'warning',
          text: 'Este modelo ainda não tem cenário salvo — configure na aba Modelo do Treino.',
        })
        return
      }
      const parts: string[] = []
      if (Array.isArray(cfg.roi) && cfg.roi.length >= 3) parts.push(`ROI com ${cfg.roi.length} pontos`)
      if (cfg.counting_line) parts.push('linha de contagem definida')
      if (cfg.camera_id) parts.push('câmera vinculada')
      setScenario({
        classes: cfg.classes ?? [],
        confidence_threshold: cfg.confidence_threshold ?? 0.5,
        zone_description: parts.join(' · '),
      })
      setScenarioLoadMsg({ kind: 'success', text: 'Cenário do modelo carregado.' })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : ''
      setScenarioLoadMsg({
        kind: 'error',
        text: msg.toLowerCase().includes('não encontrado')
          ? 'Este modelo ainda não tem cenário salvo — configure na aba Modelo do Treino.'
          : 'Erro ao carregar cenário do modelo.',
      })
    } finally {
      setScenarioLoading(false)
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

  const applyFpsToAll = () => {
    setCameraFps(Array(cameraCount).fill(defaultFps))
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
              background: isRunning ? vars.color.successMuted : vars.color.bgElevated,
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
              onClick={() => navigate('/admin/integrations')}
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

            {/* FPS padrão (WS5) */}
            <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
              <Tooltip label="Frames por segundo processados por câmera — valores maiores aumentam carga de GPU">
                <label
                  htmlFor="default-fps"
                  style={{ fontSize: 12, fontWeight: 600, color: vars.color.textSecondary, cursor: 'help' }}
                >
                  FPS padrão
                </label>
              </Tooltip>
              <input
                id="default-fps"
                type="number"
                min={FPS_MIN}
                max={FPS_MAX}
                step={1}
                value={defaultFps}
                disabled={isRunning}
                onChange={(e) => setDefaultFps(clampFps(Number(e.target.value)))}
                style={{
                  width: 72, padding: '6px 8px', borderRadius: 6, fontSize: 13,
                  background: vars.color.bgElevated,
                  color: vars.color.textPrimary,
                  border: `1px solid ${vars.color.borderSubtle}`,
                }}
              />
              <span className={s.muted} style={{ fontSize: 11 }}>1–30</span>
            </div>

            {/* Ajuste de FPS por câmera */}
            <div style={{ marginTop: 10 }}>
              <label
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  fontSize: 12, color: vars.color.textSecondary,
                  cursor: isRunning ? 'not-allowed' : 'pointer', userSelect: 'none',
                }}
              >
                <input
                  type="checkbox"
                  checked={perCameraFps}
                  disabled={isRunning}
                  onChange={(e) => setPerCameraFps(e.target.checked)}
                />
                Ajustar FPS por câmera
              </label>

              {perCameraFps && (
                <div style={{ marginTop: 10 }}>
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(4, 1fr)',
                      gap: 6,
                      maxHeight: 180,
                      overflowY: 'auto',
                    }}
                  >
                    {Array.from({ length: cameraCount }).map((_, i) => (
                      <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span className={s.muted} style={{ fontSize: 10 }}>Cam {i + 1}</span>
                        <input
                          type="number"
                          min={FPS_MIN}
                          max={FPS_MAX}
                          step={1}
                          value={cameraFps[i] ?? defaultFps}
                          disabled={isRunning}
                          aria-label={`FPS da câmera ${i + 1}`}
                          onChange={(e) => {
                            const v = clampFps(Number(e.target.value))
                            setCameraFps((prev) => {
                              const next = [...prev]
                              next[i] = v
                              return next
                            })
                          }}
                          style={{
                            width: '100%', padding: '4px 6px', borderRadius: 6, fontSize: 12,
                            background: vars.color.bgElevated,
                            color: vars.color.textPrimary,
                            border: `1px solid ${vars.color.borderSubtle}`,
                          }}
                        />
                      </div>
                    ))}
                  </div>
                  <button
                    className={s.btnGhost}
                    style={{ fontSize: 11, marginTop: 8 }}
                    disabled={isRunning}
                    onClick={applyFpsToAll}
                  >
                    Aplicar a todas
                  </button>
                </div>
              )}
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
              <option value="pretrained">Pré-treinado (modelo base do sistema)</option>
            </select>
          </div>

          {/* Config de cenário */}
          <div className={s.card}>
            <div
              className={s.cardTitle}
              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
            >
              <span>Configuração de Cenário</span>
              {modelId !== 'pretrained' && (
                <button
                  className={s.btnGhost}
                  style={{ fontSize: 11 }}
                  disabled={isRunning || scenarioLoading}
                  onClick={() => void handleLoadModelScenario()}
                >
                  {scenarioLoading ? 'Carregando...' : 'Carregar cenário do modelo'}
                </button>
              )}
            </div>

            {scenarioLoadMsg && (
              <div
                className={
                  scenarioLoadMsg.kind === 'error'
                    ? s.alertBanner.danger
                    : scenarioLoadMsg.kind === 'warning'
                      ? s.alertBanner.warning
                      : s.alertBanner.info
                }
                style={{ marginBottom: 12, fontSize: 12 }}
              >
                {scenarioLoadMsg.text}
              </div>
            )}

            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: vars.color.textSecondary }}>
                Classes detectadas
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {EPI_CLASS_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    disabled={isRunning}
                    onClick={() => toggleClass(opt.value)}
                    style={{
                      padding: '3px 10px', borderRadius: 12, fontSize: 11, cursor: 'pointer',
                      border: '1px solid',
                      borderColor: scenario.classes.includes(opt.value) ? vars.color.primary : vars.color.borderSubtle,
                      background: scenario.classes.includes(opt.value) ? vars.color.primaryAlpha : 'transparent',
                      color: scenario.classes.includes(opt.value) ? vars.color.primary : vars.color.textMuted,
                    }}
                  >
                    {opt.label}
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
              help={METRIC_HELP.detections}
            />
            <MetricBox
              label="Latência ms"
              value={metrics?.latency_ms?.toFixed(0) ?? '—'}
              icon={<Terminal size={14} />}
              active={isRunning}
              help={METRIC_HELP.latency}
            />
            <MetricBox
              label="Throughput inf/s"
              value={metrics?.throughput_infs?.toFixed(1) ?? '—'}
              icon={<Zap size={14} />}
              active={isRunning}
              help={METRIC_HELP.throughput}
            />
            <MetricBox
              label="VRAM %"
              value={metrics?.vram_pct != null ? `${metrics.vram_pct.toFixed(0)}%` : '—'}
              icon={<Terminal size={14} />}
              active={isRunning}
              warn={metrics?.vram_pct != null && metrics.vram_pct > 85}
              help={METRIC_HELP.vram}
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
                background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: 12, // allow: console de teste escuro intencional
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

      {/* ── Integrações (read-only — gestão em /admin/integrations) ─────────── */}
      <div className={s.card} style={{ marginTop: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div className={s.cardTitle}>Integrações Configuradas</div>
          <button
            className={s.btnGhost}
            style={{ fontSize: 12 }}
            onClick={() => navigate('/admin/integrations')}
          >
            Gerenciar em Integrações
          </button>
        </div>

        {/* Tabela de integrações — status REAL do banco (082) */}
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
                <th className={s.th}>Integração</th>
                <th className={s.th}>Descrição</th>
                <th className={s.th}>Segredo</th>
                <th className={s.th}>Status</th>
                <th className={s.th}>Último teste</th>
              </tr>
            </thead>
            <tbody>
              {integrations.map((int) => {
                const spec = integrationSpec(int.integration_type)
                return (
                  <tr key={int.id} className={s.trHover}>
                    <td className={s.td}>
                      <span style={{ fontWeight: 600 }}>
                        {spec?.title ?? int.integration_type}
                      </span>
                    </td>
                    <td className={s.td}>
                      <span className={s.muted}>{spec?.description ?? int.label}</span>
                    </td>
                    <td className={s.td}>
                      <span className={s.mono}>{int.secret_display ?? '—'}</span>
                    </td>
                    <td className={s.td}>
                      <IntegrationStatusBadge status={int.status} lastError={int.last_error} />
                    </td>
                    <td className={s.td}>
                      <span className={s.muted}>
                        {int.last_tested_at
                          ? new Date(int.last_tested_at).toLocaleString('pt-BR')
                          : '—'}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ── Sub-component: IntegrationStatusBadge ────────────────────────────────────

function IntegrationStatusBadge({
  status, lastError,
}: {
  status: Integration['status']
  lastError: string | null
}) {
  if (status === 'ok') return <Badge variant="success">Conectada</Badge>
  if (status === 'error') {
    const badge = <Badge variant="danger">Erro</Badge>
    if (!lastError) return badge
    return (
      <Tooltip label={lastError}>
        <span style={{ display: 'inline-flex' }}>{badge}</span>
      </Tooltip>
    )
  }
  return <Badge variant="neutral">Não configurada</Badge>
}

// ── Sub-component: MetricBox ─────────────────────────────────────────────────

function MetricBox({
  label, value, icon, active, warn, help,
}: {
  label: string
  value: string
  icon: React.ReactNode
  active: boolean
  warn?: boolean
  help?: string
}) {
  const box = (
    <div
      className={s.metricCard}
      style={{
        borderColor: warn ? vars.color.danger : undefined,
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
  if (!help) return box
  return <Tooltip label={help}>{box}</Tooltip>
}
