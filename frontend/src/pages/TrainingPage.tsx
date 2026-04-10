/**
 * TrainingPage — unified training view with sub-tabs: Dados, Treinar, Modelos.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import toast from 'react-hot-toast'
import { Upload, Play, Zap, CheckCircle } from 'lucide-react'
import { api, getToken } from '../services/api'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { Badge, statusToBadge } from '../components/ui/Badge/Badge'
import { Button } from '../components/ui/Button/Button'
import type { TrainingJob, TrainedModel, Video, ApiResponse } from '../types'
import * as s from './TrainingPage.css'

// @ts-ignore — JSX component congelado
import AnnotationInterface from '../components/AnnotationInterface'

function displayModelName(name: string): string {
  return name.replace(/yolov8n/gi, 'LGKV8n')
}

export function TrainingPage() {
  const [jobs, setJobs] = useState<TrainingJob[]>([])
  const [models, setModels] = useState<TrainedModel[]>([])
  const [videos, setVideos] = useState<Video[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null)

  // Upload state
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Training config form
  const [showConfig, setShowConfig] = useState(false)
  const [cfgPreset, setCfgPreset] = useState('balanced')
  const [cfgModelSize, setCfgModelSize] = useState('yolov8n')
  const [cfgEpochs, setCfgEpochs] = useState(50)
  const [cfgBatch, setCfgBatch] = useState(16)
  const [cfgImgSize, setCfgImgSize] = useState(640)
  const [creating, setCreating] = useState(false)
  const [activating, setActivating] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      const [jobsRes, modelsRes, videosRes] = await Promise.allSettled([
        api.get<ApiResponse<TrainingJob[]>>('/training/jobs'),
        api.get<ApiResponse<TrainedModel[]>>('/training/models'),
        api.get<ApiResponse<Video[]>>('/training/videos'),
      ])
      if (jobsRes.status === 'fulfilled') setJobs(jobsRes.value.data || [])
      if (modelsRes.status === 'fulfilled') setModels(modelsRes.value.data || [])
      if (videosRes.status === 'fulfilled') setVideos(videosRes.value.data || [])
    } catch (err) {
      console.error('Failed to load training data:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  // Upload video
  const uploadFile = useCallback(async (file: File) => {
    if (!file.type.startsWith('video/')) {
      toast.error('Selecione um arquivo de video')
      return
    }
    setUploading(true)
    setUploadProgress(0)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const xhr = new XMLHttpRequest()
      const apiBase = import.meta.env.VITE_API_URL || ''
      xhr.open('POST', `${apiBase}/api/v1/videos/upload`)
      const token = getToken()
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) setUploadProgress(Math.round((e.loaded / e.total) * 100))
      }
      xhr.onload = () => {
        setUploading(false)
        if (xhr.status >= 200 && xhr.status < 300) {
          toast.success('Video enviado com sucesso')
          loadData()
        } else {
          toast.error('Erro ao enviar video')
        }
      }
      xhr.onerror = () => { setUploading(false); toast.error('Erro de conexao ao enviar video') }
      xhr.send(formData)
    } catch {
      setUploading(false)
      toast.error('Erro ao enviar video')
    }
  }, [loadData])

  const handleFileDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) uploadFile(file)
  }, [uploadFile])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) uploadFile(file)
    e.target.value = ''
  }, [uploadFile])

  // Extract frames
  const extractFrames = useCallback(async (videoId: string) => {
    try {
      await api.post(`/training/videos/${videoId}/extract`, {})
      toast.success('Extracao de frames iniciada')
      loadData()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao extrair frames')
    }
  }, [loadData])

  // Create training job
  const createJob = async () => {
    setCreating(true)
    try {
      await api.post('/training/jobs', {
        preset: cfgPreset,
        model_size: cfgModelSize,
        total_epochs: cfgEpochs,
        batch_size: cfgBatch,
        img_size: cfgImgSize,
      })
      toast.success('Treinamento iniciado')
      setShowConfig(false)
      await loadData()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao criar job')
    } finally {
      setCreating(false)
    }
  }

  // Activate model
  const activateModel = async (modelId: string) => {
    setActivating(modelId)
    try {
      await api.post(`/training/models/${modelId}/activate`, {})
      toast.success('Modelo ativado')
      await loadData()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao ativar modelo')
    } finally {
      setActivating(null)
    }
  }

  // If annotating a video, render full-screen annotation interface
  if (selectedVideoId) {
    return (
      <AnnotationInterface
        videoId={selectedVideoId}
        onBack={() => setSelectedVideoId(null)}
      />
    )
  }

  if (loading) return <LoadingSpinner />

  const extractedVideos = videos.filter(v => v.status === 'extracted')
  const uploadedVideos = videos.filter(v => v.status === 'uploaded')
  const extractingVideos = videos.filter(v => v.status === 'extracting')

  return (
    <div className={s.page}>
      <div className={s.pageHeader}>
        <h2 className={s.pageTitle}>Treinamento</h2>
      </div>

      <Tabs.Root defaultValue="dados">
        <Tabs.List className={s.tabsList}>
          <Tabs.Trigger className={s.tabsTrigger} value="dados">Dados</Tabs.Trigger>
          <Tabs.Trigger className={s.tabsTrigger} value="treinar">Treinar</Tabs.Trigger>
          <Tabs.Trigger className={s.tabsTrigger} value="modelos">Modelos</Tabs.Trigger>
        </Tabs.List>

        {/* Tab: Dados — upload + videos + annotation */}
        <Tabs.Content value="dados" className={s.tabsContent}>
          {/* Upload area */}
          <div
            className={`${s.uploadZone}${dragOver ? ` ${s.uploadZoneActive}` : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleFileDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input ref={fileInputRef} type="file" accept="video/*" hidden onChange={handleFileSelect} />
            {uploading ? (
              <>
                <div className={s.uploadProgressTrack}>
                  <div className={s.uploadProgressFill} style={{ width: `${uploadProgress}%` }} />
                </div>
                <span className={s.uploadText}>Enviando... {uploadProgress}%</span>
              </>
            ) : (
              <>
                <Upload size={28} style={{ opacity: 0.4 }} />
                <span className={s.uploadText}>Arraste um video ou clique para selecionar</span>
              </>
            )}
          </div>

          {/* Uploaded videos (pending extraction) */}
          {uploadedVideos.length > 0 && (
            <>
              <h3 className={s.sectionTitle}>Aguardando extracao</h3>
              <div className={s.grid}>
                {uploadedVideos.map(video => (
                  <div key={video.id} className={s.jobCard}>
                    <div className={s.cardRow}>
                      <span className={s.jobName}>{video.original_filename || video.filename}</span>
                      <Button size="sm" variant="secondary" onClick={() => extractFrames(video.id)}>
                        <Play size={12} /> Extrair Frames
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Extracting */}
          {extractingVideos.length > 0 && (
            <>
              <h3 className={s.sectionTitle}>Extraindo frames...</h3>
              <div className={s.grid}>
                {extractingVideos.map(video => (
                  <div key={video.id} className={s.jobCard}>
                    <div className={s.cardRow}>
                      <span className={s.jobName}>{video.original_filename || video.filename}</span>
                      <Badge status="warning">extraindo</Badge>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Extracted — ready for annotation */}
          <h3 className={s.sectionTitle}>Prontos para anotacao</h3>
          {extractedVideos.length === 0 ? (
            <p className={s.emptyText}>Nenhum video com frames extraidos. Faca upload e extraia frames.</p>
          ) : (
            <div className={s.grid}>
              {extractedVideos.map(video => (
                <div
                  key={video.id}
                  onClick={() => setSelectedVideoId(video.id)}
                  className={s.jobCard}
                  style={{ cursor: 'pointer' }}
                >
                  <div className={s.cardRow}>
                    <div>
                      <span className={s.jobName}>{video.original_filename || video.filename}</span>
                      <span className={s.jobPreset}>{video.frame_count} frames</span>
                    </div>
                    <Badge status={statusToBadge(video.status)}>{video.status}</Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Tabs.Content>

        {/* Tab: Treinar — config + jobs */}
        <Tabs.Content value="treinar" className={s.tabsContent}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 className={s.sectionTitle} style={{ margin: 0 }}>Jobs de Treinamento</h3>
            <Button variant="primary" onClick={() => setShowConfig(true)}>
              <Zap size={14} /> Novo Treinamento
            </Button>
          </div>

          {/* Config form */}
          {showConfig && (
            <div className={s.configPanel}>
              <h4 className={s.configTitle}>Configuracao de Treinamento</h4>
              <div className={s.configGrid}>
                <div className={s.configField}>
                  <label className={s.configLabel}>Preset</label>
                  <select className={s.configSelect} value={cfgPreset} onChange={e => setCfgPreset(e.target.value)}>
                    <option value="fast">Rapido (~30min)</option>
                    <option value="balanced">Balanceado (~2h)</option>
                    <option value="quality">Qualidade (~6h)</option>
                  </select>
                </div>
                <div className={s.configField}>
                  <label className={s.configLabel}>Modelo Base</label>
                  <select className={s.configSelect} value={cfgModelSize} onChange={e => setCfgModelSize(e.target.value)}>
                    <option value="yolov8n">LGKV8n (nano)</option>
                    <option value="yolov8s">LGKV8s (small)</option>
                    <option value="yolov8m">LGKV8m (medium)</option>
                  </select>
                </div>
                <div className={s.configField}>
                  <label className={s.configLabel}>Epochs</label>
                  <input className={s.configInput} type="number" value={cfgEpochs} onChange={e => setCfgEpochs(Number(e.target.value))} min={5} max={300} />
                </div>
                <div className={s.configField}>
                  <label className={s.configLabel}>Batch Size</label>
                  <input className={s.configInput} type="number" value={cfgBatch} onChange={e => setCfgBatch(Number(e.target.value))} min={1} max={64} />
                </div>
                <div className={s.configField}>
                  <label className={s.configLabel}>Img Size</label>
                  <input className={s.configInput} type="number" value={cfgImgSize} onChange={e => setCfgImgSize(Number(e.target.value))} min={320} max={1280} step={32} />
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                <Button variant="primary" onClick={createJob} disabled={creating}>
                  {creating ? 'Criando...' : 'Iniciar Treinamento'}
                </Button>
                <Button variant="secondary" onClick={() => setShowConfig(false)}>Cancelar</Button>
              </div>
            </div>
          )}

          {jobs.length === 0 ? (
            <p className={s.emptyText}>Nenhum job de treinamento ainda.</p>
          ) : (
            <div className={s.grid}>
              {jobs.map(job => (
                <div key={job.id} className={s.jobCard}>
                  <div className={s.cardRow}>
                    <div>
                      <span className={s.jobName}>{displayModelName(job.model_size)}</span>
                      <span className={s.jobPreset}>Preset: {job.preset}</span>
                    </div>
                    <Badge status={statusToBadge(job.status)}>{job.status}</Badge>
                  </div>
                  {(job.status === 'running' || job.status === 'pending') && (
                    <div className={s.progressWrap}>
                      <div className={s.progressTrack}>
                        <div className={s.progressFill} style={{ width: `${job.progress}%` }} />
                      </div>
                      <span className={s.progressLabel}>
                        Epoch {job.current_epoch}/{job.total_epochs} ({job.progress}%)
                      </span>
                    </div>
                  )}
                  {job.status === 'completed' && job.metrics && Object.keys(job.metrics).length > 0 && (
                    <div className={s.modelMeta}>
                      {job.metrics.map50 != null && `mAP@50: ${(job.metrics.map50 * 100).toFixed(1)}%`}
                      {job.metrics.precision != null && ` | Precision: ${(job.metrics.precision * 100).toFixed(1)}%`}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Tabs.Content>

        {/* Tab: Modelos */}
        <Tabs.Content value="modelos" className={s.tabsContent}>
          <h3 className={s.sectionTitle}>Modelos Treinados</h3>
          {models.length === 0 ? (
            <p className={s.emptyText}>Nenhum modelo treinado ainda.</p>
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
                        <Badge status="active">
                          <CheckCircle size={10} style={{ marginRight: 3 }} /> ativo
                        </Badge>
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
                  {model.map50 != null && (
                    <div className={s.modelMeta}>
                      mAP@50: {(model.map50 * 100).toFixed(1)}%
                      {model.precision != null && ` | Precision: ${(model.precision * 100).toFixed(1)}%`}
                      {model.recall != null && ` | Recall: ${(model.recall * 100).toFixed(1)}%`}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Tabs.Content>
      </Tabs.Root>
    </div>
  )
}
