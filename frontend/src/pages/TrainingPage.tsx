/**
 * TrainingPage — unified training view with sub-tabs: Dados, Treinar, Modelos.
 */
import { useState, useEffect, useCallback } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import toast from 'react-hot-toast'
import { api } from '../services/api'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { Badge, statusToBadge } from '../components/ui/Badge/Badge'
import { Button } from '../components/ui/Button/Button'
import type { TrainingJob, TrainedModel, Video, ApiResponse } from '../types'
import * as s from './TrainingPage.css'

// @ts-ignore — JSX component congelado
import AnnotationInterface from '../components/AnnotationInterface'

export function TrainingPage() {
  const [jobs, setJobs] = useState<TrainingJob[]>([])
  const [models, setModels] = useState<TrainedModel[]>([])
  const [videos, setVideos] = useState<Video[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null)

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

  const createJob = async () => {
    setCreating(true)
    try {
      await api.post('/training/jobs', {
        preset: 'balanced', model_size: 'yolov8n', total_epochs: 50,
      })
      await loadData()
    } catch (err: any) {
      toast.error(err.message || 'Erro ao criar job')
    } finally {
      setCreating(false)
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

        {/* Tab: Dados — videos + annotation */}
        <Tabs.Content value="dados" className={s.tabsContent}>
          <h3 className={s.sectionTitle}>Videos para Anotacao</h3>
          {extractedVideos.length === 0 ? (
            <p className={s.emptyText}>Nenhum video disponivel. Faca upload de um video primeiro.</p>
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
                      <span className={s.jobName}>
                        {video.original_filename || video.filename}
                      </span>
                      <span className={s.jobPreset}>{video.frame_count} frames</span>
                    </div>
                    <Badge status={statusToBadge(video.status)}>{video.status}</Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Tabs.Content>

        {/* Tab: Treinar — jobs */}
        <Tabs.Content value="treinar" className={s.tabsContent}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 className={s.sectionTitle} style={{ margin: 0 }}>Jobs de Treinamento</h3>
            <Button variant="primary" onClick={createJob} disabled={creating}>
              {creating ? 'Criando...' : 'Novo Treinamento'}
            </Button>
          </div>
          {jobs.length === 0 ? (
            <p className={s.emptyText}>Nenhum job de treinamento ainda.</p>
          ) : (
            <div className={s.grid}>
              {jobs.map(job => (
                <div key={job.id} className={s.jobCard}>
                  <div className={s.cardRow}>
                    <div>
                      <span className={s.jobName}>{job.model_size}</span>
                      <span className={s.jobPreset}>Preset: {job.preset}</span>
                    </div>
                    <Badge status={statusToBadge(job.status)}>{job.status}</Badge>
                  </div>
                  {job.status === 'running' && (
                    <div className={s.progressWrap}>
                      <div className={s.progressTrack}>
                        <div className={s.progressFill} style={{ width: `${job.progress}%` }} />
                      </div>
                      <span className={s.progressLabel}>
                        Epoch {job.current_epoch}/{job.total_epochs} ({job.progress}%)
                      </span>
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
                    <span className={s.modelName}>{model.name}</span>
                    {model.is_active && <Badge status="active">active</Badge>}
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
