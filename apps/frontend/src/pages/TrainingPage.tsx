/**
 * TrainingPage — ambiente de treino completo (deliverable f).
 *
 * Tab 1 "Imagens"     — galeria paginada de imagens de treino, upload, filtros
 * Tab 2 "Modelo"      — classes treinadas c/ métricas, botão Configurar
 * Tab 3 "Treino"      — status ao vivo (WS + polling 3s), logs, Start/Stop, histórico
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import * as Tabs from '@radix-ui/react-tabs'
import { useToast } from '../components/ui/Toast/useToast'
import {
  Play,
  Square,
  Zap,
  CheckCircle,
  Settings,
  RefreshCw,
  AlertTriangle,
  ExternalLink,
} from 'lucide-react'
import { api, getToken } from '../services/api'
import { Skeleton } from '../components/ui/Skeleton/Skeleton'
import { Badge, statusToBadgeVariant } from '../components/ui/Badge/Badge'
import { Button } from '../components/ui/Button/Button'
import { Tooltip } from '../components/ui/Tooltip/Tooltip'
import { ModelScenarioWizard } from '../components/scenario/ModelScenarioWizard'
import { useTrainingSocket } from '../hooks/useTrainingSocket'
import { useAuth } from '../hooks/useAuth'
import type { TrainingJob, TrainedModel, YoloClass, ApiResponse } from '../types'
import * as s from './TrainingPage.css'
import { InfoTooltip } from '../components/ui/InfoTooltip/InfoTooltip'
import {
  FIELD_HELP, PRESET_LABELS, TRAINING_STATUS_OVERRIDES,
  humanize, labelForModule, statusToLabel,
} from '../utils/labels'

import { AnnotationStudio } from '../components/annotation/AnnotationStudio'
import type { StudioFrame } from '../components/annotation/studioTypes'
import { PropagationStatusBar } from '../components/annotation/PropagationStatusBar'
import { dismissJob, pickJobToResurface } from '../components/annotation/propagationUi'
import { TrainingGallery, type StatusFilter } from '../components/training/TrainingGallery'
import { CoverageMatrix } from '../components/training/CoverageMatrix'
import { propagationService } from '../services/propagationService'
import { vars } from '../styles/theme.css'

// ─── helpers ─────────────────────────────────────────────────────────────────

function displayModelName(name: string): string {
  return name
    .replace(/yolo26n/gi, 'LGKV26n')
    .replace(/yolo26s/gi, 'LGKV26s')
    .replace(/yolo26m/gi, 'LGKV26m')
}

function formatEta(seconds: number): string {
  if (seconds <= 0) return ''
  const m = Math.floor(seconds / 60)
  const sec = seconds % 60
  return `${m}:${String(sec).padStart(2, '0')} restantes`
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

/** Rótulos pt-BR para a proveniência do treino (trained_models.origin — migration 090). */
const ORIGIN_LABELS: Record<string, string> = {
  vast_ai: 'GPU Vast.ai',
  ultralytics_hub: 'Ultralytics HUB',
  colab: 'Google Colab',
  simulated: 'Treino simulado',
  training_service: 'Serviço de treino',
  unknown: '—',
}

function originLabel(origin?: string): string {
  return ORIGIN_LABELS[origin ?? 'unknown'] ?? origin ?? '—'
}

/**
 * Marcação de simulação (task "treino honesto", C2) — indelével e nunca no
 * mesmo formato de uma métrica real: `origin === 'simulated'` (trained_models,
 * migration 090) OU `metrics.simulated === true` (training_jobs.metrics /
 * trained_models.metrics, JSON já existente desde a 098 — marcador escrito
 * pelo backend só quando TRAINING_SIMULATION_ENABLED roda de fato).
 */
function isSimulatedArtifact(origin?: string, metrics?: { simulated?: boolean }): boolean {
  return origin === 'simulated' || metrics?.simulated === true
}

/** Tooltips pt-BR das métricas de modelo (mAP@50 / Precision / Recall). */
const METRIC_HELP: Record<string, string> = {
  'mAP@50': 'mAP@50: acerto médio das detecções com sobreposição ≥ 50% — quanto maior, melhor',
  Precision: 'Precision: das detecções feitas, quantas estavam certas',
  Recall: 'Recall: dos objetos presentes, quantos o modelo encontrou',
}

// ─── types ───────────────────────────────────────────────────────────────────

interface CurrentJobStatus {
  job: TrainingJob | null
  gpu_enabled: boolean
  live: {
    job_id: string
    stage: string
    progress: number
    epoch: number
    metrics: Record<string, number>
    error?: string
  } | null
}

// ─── mini sparkline ───────────────────────────────────────────────────────────

interface MiniChartProps {
  data: number[]
  color: string
  label: string
  width?: number
  height?: number
}

function MiniChart({ data, color, label, width = 180, height = 44 }: MiniChartProps) {
  if (data.length < 2) return null
  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1
  const pad = 3
  const points = data
    .map(
      (v, i) =>
        `${(i / (data.length - 1)) * width},${height - pad - ((v - min) / range) * (height - pad * 2)}`,
    )
    .join(' ')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <span style={{ fontSize: 10, color: vars.color.textMuted, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </span>
      <svg width={width} height={height} style={{ display: 'block', borderRadius: 4, background: vars.color.bgCard }}>
        <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span style={{ fontSize: 11, color: vars.color.textSecondary, fontFamily: 'monospace' }}>
        {data[data.length - 1]?.toFixed(4)}
      </span>
    </div>
  )
}

// ─── main component ───────────────────────────────────────────────────────────

export function TrainingPage() {
  const toast = useToast()
  const navigate = useNavigate()
  const { modules, isSuperAdmin } = useAuth()
  const trainingModules = ['epi', 'quality', 'counting'].filter(m => modules.includes(m))

  // ── estúdio de anotação (tela cheia, lista congelada) ──────────────────────
  const [studio, setStudio] = useState<{ frames: StudioFrame[]; index: number } | null>(null)
  // Recarrega a galeria quando o estúdio fecha (anotações/curadoria mudaram).
  const [galleryReloadKey, setGalleryReloadKey] = useState(0)
  // Pedido de troca de filtro pra galeria (ver TrainingGallery.statusFilterRequest)
  // — disparado pelo "Revisar" da barra de propagação semeada.
  const [galleryFilterRequest, setGalleryFilterRequest] =
    useState<{ filter: StatusFilter; nonce: number } | null>(null)
  const requestProposalsFilter = useCallback(() => {
    setGalleryFilterRequest({ filter: 'proposta_pendente', nonce: Date.now() })
  }, [])
  // Aba ativa controlada — a matriz de cobertura leva o Vitor direto pra
  // galeria filtrada naquela câmera ("achei a lacuna → vou anotar").
  const [activeTab, setActiveTab] = useState('imagens')
  const [galleryCameraFocus, setGalleryCameraFocus] =
    useState<{ cameraId: string; nonce: number } | null>(null)
  const annotateCamera = useCallback((cameraId: string) => {
    setGalleryCameraFocus({ cameraId, nonce: Date.now() })
    setActiveTab('imagens')
  }, [])

  // ── busca de imagens iguais (propagação semeada) — barra visível mesmo
  // fora do estúdio, acima da galeria (mesmo componente/polling do Estúdio).
  const [activePropagationJob, setActivePropagationJob] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    void propagationService
      .listJobs()
      .then(jobs => {
        if (cancelled) return
        const job = pickJobToResurface(jobs)
        if (job) setActivePropagationJob(job.id)
      })
      .catch(() => { /* silent — sem job ativo reconstruído, sem problema */ })
    return () => {
      cancelled = true
    }
  }, [])

  // ── Tab 1: Imagens ─────────────────────────────────────────────────────────
  const [imgTotal, setImgTotal] = useState(0)
  const apiBase = import.meta.env.VITE_API_URL || ''

  // ── Tab 2: Modelo ──────────────────────────────────────────────────────────
  const [models, setModels] = useState<TrainedModel[]>([])
  const [classes, setClasses] = useState<YoloClass[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [activating, setActivating] = useState<string | null>(null)
  // Wizard de cenário por modelo (6 passos — PUT /training/scenarios/{id}/config)
  const [scenarioModel, setScenarioModel] = useState<TrainedModel | null>(null)

  const loadModels = useCallback(async () => {
    setModelsLoading(true)
    try {
      const [modRes, clsRes] = await Promise.allSettled([
        api.get<ApiResponse<TrainedModel[]>>('/training/models'),
        api.get<ApiResponse<YoloClass[]>>('/classes'),
      ])
      if (modRes.status === 'fulfilled') setModels(modRes.value?.data || [])
      if (clsRes.status === 'fulfilled') setClasses(clsRes.value?.data || [])
    } catch { /* silent */ } finally {
      setModelsLoading(false)
    }
  }, [])

  useEffect(() => { loadModels() }, [loadModels])

  const activateModel = async (modelId: string) => {
    setActivating(modelId)
    try {
      await api.post(`/training/models/${modelId}/activate`, {})
      toast.success('Modelo ativado')
      await loadModels()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao ativar modelo')
    } finally {
      setActivating(null)
    }
  }

  const activeModel = models.find(m => m.is_active) ?? null

  // ── Tab 3: Treino ao Vivo ──────────────────────────────────────────────────
  const [jobs, setJobs] = useState<TrainingJob[]>([])
  const [currentStatus, setCurrentStatus] = useState<CurrentJobStatus | null>(null)
  const [gpuEnabled, setGpuEnabled] = useState(true)
  const [trainLogs, setTrainLogs] = useState<string[]>([])
  const logsEndRef = useRef<HTMLDivElement>(null)

  // Config form
  const [showConfig, setShowConfig] = useState(false)
  const [cfgEpochs, setCfgEpochs] = useState(50)
  const [cfgBatch, setCfgBatch] = useState(16)
  const [cfgLr, setCfgLr] = useState(0.01)
  const [cfgModel, setCfgModel] = useState('yolo26n')
  const [cfgModule, setCfgModule] = useState(() => trainingModules[0] ?? 'epi')
  const [creating, setCreating] = useState(false)
  const [stopping, setStopping] = useState(false)

  // WebSocket for live progress
  const token = getToken() || ''
  const { jobs: liveJobs } = useTrainingSocket({ wsUrl: apiBase, token })

  // Polling 3s for current job status
  const pollCurrentStatus = useCallback(async () => {
    try {
      const res = await api.get<ApiResponse<CurrentJobStatus>>('/training/jobs/current/status')
      const d = res?.data
      if (d) {
        setCurrentStatus(d)
        setGpuEnabled(d.gpu_enabled)
        // append log entry if live data present
        if (d.live) {
          const { stage, epoch, metrics } = d.live
          const map50 = metrics?.mAP50 ?? metrics?.map50
          const loss = metrics?.loss
          const msg = [
            `[${new Date().toLocaleTimeString('pt-BR')}]`,
            `stage=${stage}`,
            epoch ? `epoch=${epoch}` : '',
            loss != null ? `loss=${Number(loss).toFixed(4)}` : '',
            map50 != null ? `mAP50=${Number(map50).toFixed(4)}` : '',
          ]
            .filter(Boolean)
            .join(' ')
          setTrainLogs(prev => [...prev.slice(-99), msg])
        }
      }
    } catch { /* silent */ }
  }, [])

  const loadJobs = useCallback(async () => {
    try {
      const res = await api.get<ApiResponse<TrainingJob[]>>('/training/jobs')
      setJobs(res?.data || [])
    } catch { /* silent */ }
  }, [])

  useEffect(() => {
    pollCurrentStatus()
    loadJobs()
  }, [pollCurrentStatus, loadJobs])

  useEffect(() => {
    const id = setInterval(pollCurrentStatus, 3000)
    return () => clearInterval(id)
  }, [pollCurrentStatus])

  // Append WS events to logs
  useEffect(() => {
    const liveEntries = Object.entries(liveJobs)
    if (!liveEntries.length) return
    const [, live] = liveEntries[liveEntries.length - 1]
    if (!live) return
    const loss = live.metrics?.loss
    const map50 = live.metrics?.map50
    const msg = [
      `[WS ${new Date().toLocaleTimeString('pt-BR')}]`,
      `status=${live.status}`,
      `epoch=${live.epoch}/${live.total_epochs}`,
      loss != null ? `loss=${Number(loss).toFixed(4)}` : '',
      map50 != null ? `mAP50=${Number(map50).toFixed(4)}` : '',
      live.eta_seconds > 0 ? formatEta(live.eta_seconds) : '',
    ]
      .filter(Boolean)
      .join(' ')
    setTrainLogs(prev => [...prev.slice(-99), msg])
  }, [liveJobs])

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [trainLogs])

  const createJob = async () => {
    setCreating(true)
    try {
      await api.post('/training/jobs', {
        preset: 'balanced',
        module: cfgModule,
        model_size: cfgModel,
        total_epochs: cfgEpochs,
        batch_size: cfgBatch,
        learning_rate: cfgLr,
      })
      toast.success('Treinamento iniciado')
      setShowConfig(false)
      setTrainLogs([])
      await Promise.all([loadJobs(), pollCurrentStatus()])
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao criar job')
    } finally {
      setCreating(false)
    }
  }

  const stopJob = async (jobId: string) => {
    setStopping(true)
    try {
      await api.post(`/training/jobs/${jobId}/stop`, {})
      toast.success('Job interrompido')
      await Promise.all([loadJobs(), pollCurrentStatus()])
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao parar job')
    } finally {
      setStopping(false)
    }
  }

  const currentJob = currentStatus?.job ?? null
  const isRunning = currentJob && ['pending', 'running'].includes(currentJob.status)
  const liveJobEntry = currentJob ? liveJobs[currentJob.id] : null

  // ── estúdio de anotação em tela cheia (lista congelada) ─────────────────────
  if (studio) {
    return (
      <AnnotationStudio
        frames={studio.frames}
        initialIndex={studio.index}
        onExit={() => {
          setStudio(null)
          setGalleryReloadKey(k => k + 1)
        }}
        onExitToProposals={() => {
          setStudio(null)
          setGalleryReloadKey(k => k + 1)
          requestProposalsFilter()
        }}
      />
    )
  }

  // ── render ──────────────────────────────────────────────────────────────────
  return (
    <div className={s.page}>
      <div className={s.pageHeader}>
        <h2 className={s.pageTitle}>Treinamento</h2>
      </div>

      <Tabs.Root value={activeTab} onValueChange={setActiveTab}>
        <Tabs.List className={s.tabsList}>
          <Tabs.Trigger className={s.tabsTrigger} value="imagens">
            Imagens{imgTotal > 0 ? ` (${imgTotal})` : ''}
          </Tabs.Trigger>
          <Tabs.Trigger className={s.tabsTrigger} value="cobertura">Cobertura</Tabs.Trigger>
          <Tabs.Trigger className={s.tabsTrigger} value="modelo">Modelo</Tabs.Trigger>
          <Tabs.Trigger className={s.tabsTrigger} value="treino">Treino ao Vivo</Tabs.Trigger>
        </Tabs.List>

        {/* ── Tab 1: Imagens de Treino ────────────────────────────────────── */}
        <Tabs.Content value="imagens" className={s.tabsContent}>
          {/* Progresso da busca de imagens iguais visível sem estar dentro
              do estúdio (mesmo componente/polling — ver AnnotationStudio). */}
          {activePropagationJob && (
            <div style={{ marginBottom: 12 }}>
              <PropagationStatusBar
                jobId={activePropagationJob}
                onReview={requestProposalsFilter}
                onClose={() => {
                  if (activePropagationJob) dismissJob(activePropagationJob)
                  setActivePropagationJob(null)
                }}
              />
            </div>
          )}
          <TrainingGallery
            reloadKey={galleryReloadKey}
            onTotalChange={setImgTotal}
            onOpenStudio={(frames, index) => setStudio({ frames, index })}
            statusFilterRequest={galleryFilterRequest}
            cameraFocusRequest={galleryCameraFocus}
          />
        </Tabs.Content>

        {/* ── Tab: Cobertura por câmera (equilíbrio da base — Volta 1) ───────── */}
        <Tabs.Content value="cobertura" className={s.tabsContent}>
          <CoverageMatrix onAnnotateCamera={annotateCamera} />
        </Tabs.Content>

        {/* ── Tab 2: Modelo ──────────────────────────────────────────────────── */}
        <Tabs.Content value="modelo" className={s.tabsContent}>
          {modelsLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} variant="rect" width="100%" height={64} />)}
            </div>
          ) : (
            <>
              {/* Active model summary */}
              <div style={{
                padding: '16px 20px', background: vars.color.bgCard,
                border: `1px solid ${activeModel ? vars.color.success : vars.color.borderDefault}`,
                borderRadius: 10, marginBottom: 20,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#f1f5f9' }}>
                      Modelo Ativo
                    </h3>
                    {activeModel ? (
                      <div style={{ marginTop: 6 }}>
                        <span style={{ fontSize: 15, fontWeight: 600, color: vars.color.primaryLight }}>
                          {displayModelName(activeModel.name)}
                        </span>
                        <div style={{ display: 'flex', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
                          {activeModel.map50 != null && (
                            <MetricPill label="mAP@50" value={`${(activeModel.map50 * 100).toFixed(1)}%`} color="#22d3ee" />
                          )}
                          {activeModel.precision != null && (
                            <MetricPill label="Precisão" value={`${(activeModel.precision * 100).toFixed(1)}%`} color={vars.color.primaryLight} />
                          )}
                          {activeModel.recall != null && (
                            <MetricPill label="Cobertura" value={`${(activeModel.recall * 100).toFixed(1)}%`} color="#34d399" />
                          )}
                        </div>
                        <div style={{ display: 'flex', gap: 12, marginTop: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                          <span style={{ fontSize: 11, color: vars.color.textMuted }}>
                            Origem: {originLabel(activeModel.origin)}
                          </span>
                          {isSimulatedArtifact(activeModel.origin, activeModel.metrics) && <SimulationBadge />}
                          <OwnerInfo model={activeModel} />
                        </div>
                        <div style={{ fontSize: 11, color: vars.color.textMuted, marginTop: 6 }}>
                          Criado em {fmtDate(activeModel.created_at)}
                        </div>
                      </div>
                    ) : (
                      <p style={{ color: vars.color.textMuted, fontSize: 13, margin: '6px 0 0' }}>
                        Nenhum modelo ativo. Ative um modelo abaixo.
                      </p>
                    )}
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => navigate('/epi/training/classes')}
                  >
                    <Settings size={13} /> Configurar Classes
                  </Button>
                </div>
              </div>

              {/* Classes section */}
              {classes.length > 0 && (
                <>
                  <h3 className={s.sectionTitle}>Classes de Detecção</h3>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(160px,1fr))',
                    gap: 8, marginBottom: 20,
                  }}>
                    {classes.map(cls => (
                      <div
                        key={cls.id}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 8,
                          padding: '10px 12px',
                          background: vars.color.bgCard,
                          border: `1px solid ${vars.color.borderDefault}`,
                          borderRadius: 8,
                        }}
                      >
                        <div style={{
                          width: 10, height: 10, borderRadius: '50%', flexShrink: 0,
                          background: cls.color || vars.color.primaryDark,
                        }} />
                        <span style={{ fontSize: 13, color: vars.color.borderDefault, fontWeight: 500 }}>{cls.name}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {/* All trained models list */}
              <h3 className={s.sectionTitle}>Modelos Treinados</h3>
              {models.length === 0 ? (
                <p className={s.emptyText}>Nenhum modelo treinado ainda. Inicie um treino na aba "Treino ao Vivo".</p>
              ) : (
                <div className={s.gridModels}>
                  {models.map(model => (
                    <div
                      key={model.id}
                      className={`${s.modelCard}${model.is_active ? ` ${s.modelCardActive}` : ''}`}
                    >
                      <div className={s.cardRow}>
                        <div>
                          <span className={s.modelName}>{displayModelName(model.name)}</span>
                          {model.is_active && (
                            <span style={{ marginLeft: 8 }}>
                              <Badge variant="success">
                                <CheckCircle size={10} style={{ marginRight: 3 }} /> ativo
                              </Badge>
                            </span>
                          )}
                        </div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => setScenarioModel(model)}
                          >
                            <Settings size={12} /> Configurar Cenário
                          </Button>
                          {!model.is_active && (
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => activateModel(model.id)}
                              disabled={activating === model.id}
                            >
                              {activating === model.id ? '...' : 'Ativar'}
                            </Button>
                          )}
                        </div>
                      </div>
                      {(model.map50 != null || model.precision != null || model.recall != null) && (
                        <div className={s.modelMeta} style={{ marginTop: 8, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                          {model.map50 != null && (
                            <MetricPill label="mAP@50" value={`${(model.map50 * 100).toFixed(1)}%`} color="#22d3ee" />
                          )}
                          {model.precision != null && (
                            <MetricPill label="Precisão" value={`${(model.precision * 100).toFixed(1)}%`} color={vars.color.primaryLight} />
                          )}
                          {model.recall != null && (
                            <MetricPill label="Cobertura" value={`${(model.recall * 100).toFixed(1)}%`} color="#34d399" />
                          )}
                        </div>
                      )}
                      <div style={{ display: 'flex', gap: 12, marginTop: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                        <span style={{ fontSize: 11, color: vars.color.textMuted }}>
                          Origem: {originLabel(model.origin)}
                        </span>
                        {isSimulatedArtifact(model.origin, model.metrics) && <SimulationBadge />}
                        <OwnerInfo model={model} />
                      </div>
                      <div style={{ fontSize: 11, color: vars.color.textMuted, marginTop: 6 }}>
                        {fmtDate(model.created_at)}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Wizard de cenário (6 passos) — componente com overlay próprio */}
              {scenarioModel && (
                <ModelScenarioWizard
                  modelId={scenarioModel.id}
                  modelName={displayModelName(scenarioModel.name)}
                  onClose={() => setScenarioModel(null)}
                  onSaved={() => {
                    toast.success('Cenário do modelo salvo')
                    loadModels()
                  }}
                />
              )}
            </>
          )}
        </Tabs.Content>

        {/* ── Tab 3: Treino ao Vivo ───────────────────────────────────────────── */}
        <Tabs.Content value="treino" className={s.tabsContent}>

          {/* Vast.ai / GPU banner — link só para superadmin (rota /admin/* é AdminRoute) */}
          {!gpuEnabled && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
              background: vars.color.warningMuted, border: `1px solid ${vars.color.warning}`,
              borderRadius: 8, marginBottom: 16,
            }}>
              <AlertTriangle size={16} color={vars.color.warning} style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: vars.color.warning }}>
                Chave de GPU não configurada — o treino vai falhar até uma GPU real ser configurada
                (não roda mais em simulação automaticamente).{' '}
              </span>
              {isSuperAdmin ? (
                <Link
                  to="/admin/integrations?type=vast_ai"
                  style={{ fontSize: 13, color: vars.color.primaryLight, display: 'flex', alignItems: 'center', gap: 4, textDecoration: 'none', whiteSpace: 'nowrap' }}
                >
                  Administração → Integrações <ExternalLink size={11} />
                </Link>
              ) : (
                <span style={{ fontSize: 13, color: vars.color.textSecondary, whiteSpace: 'nowrap' }}>
                  Solicite ao administrador da plataforma a configuração da chave de GPU.
                </span>
              )}
            </div>
          )}

          {/* Current job status card */}
          <div style={{
            padding: '16px 20px',
            background: vars.color.bgCard,
            border: `1px solid ${vars.color.borderDefault}`,
            borderRadius: 10, marginBottom: 16,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#f1f5f9' }}>
                Job Atual
              </h3>
              <div style={{ display: 'flex', gap: 8 }}>
                {isRunning && currentJob && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => stopJob(currentJob.id)}
                    disabled={stopping}
                    style={{ color: '#ef4444', borderColor: 'rgba(239,68,68,0.4)' }}
                  >
                    <Square size={12} /> {stopping ? 'Parando...' : 'Parar'}
                  </Button>
                )}
                {!isRunning && (
                  <Button variant="primary" size="sm" onClick={() => setShowConfig(v => !v)}>
                    <Zap size={13} /> Novo Treino
                  </Button>
                )}
                <button
                  onClick={() => { pollCurrentStatus(); loadJobs() }}
                  style={{ background: 'none', border: 'none', color: vars.color.textMuted, cursor: 'pointer', padding: 4 }}
                  title="Atualizar"
                >
                  <RefreshCw size={14} />
                </button>
              </div>
            </div>

            {/* Config form */}
            {showConfig && !isRunning && (
              <div style={{
                padding: '14px 16px', background: vars.color.bgCard,
                border: `1px solid ${vars.color.borderDefault}`, borderRadius: 8, marginBottom: 16,
              }}>
                <div className={s.configGrid}>
                  <div className={s.configField}>
                    <label className={s.configLabel}>Módulo <InfoTooltip text={FIELD_HELP.module} /></label>
                    <select className={s.configSelect} value={cfgModule} onChange={e => setCfgModule(e.target.value)}>
                      {(trainingModules.length ? trainingModules : ['epi']).map(m => (
                        <option key={m} value={m}>{labelForModule(m)}</option>
                      ))}
                    </select>
                  </div>
                  <div className={s.configField}>
                    <label className={s.configLabel}>Modelo Base <InfoTooltip text={FIELD_HELP.base_model} /></label>
                    <select className={s.configSelect} value={cfgModel} onChange={e => setCfgModel(e.target.value)}>
                      <option value="yolo26n">LGKV26n (nano)</option>
                      <option value="yolo26s">LGKV26s (small)</option>
                      <option value="yolo26m">LGKV26m (medium)</option>
                    </select>
                  </div>
                  <div className={s.configField}>
                    <label className={s.configLabel}>Épocas <InfoTooltip text={FIELD_HELP.epochs} /></label>
                    <input className={s.configInput} type="number" value={cfgEpochs} min={5} max={300}
                      onChange={e => setCfgEpochs(Number(e.target.value))} />
                  </div>
                  <div className={s.configField}>
                    <label className={s.configLabel}>Tamanho do lote <InfoTooltip text={FIELD_HELP.batch_size} /></label>
                    <input className={s.configInput} type="number" value={cfgBatch} min={1} max={64}
                      onChange={e => setCfgBatch(Number(e.target.value))} />
                  </div>
                  <div className={s.configField}>
                    <label className={s.configLabel}>Taxa de aprendizado <InfoTooltip text={FIELD_HELP.learning_rate} /></label>
                    <input className={s.configInput} type="number" value={cfgLr} min={0.0001} max={0.1} step={0.001}
                      onChange={e => setCfgLr(Number(e.target.value))} />
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                  <Button variant="primary" onClick={createJob} disabled={creating}>
                    <Play size={13} /> {creating ? 'Iniciando...' : 'Iniciar Treinamento'}
                  </Button>
                  <Button variant="secondary" onClick={() => setShowConfig(false)}>Cancelar</Button>
                </div>
              </div>
            )}

            {currentJob ? (
              <div>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
                  <span title={currentJob.status}>
                    <Badge variant={statusToBadgeVariant(currentJob.status)}>
                      {statusToLabel(currentJob.status, TRAINING_STATUS_OVERRIDES)}
                    </Badge>
                  </span>
                  {currentJob.metrics?.simulated === true && <SimulationBadge />}
                  <span style={{ fontSize: 13, color: vars.color.textSecondary }}>
                    {displayModelName(currentJob.model_size)} · {PRESET_LABELS[currentJob.preset] ?? humanize(currentJob.preset)}
                  </span>
                  <span style={{ fontSize: 12, color: vars.color.textMuted, marginLeft: 'auto' }}>
                    {fmtDate(currentJob.created_at)}
                  </span>
                </div>

                {/* Progress bar */}
                {(currentJob.status === 'running' || currentJob.status === 'pending') && (
                  <div className={s.progressWrap}>
                    <div className={s.progressTrack}>
                      <div
                        className={s.progressFill}
                        style={{ width: `${liveJobEntry?.progress ?? currentJob.progress}%` }}
                      />
                    </div>
                    <span className={s.progressLabel}>
                      Epoch {liveJobEntry?.epoch ?? currentJob.current_epoch}/{liveJobEntry?.total_epochs ?? currentJob.total_epochs}
                      {' '}({liveJobEntry?.progress ?? currentJob.progress}%)
                      {liveJobEntry && liveJobEntry.eta_seconds > 0 && ` · ${formatEta(liveJobEntry.eta_seconds)}`}
                    </span>
                  </div>
                )}

                {/* Live sparklines */}
                {liveJobEntry && (liveJobEntry.lossHistory.length >= 2 || liveJobEntry.map50History.length >= 2) && (
                  <div style={{ display: 'flex', gap: 20, marginTop: 12, flexWrap: 'wrap' }}>
                    {liveJobEntry.lossHistory.length >= 2 && (
                      <MiniChart data={liveJobEntry.lossHistory} color={vars.color.primaryLight} label="Loss" />
                    )}
                    {liveJobEntry.map50History.length >= 2 && (
                      <MiniChart data={liveJobEntry.map50History} color="#22d3ee" label="mAP@50" />
                    )}
                  </div>
                )}

                {/* Completed metrics */}
                {currentJob.status === 'completed' && currentJob.metrics && Object.keys(currentJob.metrics).length > 0 && (
                  <div style={{ display: 'flex', gap: 12, marginTop: 10, flexWrap: 'wrap' }}>
                    {currentJob.metrics.map50 != null && (
                      <MetricPill label="mAP@50" value={`${(currentJob.metrics.map50 * 100).toFixed(1)}%`} color="#22d3ee" />
                    )}
                    {currentJob.metrics.precision != null && (
                      <MetricPill label="Precisão" value={`${(currentJob.metrics.precision * 100).toFixed(1)}%`} color={vars.color.primaryLight} />
                    )}
                    {currentJob.metrics.recall != null && (
                      <MetricPill label="Cobertura" value={`${(currentJob.metrics.recall * 100).toFixed(1)}%`} color="#34d399" />
                    )}
                  </div>
                )}

                {currentJob.status === 'failed' && currentJob.error_message && (
                  <div style={{ marginTop: 8, padding: '8px 10px', background: 'rgba(239,68,68,0.08)', borderRadius: 6, fontSize: 12, color: '#f87171' }}>
                    {currentJob.error_message}
                  </div>
                )}
              </div>
            ) : (
              <p style={{ color: vars.color.textMuted, fontSize: 13, margin: 0 }}>
                Nenhum job em andamento. Clique em "Novo Treino" para iniciar.
              </p>
            )}
          </div>

          {/* Log stream */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: vars.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Log de Eventos
              </span>
              <button
                onClick={() => setTrainLogs([])}
                style={{ background: 'none', border: 'none', color: vars.color.textMuted, fontSize: 11, cursor: 'pointer' }}
              >
                limpar
              </button>
            </div>
            <div style={{
              height: 180, overflowY: 'auto', background: '#0a0f1a',
              border: `1px solid ${vars.color.borderDefault}`, borderRadius: 8,
              padding: '8px 10px', fontFamily: 'monospace', fontSize: 11, color: vars.color.textMuted,
              scrollbarWidth: 'thin',
            }}>
              {trainLogs.length === 0 ? (
                <span style={{ color: vars.color.borderStrong }}>Aguardando eventos de treinamento...</span>
              ) : (
                trainLogs.map((line, i) => (
                  <div key={i} style={{ color: line.startsWith('[WS') ? vars.color.primaryLight : vars.color.textSecondary, lineHeight: 1.6 }}>
                    {line}
                  </div>
                ))
              )}
              <div ref={logsEndRef} />
            </div>
          </div>

          {/* Job history table */}
          <h3 className={s.sectionTitle}>Histórico de Treinos</h3>
          {jobs.length === 0 ? (
            <p className={s.emptyText}>Nenhum job de treinamento ainda.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${vars.color.borderDefault}` }}>
                    {([
                      { label: 'Modelo' },
                      { label: 'Preset' },
                      { label: 'Status' },
                      { label: 'Épocas', hint: FIELD_HELP.epochs },
                      { label: 'mAP@50', hint: FIELD_HELP.map50 },
                      { label: 'Precisão', hint: FIELD_HELP.precision },
                      { label: 'Cobertura', hint: FIELD_HELP.recall },
                      { label: 'Data' },
                    ] as { label: string; hint?: string }[]).map(h => (
                      <th key={h.label} style={{ padding: '6px 10px', textAlign: 'left', color: vars.color.textMuted, fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        {h.label}
                        {h.hint && <InfoTooltip text={h.hint} />}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {jobs.map(job => (
                    <tr
                      key={job.id}
                      style={{ borderBottom: `1px solid ${vars.color.borderSubtle}` }}
                    >
                      <td style={{ padding: '8px 10px', color: vars.color.borderDefault }}>{displayModelName(job.model_size)}</td>
                      <td style={{ padding: '8px 10px', color: vars.color.textSecondary }}>{PRESET_LABELS[job.preset] ?? humanize(job.preset)}</td>
                      <td style={{ padding: '8px 10px' }}>
                        <span title={job.status} style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                          <Badge variant={statusToBadgeVariant(job.status)}>
                            {statusToLabel(job.status, TRAINING_STATUS_OVERRIDES)}
                          </Badge>
                          {job.metrics?.simulated === true && <SimulationBadge />}
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px', color: vars.color.textSecondary }}>
                        {job.current_epoch}/{job.total_epochs}
                      </td>
                      <td style={{ padding: '8px 10px', color: '#22d3ee', fontFamily: 'monospace' }}>
                        {job.metrics?.map50 != null ? `${(job.metrics.map50 * 100).toFixed(1)}%` : '—'}
                      </td>
                      <td style={{ padding: '8px 10px', color: vars.color.primaryLight, fontFamily: 'monospace' }}>
                        {job.metrics?.precision != null ? `${(job.metrics.precision * 100).toFixed(1)}%` : '—'}
                      </td>
                      <td style={{ padding: '8px 10px', color: '#34d399', fontFamily: 'monospace' }}>
                        {job.metrics?.recall != null ? `${(job.metrics.recall * 100).toFixed(1)}%` : '—'}
                      </td>
                      <td style={{ padding: '8px 10px', color: vars.color.textMuted, whiteSpace: 'nowrap' }}>
                        {fmtDate(job.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Tabs.Content>
      </Tabs.Root>
    </div>
  )
}

// ─── shared sub-components ────────────────────────────────────────────────────

/**
 * Marcação visual inconfundível de simulação (task "treino honesto", C2) —
 * NUNCA no mesmo formato de uma métrica real (MetricPill). Badge "danger"
 * (vermelho) propositalmente destoante das cores de sucesso/primário usadas
 * pelas métricas reais.
 */
function SimulationBadge() {
  return (
    <Badge variant="danger">
      <AlertTriangle size={10} style={{ marginRight: 3 }} /> SIMULAÇÃO — não é um treino real
    </Badge>
  )
}

function MetricPill({ label, value, color }: { label: string; value: string; color: string }) {
  const pill = (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
      <span style={{ fontSize: 9, color: vars.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
        {label}
      </span>
      <span style={{ fontSize: 14, fontWeight: 700, color, fontFamily: 'monospace' }}>{value}</span>
    </div>
  )
  const help = METRIC_HELP[label]
  if (!help) return pill
  return <Tooltip label={help}>{pill}</Tooltip>
}

/** Dono do modelo — nome com Tooltip exibindo o email (quando disponível). */
function OwnerInfo({ model }: { model: TrainedModel }) {
  const name = model.owner_name ?? '—'
  const text = (
    <span style={{ fontSize: 11, color: vars.color.textMuted }}>
      Dono: {name}
    </span>
  )
  if (!model.owner_email) return text
  return <Tooltip label={model.owner_email}>{text}</Tooltip>
}
