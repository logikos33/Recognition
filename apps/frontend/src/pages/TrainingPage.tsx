/**
 * TrainingPage — ambiente de treino completo (deliverable f).
 *
 * Tab 1 "Imagens"     — galeria paginada de imagens de treino, upload, filtros
 * Tab 2 "Modelo"      — classes treinadas c/ métricas, botão Configurar
 * Tab 3 "Treino"      — status ao vivo (WS + polling 3s), logs, Start/Stop, histórico
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import { useToast } from '../components/ui/Toast/useToast'
import {
  Upload,
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
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { Skeleton } from '../components/ui/Skeleton/Skeleton'
import { Badge, statusToBadgeVariant } from '../components/ui/Badge/Badge'
import { Button } from '../components/ui/Button/Button'
import { useTrainingSocket } from '../hooks/useTrainingSocket'
import { useAuth } from '../hooks/useAuth'
import type { TrainingJob, TrainedModel, YoloClass, ApiResponse } from '../types'
import * as s from './TrainingPage.css'

// @ts-ignore — JSX component congelado
import AnnotationInterface from '../components/AnnotationInterface'
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

// ─── types ───────────────────────────────────────────────────────────────────

interface TrainingImage {
  id: string
  video_id: string
  frame_number: number
  filename: string
  is_annotated: boolean
  created_at: string
  video_name?: string
}

interface ImageGalleryResponse {
  frames: TrainingImage[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

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

type AnnotatedFilter = 'all' | 'yes' | 'no'

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
      <svg width={width} height={height} style={{ display: 'block', borderRadius: 4, background: 'rgba(255,255,255,0.03)' }}>
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
  const { modules } = useAuth()
  const trainingModules = ['epi', 'quality', 'counting'].filter(m => modules.includes(m))

  // ── annotation full-screen ─────────────────────────────────────────────────
  const [annotatingVideoId, setAnnotatingVideoId] = useState<string | null>(null)

  // ── Tab 1: Images ──────────────────────────────────────────────────────────
  const [images, setImages] = useState<TrainingImage[]>([])
  const [imgTotal, setImgTotal] = useState(0)
  const [imgPage, setImgPage] = useState(1)
  const [imgTotalPages, setImgTotalPages] = useState(1)
  const [imgFilter, setImgFilter] = useState<AnnotatedFilter>('all')
  const [imgLoading, setImgLoading] = useState(false)
  const [uploadingImages, setUploadingImages] = useState(false)
  const [dragOverImages, setDragOverImages] = useState(false)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const apiBase = import.meta.env.VITE_API_URL || ''

  const loadImages = useCallback(async (page: number, filter: AnnotatedFilter) => {
    setImgLoading(true)
    try {
      const params = new URLSearchParams({ page: String(page), page_size: '24' })
      if (filter === 'yes') params.set('is_annotated', 'true')
      if (filter === 'no') params.set('is_annotated', 'false')
      const res = await api.get<ApiResponse<ImageGalleryResponse>>(`/training/images?${params}`)
      const d = res?.data
      if (d) {
        setImages(d.frames || [])
        setImgTotal(d.total)
        setImgPage(d.page)
        setImgTotalPages(d.total_pages)
      }
    } catch {
      /* silent */
    } finally {
      setImgLoading(false)
    }
  }, [])

  useEffect(() => {
    loadImages(imgPage, imgFilter)
  }, [imgPage, imgFilter, loadImages])

  const uploadImages = useCallback(
    async (files: File[]) => {
      const valid = files.filter(f => /\.(jpe?g|png|webp)$/i.test(f.name))
      if (!valid.length) { toast.error('Selecione imagens JPG, PNG ou WebP'); return }
      if (valid.length > 50) { toast.error('Máximo de 50 imagens por upload'); return }
      setUploadingImages(true)
      try {
        const form = new FormData()
        valid.forEach(f => form.append('images', f))
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const res = await api.post<any>('/v1/videos/images/upload', form)
        const data = res?.data || res
        toast.success(`${data?.uploaded ?? valid.length} imagens enviadas`)
        await loadImages(1, imgFilter)
        setImgPage(1)
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : 'Erro ao enviar imagens')
      } finally {
        setUploadingImages(false)
      }
    },
    [loadImages, imgFilter, toast],
  )

  // ── Tab 2: Modelo ──────────────────────────────────────────────────────────
  const [models, setModels] = useState<TrainedModel[]>([])
  const [classes, setClasses] = useState<YoloClass[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [activating, setActivating] = useState<string | null>(null)

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

  // ── full-screen annotation ──────────────────────────────────────────────────
  if (annotatingVideoId) {
    return (
      <AnnotationInterface
        videoId={annotatingVideoId}
        onBack={() => setAnnotatingVideoId(null)}
      />
    )
  }

  // ── render ──────────────────────────────────────────────────────────────────
  return (
    <div className={s.page}>
      <div className={s.pageHeader}>
        <h2 className={s.pageTitle}>Treinamento</h2>
      </div>

      <Tabs.Root defaultValue="imagens">
        <Tabs.List className={s.tabsList}>
          <Tabs.Trigger className={s.tabsTrigger} value="imagens">
            Imagens{imgTotal > 0 ? ` (${imgTotal})` : ''}
          </Tabs.Trigger>
          <Tabs.Trigger className={s.tabsTrigger} value="modelo">Modelo</Tabs.Trigger>
          <Tabs.Trigger className={s.tabsTrigger} value="treino">Treino ao Vivo</Tabs.Trigger>
        </Tabs.List>

        {/* ── Tab 1: Imagens de Treino ────────────────────────────────────── */}
        <Tabs.Content value="imagens" className={s.tabsContent}>

          {/* Upload zone */}
          <div
            style={{
              border: `1.5px dashed ${dragOverImages ? vars.color.primaryLight : 'rgba(255,255,255,0.15)'}`,
              borderRadius: 10, padding: '14px 18px', marginBottom: 16, cursor: 'pointer',
              background: dragOverImages ? 'rgba(96,165,250,0.08)' : 'rgba(255,255,255,0.03)',
              display: 'flex', alignItems: 'center', gap: 12, transition: 'all 0.15s',
            }}
            onDragOver={e => { e.preventDefault(); setDragOverImages(true) }}
            onDragLeave={() => setDragOverImages(false)}
            onDrop={e => { e.preventDefault(); setDragOverImages(false); uploadImages(Array.from(e.dataTransfer.files)) }}
            onClick={() => imageInputRef.current?.click()}
          >
            <input
              ref={imageInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              hidden
              onChange={e => { if (e.target.files) uploadImages(Array.from(e.target.files)); e.target.value = '' }}
            />
            {uploadingImages ? (
              <><LoadingSpinner /><span style={{ fontSize: 13, color: vars.color.textMuted }}>Enviando imagens...</span></>
            ) : (
              <>
                <Upload size={18} style={{ opacity: 0.4, flexShrink: 0 }} />
                <span style={{ fontSize: 13, color: vars.color.textMuted }}>
                  Arraste imagens (JPG/PNG/WebP) ou clique — até 50 por vez
                </span>
              </>
            )}
          </div>

          {/* Filters */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: vars.color.textMuted, fontWeight: 600 }}>Filtro:</span>
            {(['all', 'yes', 'no'] as AnnotatedFilter[]).map(f => (
              <button
                key={f}
                onClick={() => { setImgFilter(f); setImgPage(1) }}
                style={{
                  padding: '4px 12px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                  cursor: 'pointer', border: '1px solid',
                  background: imgFilter === f ? vars.color.primaryDark : 'transparent',
                  color: imgFilter === f ? vars.color.textOnPrimary : vars.color.textSecondary,
                  borderColor: imgFilter === f ? vars.color.primaryDark : 'rgba(255,255,255,0.1)',
                }}
              >
                {f === 'all' ? 'Todas' : f === 'yes' ? 'Anotadas' : 'Sem anotação'}
              </button>
            ))}
            <span style={{ fontSize: 12, color: vars.color.textMuted, marginLeft: 'auto' }}>
              {imgTotal} imagem{imgTotal !== 1 ? 's' : ''}
            </span>
          </div>

          {/* Gallery grid */}
          {imgLoading ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px,1fr))', gap: 8 }}>
              {Array.from({ length: 12 }).map((_, i) => (
                <Skeleton key={i} variant="rect" width="100%" height={80} />
              ))}
            </div>
          ) : images.length === 0 ? (
            <p className={s.emptyText}>
              {imgFilter === 'all'
                ? 'Nenhuma imagem de treino. Faça upload de imagens ou envie vídeos para extração de frames.'
                : imgFilter === 'yes'
                  ? 'Nenhuma imagem anotada ainda.'
                  : 'Todas as imagens já foram anotadas.'}
            </p>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px,1fr))', gap: 8, marginBottom: 16 }}>
              {images.map(img => (
                <div
                  key={img.id}
                  style={{
                    position: 'relative', borderRadius: 6, overflow: 'hidden',
                    border: `1px solid ${img.is_annotated ? 'rgba(34,197,94,0.4)' : 'rgba(255,255,255,0.08)'}`,
                    background: vars.color.bgBase, cursor: 'pointer',
                  }}
                  onClick={() => img.video_id && setAnnotatingVideoId(img.video_id)}
                  title={img.video_name ?? img.filename}
                >
                  <img
                    src={`${apiBase}/api/training/frames/${img.id}/image`}
                    alt={img.filename}
                    loading="lazy"
                    style={{ width: '100%', height: 80, objectFit: 'cover', display: 'block' }}
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                  />
                  {img.is_annotated && (
                    <div style={{
                      position: 'absolute', bottom: 2, right: 2,
                      background: 'rgba(34,197,94,0.9)', borderRadius: '50%',
                      width: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <CheckCircle size={10} color={vars.color.textOnPrimary} />
                    </div>
                  )}
                  <div style={{ padding: '3px 4px', fontSize: 9, color: vars.color.textMuted, lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    #{img.frame_number}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {imgTotalPages > 1 && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'center', marginTop: 8 }}>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setImgPage(p => Math.max(1, p - 1))}
                disabled={imgPage <= 1}
              >
                ← Anterior
              </Button>
              <span style={{ fontSize: 12, color: vars.color.textMuted }}>
                Página {imgPage} de {imgTotalPages}
              </span>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setImgPage(p => Math.min(imgTotalPages, p + 1))}
                disabled={imgPage >= imgTotalPages}
              >
                Próxima →
              </Button>
            </div>
          )}
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
                padding: '16px 20px', background: 'rgba(255,255,255,0.04)',
                border: `1px solid ${activeModel ? 'rgba(34,197,94,0.3)' : 'rgba(255,255,255,0.08)'}`,
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
                            <MetricPill label="Precision" value={`${(activeModel.precision * 100).toFixed(1)}%`} color={vars.color.primaryLight} />
                          )}
                          {activeModel.recall != null && (
                            <MetricPill label="Recall" value={`${(activeModel.recall * 100).toFixed(1)}%`} color="#34d399" />
                          )}
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
                    onClick={() => {
                      // Link para fluxo de configuração (ScenarioEditor / ModuleClasses)
                      window.location.href = '/module-classes'
                    }}
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
                          background: 'rgba(255,255,255,0.04)',
                          border: '1px solid rgba(255,255,255,0.08)',
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
                      {(model.map50 != null || model.precision != null || model.recall != null) && (
                        <div className={s.modelMeta} style={{ marginTop: 8, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                          {model.map50 != null && (
                            <MetricPill label="mAP@50" value={`${(model.map50 * 100).toFixed(1)}%`} color="#22d3ee" />
                          )}
                          {model.precision != null && (
                            <MetricPill label="Precision" value={`${(model.precision * 100).toFixed(1)}%`} color={vars.color.primaryLight} />
                          )}
                          {model.recall != null && (
                            <MetricPill label="Recall" value={`${(model.recall * 100).toFixed(1)}%`} color="#34d399" />
                          )}
                        </div>
                      )}
                      <div style={{ fontSize: 11, color: vars.color.textMuted, marginTop: 6 }}>
                        {fmtDate(model.created_at)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </Tabs.Content>

        {/* ── Tab 3: Treino ao Vivo ───────────────────────────────────────────── */}
        <Tabs.Content value="treino" className={s.tabsContent}>

          {/* Vast.ai / GPU banner */}
          {!gpuEnabled && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
              background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)',
              borderRadius: 8, marginBottom: 16,
            }}>
              <AlertTriangle size={16} color="#f59e0b" style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: '#fbbf24' }}>
                Chave de GPU não configurada — treinos rodarão em simulação.{' '}
              </span>
              <a
                href="/admin/integrations"
                style={{ fontSize: 13, color: vars.color.primaryLight, display: 'flex', alignItems: 'center', gap: 4, textDecoration: 'none', whiteSpace: 'nowrap' }}
              >
                Administração → Integrações <ExternalLink size={11} />
              </a>
            </div>
          )}

          {/* Current job status card */}
          <div style={{
            padding: '16px 20px',
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.08)',
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
                padding: '14px 16px', background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)', borderRadius: 8, marginBottom: 16,
              }}>
                <div className={s.configGrid}>
                  <div className={s.configField}>
                    <label className={s.configLabel}>Módulo</label>
                    <select className={s.configSelect} value={cfgModule} onChange={e => setCfgModule(e.target.value)}>
                      {(trainingModules.length ? trainingModules : ['epi']).map(m => (
                        <option key={m} value={m}>{m.charAt(0).toUpperCase() + m.slice(1)}</option>
                      ))}
                    </select>
                  </div>
                  <div className={s.configField}>
                    <label className={s.configLabel}>Modelo Base</label>
                    <select className={s.configSelect} value={cfgModel} onChange={e => setCfgModel(e.target.value)}>
                      <option value="yolo26n">LGKV26n (nano)</option>
                      <option value="yolo26s">LGKV26s (small)</option>
                      <option value="yolo26m">LGKV26m (medium)</option>
                    </select>
                  </div>
                  <div className={s.configField}>
                    <label className={s.configLabel}>Epochs</label>
                    <input className={s.configInput} type="number" value={cfgEpochs} min={5} max={300}
                      onChange={e => setCfgEpochs(Number(e.target.value))} />
                  </div>
                  <div className={s.configField}>
                    <label className={s.configLabel}>Batch Size</label>
                    <input className={s.configInput} type="number" value={cfgBatch} min={1} max={64}
                      onChange={e => setCfgBatch(Number(e.target.value))} />
                  </div>
                  <div className={s.configField}>
                    <label className={s.configLabel}>Learning Rate</label>
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
                  <Badge variant={statusToBadgeVariant(currentJob.status)}>{currentJob.status}</Badge>
                  <span style={{ fontSize: 13, color: vars.color.textSecondary }}>
                    {displayModelName(currentJob.model_size)} · {currentJob.preset}
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
                      <MetricPill label="Precision" value={`${(currentJob.metrics.precision * 100).toFixed(1)}%`} color={vars.color.primaryLight} />
                    )}
                    {currentJob.metrics.recall != null && (
                      <MetricPill label="Recall" value={`${(currentJob.metrics.recall * 100).toFixed(1)}%`} color="#34d399" />
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
              border: '1px solid rgba(255,255,255,0.07)', borderRadius: 8,
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
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
                    {['Modelo', 'Preset', 'Status', 'Epochs', 'mAP@50', 'Precision', 'Recall', 'Data'].map(h => (
                      <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: vars.color.textMuted, fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {jobs.map(job => (
                    <tr
                      key={job.id}
                      style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
                    >
                      <td style={{ padding: '8px 10px', color: vars.color.borderDefault }}>{displayModelName(job.model_size)}</td>
                      <td style={{ padding: '8px 10px', color: vars.color.textSecondary }}>{job.preset}</td>
                      <td style={{ padding: '8px 10px' }}>
                        <Badge variant={statusToBadgeVariant(job.status)}>{job.status}</Badge>
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

// ─── shared sub-component ─────────────────────────────────────────────────────

function MetricPill({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
      <span style={{ fontSize: 9, color: vars.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
        {label}
      </span>
      <span style={{ fontSize: 14, fontWeight: 700, color, fontFamily: 'monospace' }}>{value}</span>
    </div>
  )
}
