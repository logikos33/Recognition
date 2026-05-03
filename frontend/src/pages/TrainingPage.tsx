/**
 * TrainingPage — unified training view with sub-tabs: Dados, Treinar, Modelos.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import { useToast } from '../components/ui/Toast/useToast'
import { Upload, Play, Zap, CheckCircle, Trash2, Plus } from 'lucide-react'
import { api, getToken } from '../services/api'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { Badge, statusToBadgeVariant } from '../components/ui/Badge/Badge'
import { Button } from '../components/ui/Button/Button'
import { FrameTimeline } from '../components/training/FrameTimeline'
import type { FrameInfo } from '../components/training/FrameTimeline'
import { useTrainingSocket } from '../hooks/useTrainingSocket'
import { useAuth } from '../hooks/useAuth'
import type { TrainingJob, TrainedModel, Video, ApiResponse } from '../types'
import * as s from './TrainingPage.css'

// @ts-ignore — JSX component congelado
import AnnotationInterface from '../components/AnnotationInterface'

function displayModelName(name: string): string {
  return name.replace(/yolo26n/gi, 'LGKV26n').replace(/yolo26s/gi, 'LGKV26s').replace(/yolo26m/gi, 'LGKV26m')
}

function formatEta(seconds: number): string {
  if (seconds <= 0) return ''
  const m = Math.floor(seconds / 60)
  const sec = seconds % 60
  return `${m}:${String(sec).padStart(2, '0')} restantes`
}

interface MiniChartProps {
  data: number[]
  color: string
  label: string
  width?: number
  height?: number
}

function MiniChart({ data, color, label, width = 200, height = 52 }: MiniChartProps) {
  if (data.length < 2) return null
  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1
  const pad = 3
  const points = data
    .map((v, i) => `${(i / (data.length - 1)) * width},${height - pad - ((v - min) / range) * (height - pad * 2)}`)
    .join(' ')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ fontSize: 11, color: '#888', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
      <svg width={width} height={height} style={{ display: 'block', borderRadius: 4, background: 'rgba(255,255,255,0.03)' }}>
        <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span style={{ fontSize: 12, color: '#ccc', fontFamily: 'monospace' }}>
        {data[data.length - 1]?.toFixed(4)}
      </span>
    </div>
  )
}

export function TrainingPage() {
  const toast = useToast()
  const { modules } = useAuth()
  // Módulos de treinamento habilitados para este tenant
  const trainingModules = ['epi', 'quality', 'counting'].filter(m => modules.includes(m))

  const [jobs, setJobs] = useState<TrainingJob[]>([])
  const [models, setModels] = useState<TrainedModel[]>([])
  const [videos, setVideos] = useState<Video[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null)
  const [frameTimelineVideo, setFrameTimelineVideo] = useState<Video | null>(null)

  // Upload state (video)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Upload state (direct images)
  const [uploadingImages, setUploadingImages] = useState(false)
  const [dragOverImages, setDragOverImages] = useState(false)
  const imageInputRef = useRef<HTMLInputElement>(null)

  // Training config form
  const [showConfig, setShowConfig] = useState(false)
  const [cfgPreset, setCfgPreset] = useState('balanced')
  const [cfgModelSize, setCfgModelSize] = useState('yolo26n')
  const [cfgEpochs, setCfgEpochs] = useState(50)
  const [cfgBatch, setCfgBatch] = useState(16)
  const [cfgImgSize, setCfgImgSize] = useState(640)
  const [cfgModule, setCfgModule] = useState(() => trainingModules[0] ?? 'epi')
  const [creating, setCreating] = useState(false)
  const [activating, setActivating] = useState<string | null>(null)
  const [deleteConfirmVideo, setDeleteConfirmVideo] = useState<Video | null>(null)

  const [validatedCount, setValidatedCount] = useState<number | null>(null)
  const [validatedAnnotated, setValidatedAnnotated] = useState<number | null>(null)
  const [loadingValidation, setLoadingValidation] = useState(false)

  // Simple/Advanced mode toggle
  const [simpleMode, setSimpleMode] = useState(true)
  const [selectedProfile, setSelectedProfile] = useState<'fast' | 'balanced' | 'quality'>('balanced')
  const [showCostModal, setShowCostModal] = useState(false)

  const getVideoStatusLabel = (video: Video): string => {
    switch (video.status) {
      case 'queued': return 'Na fila...'
      case 'extracting': {
        const exp = video.frames_expected ?? 0
        const cnt = video.frame_count ?? 0
        if (exp > 0) {
          const pct = Math.round(Math.min((cnt / exp) * 100, 100))
          return `Extraindo: ${cnt}/${exp} (${pct}%)`
        }
        return 'Extraindo...'
      }
      case 'pre_annotating': return 'Pré-anotando...'
      case 'pre_annotated': return 'Pré-anotado ✓'
      case 'extracted': return 'Extraído'
      case 'error': return `Erro: ${video.error_message ?? 'falha na extração'}`
      default: return video.status ?? ''
    }
  }

  const PROFILES: Record<'fast' | 'balanced' | 'quality', { label: string; epochs: number; imgsz: number; batch: number; model: string; desc: string }> = {
    fast:     { label: 'Rápido (~15 min)',      epochs: 10,  imgsz: 416, batch: 16, model: 'yolo26n.pt', desc: 'Bom para testar se as anotações estão corretas.' },
    balanced: { label: 'Recomendado (~1-2h)',    epochs: 50,  imgsz: 640, batch: 16, model: 'yolo26n.pt', desc: 'Equilíbrio entre velocidade e qualidade.' },
    quality:  { label: 'Alta Precisão (~3-6h)',  epochs: 100, imgsz: 640, batch: 8,  model: 'yolo26s.pt', desc: 'Máxima precisão. Use quando confiança é crítica.' },
  }

  // Storage stats
  const [storageUsed, setStorageUsed] = useState('')
  const [storagePercent, setStoragePercent] = useState(0)

  // Frame thumbnails cache per video (full FrameInfo for FrameTimeline)
  const [frameCache, setFrameCache] = useState<Record<string, FrameInfo[]>>({})

  // WebSocket for live training progress
  const apiBase = import.meta.env.VITE_API_URL || ''
  const token = getToken() || ''
  const { jobs: liveJobs } = useTrainingSocket({ wsUrl: apiBase, token })
  const extractingSetRef = useRef<Set<string>>(new Set())
  // Ref so uploadFile can call runBrowserExtraction without hoisting issues
  const runBrowserExtractionRef = useRef<(videoId: string) => void>(() => {})

  const loadStorage = useCallback(async () => {
    try {
      const res = await api.get<any>('/v1/videos/storage')
      const data = res?.data || res
      setStorageUsed(data.used_formatted || '0 B')
      setStoragePercent(data.percentage || 0)
    } catch { /* silent */ }
  }, [])

  const loadValidationStats = useCallback(async (videoList: Video[]) => {
    const extracted = videoList.filter(v => v.status === 'extracted')
    if (extracted.length === 0) {
      setValidatedCount(0)
      setValidatedAnnotated(0)
      return
    }
    setLoadingValidation(true)
    try {
      const token = getToken()
      const authHeader = token ? `Bearer ${token}` : ''
      const results = await Promise.allSettled(
        extracted.map(v =>
          fetch(`/api/training/videos/${v.id}/validation-stats`, {
            headers: { Authorization: authHeader },
          }).then(r => r.json())
        )
      )
      let totalValidated = 0
      let totalAnnotated = 0
      for (const r of results) {
        if (r.status === 'fulfilled' && r.value?.stats) {
          totalValidated += r.value.stats.validated || 0
          totalAnnotated += r.value.stats.annotated || 0
        }
      }
      setValidatedCount(totalValidated)
      setValidatedAnnotated(totalAnnotated)
    } catch { /* silent */ }
    finally {
      setLoadingValidation(false)
    }
  }, [])

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

  useEffect(() => { loadData(); loadStorage() }, [loadData, loadStorage])

  useEffect(() => {
    if (videos.length > 0) loadValidationStats(videos)
  }, [videos, loadValidationStats])

  // Poll transitional videos every 3s (queued, extracting, pre_annotating)
  useEffect(() => {
    const transitional = videos.filter(
      v => ['queued', 'extracting', 'pre_annotating'].includes(v.status) &&
           !extractingSetRef.current.has(v.id)
    )
    if (transitional.length === 0) return
    const timer = setInterval(async () => {
      for (const v of transitional) {
        try {
          const res = await api.get<any>(`/v1/videos/${v.id}/status`)
          const data = res?.data || res
          const video = data?.video
          if (video) {
            setVideos(prev => prev.map(pv => pv.id === v.id ? { ...pv, ...video, id: pv.id } : pv))
            if (!['queued', 'extracting', 'pre_annotating'].includes(video.status)) {
              loadData()
              loadStorage()
            }
          }
        } catch { /* silent */ }
      }
    }, 3000)
    return () => clearInterval(timer)
  }, [videos, loadData, loadStorage])

  // Load frames for extracted videos
  useEffect(() => {
    const extracted = videos.filter(v => v.status === 'extracted')
    extracted.forEach(v => {
      if (!frameCache[v.id]) loadFramesRef.current(v.id)
    })
  }, [videos, frameCache])

  // Upload video — presigned URL flow (direct to R2) with real byte progress
  const uploadFile = useCallback(async (file: File) => {
    if (!file.type.startsWith('video/')) {
      toast.error('Selecione um arquivo de video')
      return
    }
    setUploading(true)
    setUploadProgress(0)
    try {
      // Step 1: request presigned upload URL
      const urlRes = await api.post<ApiResponse<{ upload_url: string; video_id: string; storage_key: string }>>(
        '/v1/videos/upload-url',
        { filename: file.name, content_type: file.type || 'video/mp4', file_size: file.size },
      )
      const uploadData = urlRes.data
      if (!uploadData) throw new Error('Resposta invalida do servidor')
      const { upload_url, video_id } = uploadData
      let effectiveVideoId = video_id

      // Step 2: upload file with real byte-level progress
      const doMultipart = () => new Promise<string>((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) setUploadProgress(Math.round((e.loaded / e.total) * 100))
        }
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try { resolve(JSON.parse(xhr.responseText).data?.id ?? '') } catch { resolve('') }
          } else {
            reject(new Error(`Upload falhou: ${xhr.status}`))
          }
        }
        xhr.onerror = () => reject(new Error('Erro de conexao ao enviar video'))
        const formData = new FormData()
        formData.append('file', file)
        xhr.open('POST', `${apiBase}/api/v1/videos/upload`)
        const tok = getToken()
        if (tok) xhr.setRequestHeader('Authorization', `Bearer ${tok}`)
        xhr.send(formData)
      })

      if (upload_url.startsWith('http')) {
        // Production: PUT directly to R2 — real byte progress via xhr.upload.onprogress
        const r2Ok = await new Promise<boolean>((resolve) => {
          const xhr = new XMLHttpRequest()
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) setUploadProgress(Math.round((e.loaded / e.total) * 100))
          }
          xhr.onload = () => resolve(xhr.status >= 200 && xhr.status < 300)
          xhr.onerror = () => resolve(false)  // CORS or network error → fallback
          xhr.open('PUT', upload_url)
          xhr.setRequestHeader('Content-Type', file.type || 'video/mp4')
          xhr.send(file)
        })

        if (!r2Ok) {
          // R2 PUT failed (CORS not configured) — clean up orphan and fall back to multipart
          setUploadProgress(0)
          try { await api.delete(`/v1/videos/${video_id}`) } catch { /* orphan cleanup best-effort */ }
          effectiveVideoId = await doMultipart()
        } else {
          // R2 PUT succeeded — notify backend to queue server-side extraction
          try { await api.post(`/v1/videos/${effectiveVideoId}/upload-complete`, {}) } catch { /* best-effort */ }
        }
      } else {
        // Local dev: POST multipart to Flask
        await new Promise<void>((resolve, reject) => {
          const xhr = new XMLHttpRequest()
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) setUploadProgress(Math.round((e.loaded / e.total) * 100))
          }
          xhr.onload = () => xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`Upload falhou: ${xhr.status}`))
          xhr.onerror = () => reject(new Error('Erro de conexao ao enviar video'))
          const formData = new FormData()
          formData.append('file', file)
          xhr.open('POST', `${apiBase}${upload_url}`)
          const tok = getToken()
          if (tok) xhr.setRequestHeader('Authorization', `Bearer ${tok}`)
          xhr.send(formData)
        })
      }

      setUploading(false)
      toast.success('Video enviado com sucesso')
      loadData()

      // Step 3: browser-side frame extraction (no Celery)
      if (effectiveVideoId) runBrowserExtractionRef.current(effectiveVideoId)
    } catch (err: unknown) {
      setUploading(false)
      toast.error(err instanceof Error ? err.message : 'Erro ao enviar video')
    }
  }, [loadData, apiBase])

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

  // Direct image batch upload (Track B)
  const uploadImages = useCallback(async (files: File[]) => {
    const images = files.filter(f => /\.(jpe?g|png|webp)$/i.test(f.name))
    if (!images.length) { toast.error('Selecione imagens JPG, PNG ou WebP'); return }
    if (images.length > 50) { toast.error('Máximo de 50 imagens por upload'); return }
    setUploadingImages(true)
    try {
      const form = new FormData()
      images.forEach(f => form.append('images', f))
      const res = await api.post<any>('/v1/videos/images/upload', form)
      const data = res?.data || res
      toast.success(`${data.uploaded} imagens enviadas`)
      await loadData()
      loadStorage()
      if (data.video_id) loadFramesRef.current(data.video_id)
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao enviar imagens')
    } finally {
      setUploadingImages(false)
    }
  }, [loadData, loadStorage])

  const handleImageDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOverImages(false)
    uploadImages(Array.from(e.dataTransfer.files))
  }, [uploadImages])

  const handleImageSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) uploadImages(Array.from(e.target.files))
    e.target.value = ''
  }, [uploadImages])

  // Server-side frame extraction via OpenCV (handles all codecs)
  const runBrowserExtraction = useCallback(async (videoId: string) => {
    extractingSetRef.current.add(videoId)
    setVideos(prev => prev.map(v => v.id === videoId ? { ...v, status: 'extracting' } : v))
    try {
      await api.post(`/v1/videos/${videoId}/server-extract`, {})
      toast.success('Extração iniciada — aguarde...')
      // Remove from set so the 3s polling loop can detect "extracted"
      extractingSetRef.current.delete(videoId)
    } catch (err: unknown) {
      setVideos(prev => prev.map(v => v.id === videoId ? { ...v, status: 'error', error_message: 'Falha na extracao' } : v))
      toast.error(err instanceof Error ? err.message : 'Falha ao iniciar extracao')
      extractingSetRef.current.delete(videoId)
    }
  }, [loadData, loadStorage])

  // Delete video (called after modal confirmation)
  const deleteVideo = useCallback(async (videoId: string) => {
    try {
      await api.delete(`/v1/videos/${videoId}`)
      toast.success('Video excluido')
      setVideos(prev => prev.filter(v => v.id !== videoId))
      setDeleteConfirmVideo(null)
      loadStorage()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao excluir')
    }
  }, [loadStorage])

  // Keep ref in sync so uploadFile can call it without hoisting issues
  runBrowserExtractionRef.current = runBrowserExtraction

  // Load frames for FrameTimeline (no slice — all frames metadata)
  const loadFramesRef = useRef<(videoId: string) => void>(() => {})
  loadFramesRef.current = async (videoId: string) => {
    try {
      const res = await api.get<any>(`/training/videos/${videoId}/frames`)
      const data = res?.data || res
      const frames: FrameInfo[] = Array.isArray(data) ? data : (data?.frames || [])
      setFrameCache(prev => ({ ...prev, [videoId]: frames }))
    } catch { /* silent */ }
  }

  // Open FrameTimeline for a video (loads frames if not cached)
  const openTimeline = useCallback((video: Video) => {
    if (!frameCache[video.id]) loadFramesRef.current(video.id)
    setFrameTimelineVideo(video)
  }, [frameCache])

  // From FrameTimeline: annotate a specific frame → open AnnotationInterface
  const handleAnnotate = useCallback((_frameId: string) => {
    if (frameTimelineVideo) {
      setSelectedVideoId(frameTimelineVideo.id)
      setFrameTimelineVideo(null)
    }
  }, [frameTimelineVideo])

  // From FrameTimeline: pre-annotate frame with AI
  const handlePreAnnotate = useCallback(async (frameId: string) => {
    toast.info('Pré-anotando com IA...')
    try {
      const res = await api.post<{ success: boolean; data?: { annotations_count?: number } }>(`/frames/${frameId}/pre-annotate`, {})
      const count = res.data?.annotations_count ?? 0
      if (count > 0) {
        toast.success(`IA detectou ${count} objeto(s)`)
      } else {
        toast.warning('Nenhuma detecção encontrada. Tente intensidade maior.')
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao pré-anotar')
    }
  }, [])

  // Create training job (called after cost modal confirmation)
  const createJob = async () => {
    setShowCostModal(false)
    setCreating(true)
    try {
      let preset: string, modelSize: string, epochs: number, batch: number, imgSize: number
      if (simpleMode) {
        const profile = PROFILES[selectedProfile]
        preset = selectedProfile
        modelSize = profile.model.replace('.pt', '')
        epochs = profile.epochs
        batch = profile.batch
        imgSize = profile.imgsz
      } else {
        preset = cfgPreset
        modelSize = cfgModelSize
        epochs = cfgEpochs
        batch = cfgBatch
        imgSize = cfgImgSize
      }
      await api.post('/training/jobs', {
        preset,
        module: cfgModule,
        model_size: modelSize,
        total_epochs: epochs,
        batch_size: batch,
        img_size: imgSize,
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

  // Full-screen annotation (frozen component — page replacement)
  if (selectedVideoId) {
    return (
      <AnnotationInterface
        videoId={selectedVideoId}
        onBack={() => setSelectedVideoId(null)}
      />
    )
  }

  if (loading) return <LoadingSpinner />

  const extractedVideos = videos.filter(v => v.status === 'extracted' || v.status === 'pre_annotated')
  const uploadedVideos = videos.filter(v => v.status === 'uploaded')
  const transitionalVideos = videos.filter(v => ['queued', 'extracting', 'pre_annotating'].includes(v.status))
  const errorVideos = videos.filter(v => v.status === 'error')
  const totalFrames = videos.reduce((sum, v) => sum + (v.frame_count || 0), 0)
  const validatedOk = (validatedCount ?? 0) >= 20
  const canTrain = totalFrames >= 20 && validatedOk

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

        {/* Tab: Dados — upload + videos + FrameTimeline entry */}
        <Tabs.Content value="dados" className={s.tabsContent}>
          {/* Storage bar */}
          <div className={s.storageBar}>
            <span className={s.storageLabel}>Armazenamento</span>
            <div className={s.storageTrack}>
              <div className={s.storageFill} style={{ width: `${Math.min(storagePercent, 100)}%` }} />
            </div>
            <span className={s.storageLabel}>{storageUsed} / 5 GB</span>
            <button className={s.storagePlus} onClick={() => toast.info('Em breve: adquirir mais armazenamento')} title="Adquirir mais armazenamento">
              <Plus size={12} />
            </button>
          </div>

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

          {/* Image batch upload zone */}
          <div
            style={{
              border: `1.5px dashed ${dragOverImages ? '#60a5fa' : 'rgba(255,255,255,0.15)'}`,
              borderRadius: 10, padding: '14px 18px', marginBottom: 12, cursor: 'pointer',
              background: dragOverImages ? 'rgba(96,165,250,0.08)' : 'rgba(255,255,255,0.03)',
              display: 'flex', alignItems: 'center', gap: 12, transition: 'all 0.15s',
            }}
            onDragOver={(e) => { e.preventDefault(); setDragOverImages(true) }}
            onDragLeave={() => setDragOverImages(false)}
            onDrop={handleImageDrop}
            onClick={() => imageInputRef.current?.click()}
          >
            <input ref={imageInputRef} type="file" accept="image/jpeg,image/png,image/webp" multiple hidden onChange={handleImageSelect} />
            {uploadingImages ? (
              <><LoadingSpinner /><span style={{ fontSize: 13, color: '#888' }}>Enviando imagens...</span></>
            ) : (
              <><Upload size={18} style={{ opacity: 0.4, flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: '#888' }}>
                Arraste imagens (JPG/PNG/WebP) ou clique — até 50 por vez
              </span></>
            )}
          </div>

          {/* Dataset summary cards */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
            {[
              { label: 'Vídeos enviados', value: videos.length },
              { label: 'Frames extraídos', value: totalFrames },
              { label: 'Prontos para anotar', value: extractedVideos.length },
            ].map(stat => (
              <div key={stat.label} style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 8,
                padding: '10px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
                minWidth: 120,
              }}>
                <span style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', lineHeight: 1 }}>{stat.value}</span>
                <span style={{ fontSize: 11, color: '#64748b', fontWeight: 500 }}>{stat.label}</span>
              </div>
            ))}
          </div>

          {/* Uploaded videos (pending extraction) */}
          {uploadedVideos.length > 0 && (
            <>
              <h3 className={s.sectionTitle}>Aguardando extracao</h3>
              <div className={s.grid}>
                {uploadedVideos.map(video => (
                  <div key={video.id} className={s.jobCard}>
                    <div className={s.cardRow}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span className={s.jobName}>{video.original_filename || video.filename}</span>
                        {video.file_size && <span className={s.jobPreset}>{(video.file_size / 1024 / 1024).toFixed(1)} MB</span>}
                      </div>
                      <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                        <Button size="sm" variant="secondary" onClick={() => runBrowserExtraction(video.id)}>
                          <Play size={12} /> Extrair Frames
                        </Button>
                        <button className={s.deleteBtn} onClick={() => setDeleteConfirmVideo(video)} title="Excluir video">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Transitional — queued, extracting, pre_annotating — polled every 3s */}
          {transitionalVideos.length > 0 && (
            <>
              <h3 className={s.sectionTitle}>Processando...</h3>
              <div className={s.grid}>
                {transitionalVideos.map(video => (
                  <div key={video.id} className={s.jobCard}>
                    <div className={s.cardRow}>
                      <span className={s.jobName}>{video.original_filename || video.filename}</span>
                      <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                        <Badge variant="warning">{getVideoStatusLabel(video)}</Badge>
                        <button className={s.deleteBtn} onClick={() => setDeleteConfirmVideo(video)} title="Excluir video">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                    {video.status === 'extracting' && (
                      <div style={{ marginTop: 8 }}>
                        {(video.frames_expected ?? 0) > 0 ? (
                          <>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                              <div style={{ flex: 1, height: 4, background: '#333', borderRadius: 2, overflow: 'hidden' }}>
                                <div style={{
                                  width: `${Math.round(Math.min((video.frame_count || 0) / (video.frames_expected ?? 1) * 100, 100))}%`,
                                  height: '100%',
                                  background: '#3b82f6',
                                  borderRadius: 2,
                                  transition: 'width 0.3s ease',
                                }} />
                              </div>
                              <span style={{ fontSize: 12, color: '#aaa', minWidth: 36, textAlign: 'right' }}>
                                {Math.round(Math.min((video.frame_count || 0) / (video.frames_expected ?? 1) * 100, 100))}%
                              </span>
                            </div>
                            <span style={{ fontSize: 11, color: '#666' }}>
                              {video.frame_count || 0}/{video.frames_expected} frames
                            </span>
                          </>
                        ) : (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <LoadingSpinner />
                            <span style={{ fontSize: 12, color: '#888' }}>Extraindo frames no servidor...</span>
                          </div>
                        )}
                      </div>
                    )}
                    {(video.status === 'queued' || video.status === 'pre_annotating') && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
                        <LoadingSpinner />
                        <span style={{ fontSize: 12, color: '#888' }}>{getVideoStatusLabel(video)}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Error videos — with retry */}
          {errorVideos.length > 0 && (
            <>
              <h3 className={s.sectionTitle} style={{ color: '#ef4444' }}>Falha na extracao</h3>
              <div className={s.grid}>
                {errorVideos.map(video => (
                  <div key={video.id} className={s.jobCard} style={{ borderColor: 'rgba(239,68,68,0.3)' }}>
                    <div className={s.cardRow}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <span className={s.jobName}>{video.original_filename || video.filename}</span>
                        {video.error_message && (
                          <span className={s.jobPreset} style={{ color: '#ef4444' }}>{video.error_message}</span>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                        <Badge variant="danger">Erro</Badge>
                        <Button size="sm" variant="secondary" onClick={() => runBrowserExtraction(video.id)}>
                          <Play size={12} /> Tentar novamente
                        </Button>
                        <button className={s.deleteBtn} onClick={() => setDeleteConfirmVideo(video)} title="Excluir video">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Extracted — click opens CapCut FrameTimeline */}
          <h3 className={s.sectionTitle}>Prontos para anotacao</h3>
          {extractedVideos.length === 0 ? (
            <p className={s.emptyText}>Nenhum video com frames extraidos. Faca upload e extraia frames.</p>
          ) : (
            <div className={s.grid}>
              {extractedVideos.map(video => {
                const frames = frameCache[video.id]
                return (
                  <div key={video.id} className={s.jobCard}>
                    <div className={s.cardRow}>
                      <div style={{ cursor: 'pointer', flex: 1 }} onClick={() => openTimeline(video)}>
                        <span className={s.jobName}>{video.original_filename || video.filename}</span>
                        <span className={s.jobPreset}>{video.frame_count} frames</span>
                      </div>
                      <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                        <Badge variant={statusToBadgeVariant(video.status)}>{video.status}</Badge>
                        <button className={s.deleteBtn} onClick={() => setDeleteConfirmVideo(video)} title="Excluir video">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                    {/* Mini thumbnail strip — click opens full timeline */}
                    {frames && frames.length > 0 && (
                      <div className={s.carouselWrap} onClick={() => openTimeline(video)} style={{ cursor: 'pointer' }}>
                        {frames.slice(0, 12).map((frame) => (
                          <img
                            key={frame.id}
                            className={s.carouselThumb}
                            src={frame.url ?? `${apiBase}/api/training/frames/${frame.id}/image`}
                            alt={`Frame ${frame.filename}`}
                            loading="lazy"
                          />
                        ))}
                        {frames.length > 12 && (
                          <div style={{
                            flexShrink: 0,
                            width: 72,
                            height: 48,
                            borderRadius: 4,
                            background: 'rgba(139,92,246,0.15)',
                            border: '1px solid rgba(139,92,246,0.3)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 11,
                            color: '#a78bfa',
                            fontWeight: 600,
                          }}>
                            +{frames.length - 12}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </Tabs.Content>

        {/* Tab: Treinar — config + jobs with live WS progress */}
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

              {/* Simple / Advanced toggle */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                <button
                  onClick={() => setSimpleMode(true)}
                  style={{
                    padding: '5px 14px', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                    background: simpleMode ? '#7c3aed' : 'transparent',
                    color: simpleMode ? '#fff' : '#94a3b8',
                    border: `1px solid ${simpleMode ? '#7c3aed' : 'rgba(255,255,255,0.1)'}`,
                  }}
                >
                  Simples
                </button>
                <button
                  onClick={() => setSimpleMode(false)}
                  style={{
                    padding: '5px 14px', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                    background: !simpleMode ? '#7c3aed' : 'transparent',
                    color: !simpleMode ? '#fff' : '#94a3b8',
                    border: `1px solid ${!simpleMode ? '#7c3aed' : 'rgba(255,255,255,0.1)'}`,
                  }}
                >
                  Avançado
                </button>
              </div>

              {simpleMode ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {(['fast', 'balanced', 'quality'] as const).map(key => {
                    const p = PROFILES[key]
                    const isSelected = selectedProfile === key
                    return (
                      <label
                        key={key}
                        style={{
                          display: 'flex', alignItems: 'flex-start', gap: 12, padding: '12px 14px',
                          borderRadius: 8, cursor: 'pointer',
                          border: `1px solid ${isSelected ? 'rgba(124,58,237,0.6)' : 'rgba(255,255,255,0.07)'}`,
                          background: isSelected ? 'rgba(124,58,237,0.12)' : 'transparent',
                        }}
                      >
                        <input
                          type="radio"
                          name="profile"
                          value={key}
                          checked={isSelected}
                          onChange={() => setSelectedProfile(key)}
                          style={{ marginTop: 3, accentColor: '#7c3aed' }}
                        />
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 600, color: '#f1f5f9' }}>{p.label}</div>
                          <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>{p.desc}</div>
                        </div>
                      </label>
                    )
                  })}
                </div>
              ) : (
                <div className={s.configGrid}>
                  <div className={s.configField}>
                    <label className={s.configLabel}>Módulo</label>
                    <select className={s.configSelect} value={cfgModule} onChange={e => setCfgModule(e.target.value)}>
                      {trainingModules.map(m => (
                        <option key={m} value={m}>{m.charAt(0).toUpperCase() + m.slice(1)}</option>
                      ))}
                    </select>
                  </div>
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
                      <option value="yolo26n">LGKV26n (nano)</option>
                      <option value="yolo26s">LGKV26s (small)</option>
                      <option value="yolo26m">LGKV26m (medium)</option>
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
              )}

              {/* AI_NOTE: US-025 — validation stats shown above training button */}
              <div style={{
                display: 'flex', gap: '16px', marginTop: 12, marginBottom: 4,
                padding: '10px 14px', background: 'rgba(255,255,255,0.04)',
                borderRadius: '8px', border: '1px solid rgba(255,255,255,0.08)',
                flexWrap: 'wrap', alignItems: 'center',
              }}>
                <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: '13px' }}>
                  Frames anotados: <strong style={{ color: '#22c55e' }}>{validatedAnnotated ?? '...'}</strong>
                </span>
                <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: '13px' }}>
                  Frames validados: <strong style={{ color: validatedOk ? '#3b82f6' : '#f59e0b' }}>
                    {loadingValidation ? '...' : (validatedCount ?? 0)}
                  </strong>
                  {' / 20'}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                <Button
                  variant="primary"
                  onClick={() => setShowCostModal(true)}
                  disabled={creating || !canTrain}
                >
                  {creating ? 'Criando...' : 'Iniciar Treinamento'}
                </Button>
                <Button variant="secondary" onClick={() => setShowConfig(false)}>Cancelar</Button>
                {totalFrames < 20 && (
                  <span style={{ fontSize: 12, color: '#f59e0b' }}>
                    Minimo de 20 frames necessario. Voce tem {totalFrames} frames.
                  </span>
                )}
                {totalFrames >= 20 && !validatedOk && (
                  <span style={{ fontSize: 12, color: '#f59e0b' }}>
                    Valide pelo menos 20 frames antes de treinar. ({validatedCount ?? 0} validados)
                  </span>
                )}
              </div>
            </div>
          )}

          {jobs.length === 0 ? (
            <p className={s.emptyText}>Nenhum job de treinamento ainda.</p>
          ) : (
            <div className={s.grid}>
              {jobs.map(job => {
                const live = liveJobs[job.id]
                const isLive = live && live.status !== 'pending'
                const displayStatus = isLive ? live.status : job.status
                const showLiveProgress = isLive && (live.status === 'training' || live.status === 'creating_pod')

                return (
                  <div key={job.id} className={s.jobCard}>
                    <div className={s.cardRow}>
                      <div>
                        <span className={s.jobName}>{displayModelName(job.model_size)}</span>
                        <span className={s.jobPreset}>Preset: {job.preset}</span>
                      </div>
                      <Badge variant={statusToBadgeVariant(displayStatus)}>{displayStatus}</Badge>
                    </div>

                    {/* Live WebSocket progress */}
                    {showLiveProgress && (
                      <div style={{ marginTop: 12 }}>
                        <div className={s.progressWrap}>
                          <div className={s.progressTrack}>
                            <div className={s.progressFill} style={{ width: `${live.progress}%` }} />
                          </div>
                          <span className={s.progressLabel}>
                            Epoch {live.epoch}/{live.total_epochs} ({live.progress}%)
                            {live.eta_seconds > 0 && ` · ${formatEta(live.eta_seconds)}`}
                          </span>
                        </div>

                        {/* SVG sparkline charts */}
                        {(live.lossHistory.length >= 2 || live.map50History.length >= 2) && (
                          <div style={{ display: 'flex', gap: 24, marginTop: 14, flexWrap: 'wrap' }}>
                            {live.lossHistory.length >= 2 && (
                              <MiniChart data={live.lossHistory} color="#a78bfa" label="Loss" />
                            )}
                            {live.map50History.length >= 2 && (
                              <MiniChart data={live.map50History} color="#22d3ee" label="mAP@50" />
                            )}
                          </div>
                        )}

                        {/* Live metric badges */}
                        {live.metrics && (live.metrics.precision != null || live.metrics.recall != null) && (
                          <div style={{ display: 'flex', gap: 12, marginTop: 10, flexWrap: 'wrap' }}>
                            {live.metrics.precision != null && (
                              <span style={{ fontSize: 11, color: '#888' }}>
                                Precision: <strong style={{ color: '#ccc' }}>{(live.metrics.precision * 100).toFixed(1)}%</strong>
                              </span>
                            )}
                            {live.metrics.recall != null && (
                              <span style={{ fontSize: 11, color: '#888' }}>
                                Recall: <strong style={{ color: '#ccc' }}>{(live.metrics.recall * 100).toFixed(1)}%</strong>
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Static progress fallback (no live data) */}
                    {!showLiveProgress && (job.status === 'running' || job.status === 'pending') && (
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
                )
              })}
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
                        <Badge variant="success">
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

      {/* Delete confirmation modal */}
      {deleteConfirmVideo && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 200,
          background: 'rgba(0,0,0,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => setDeleteConfirmVideo(null)}>
          <div style={{
            background: '#0f172a',
            border: '1px solid #1e293b',
            borderRadius: 12,
            padding: '24px 28px',
            maxWidth: 380,
            width: '90%',
          }} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 8px', fontSize: 16, fontWeight: 700, color: '#f1f5f9' }}>
              Excluir video?
            </h3>
            <p style={{ margin: '0 0 20px', fontSize: 13, color: '#64748b', wordBreak: 'break-all' }}>
              "{deleteConfirmVideo.original_filename || deleteConfirmVideo.filename}" sera excluido permanentemente. Esta acao nao pode ser desfeita.
            </p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <Button variant="secondary" onClick={() => setDeleteConfirmVideo(null)}>Cancelar</Button>
              <Button variant="primary" onClick={() => deleteVideo(deleteConfirmVideo.id)}
                style={{ background: '#ef4444', borderColor: '#ef4444' }}>
                Excluir
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* CapCut-style FrameTimeline overlay */}
      {frameTimelineVideo && (
        <FrameTimeline
          frames={frameCache[frameTimelineVideo.id] || []}
          videoName={frameTimelineVideo.original_filename || frameTimelineVideo.filename}
          apiBase={apiBase}
          onAnnotate={handleAnnotate}
          onPreAnnotate={handlePreAnnotate}
          onClose={() => setFrameTimelineVideo(null)}
        />
      )}

      {/* Cost confirmation modal */}
      {showCostModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 200,
          background: 'rgba(0,0,0,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => setShowCostModal(false)}>
          <div style={{
            background: '#0f172a',
            border: '1px solid #1e293b',
            borderRadius: 12,
            padding: '24px 28px',
            maxWidth: 420,
            width: '90%',
          }} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 16px', fontSize: 16, fontWeight: 700, color: '#f1f5f9' }}>
              Confirmar Treinamento
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
              {simpleMode ? (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: '#64748b' }}>Perfil</span>
                    <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{PROFILES[selectedProfile].label}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: '#64748b' }}>Epochs</span>
                    <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{PROFILES[selectedProfile].epochs}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: '#64748b' }}>Tempo estimado</span>
                    <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{PROFILES[selectedProfile].label.match(/\(.*\)/)?.[0] ?? '—'}</span>
                  </div>
                </>
              ) : (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: '#64748b' }}>Preset</span>
                    <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{cfgPreset}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: '#64748b' }}>Epochs</span>
                    <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{cfgEpochs}</span>
                  </div>
                </>
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                <span style={{ color: '#64748b' }}>Custo estimado</span>
                <span style={{ color: '#22c55e', fontWeight: 600 }}>R$ 0,00 (processamento local)</span>
              </div>
            </div>
            <p style={{ margin: '0 0 20px', fontSize: 12, color: '#f59e0b', background: 'rgba(245,158,11,0.08)', borderRadius: 6, padding: '8px 10px' }}>
              Após iniciar, o custo do tempo já utilizado será cobrado.
            </p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <Button variant="secondary" onClick={() => setShowCostModal(false)}>Cancelar</Button>
              <Button variant="primary" onClick={createJob} disabled={creating}>
                {creating ? 'Criando...' : 'Confirmar e treinar'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
