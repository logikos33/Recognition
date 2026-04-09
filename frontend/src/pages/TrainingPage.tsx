/**
 * TrainingPage — lista jobs de treinamento e modelos.
 */
import { useState, useEffect, useCallback } from 'react'
import toast from 'react-hot-toast'
import { api } from '../services/api'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { Badge, statusToBadge } from '../components/ui/Badge/Badge'
import { Button } from '../components/ui/Button/Button'
import type { TrainingJob, TrainedModel, ApiResponse } from '../types'
import * as s from './TrainingPage.css'

export function TrainingPage() {
  const [jobs, setJobs] = useState<TrainingJob[]>([])
  const [models, setModels] = useState<TrainedModel[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)

  const loadData = useCallback(async () => {
    try {
      const [jobsRes, modelsRes] = await Promise.all([
        api.get<ApiResponse<TrainingJob[]>>('/training/jobs'),
        api.get<ApiResponse<TrainedModel[]>>('/training/models'),
      ])
      setJobs(jobsRes.data || [])
      setModels(modelsRes.data || [])
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

  if (loading) return <LoadingSpinner />

  return (
    <div className={s.page}>
      <div className={s.pageHeader}>
        <h2 className={s.pageTitle}>Treinamento</h2>
        <Button variant="primary" onClick={createJob} disabled={creating}>
          {creating ? 'Criando...' : 'Novo Treinamento'}
        </Button>
      </div>

      {/* Jobs */}
      <h3 className={s.sectionTitle}>Jobs de Treinamento</h3>
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

      {/* Models */}
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
    </div>
  )
}
