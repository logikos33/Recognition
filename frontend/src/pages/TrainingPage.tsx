/**
 * TrainingPage — lista jobs de treinamento e modelos.
 */
import { useState, useEffect, useCallback } from 'react'
import { api } from '../services/api'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { StatusBadge } from '../components/shared/StatusBadge'
import type { TrainingJob, TrainedModel, ApiResponse } from '../types'

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
      alert(err.message || 'Erro ao criar job')
    } finally {
      setCreating(false)
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div style={{ padding: 32 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ color: '#e2e8f0', margin: 0 }}>Treinamento</h2>
        <button onClick={createJob} disabled={creating} style={{
          padding: '8px 20px', borderRadius: 8, border: 'none',
          background: '#2563eb', color: '#fff', fontSize: 14,
          fontWeight: 600, cursor: creating ? 'not-allowed' : 'pointer',
        }}>
          {creating ? 'Criando...' : 'Novo Treinamento'}
        </button>
      </div>

      {/* Jobs */}
      <h3 style={{ color: '#94a3b8', fontSize: 14, marginBottom: 12 }}>Jobs de Treinamento</h3>
      {jobs.length === 0 ? (
        <p style={{ color: '#64748b' }}>Nenhum job de treinamento ainda.</p>
      ) : (
        <div style={{ display: 'grid', gap: 10, marginBottom: 32 }}>
          {jobs.map(job => (
            <div key={job.id} style={{
              padding: 16, background: '#1e293b', borderRadius: 12,
              border: '1px solid #334155',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{job.model_size}</span>
                  <span style={{ color: '#64748b', fontSize: 13, marginLeft: 8 }}>
                    Preset: {job.preset}
                  </span>
                </div>
                <StatusBadge status={job.status} />
              </div>
              {job.status === 'running' && (
                <div style={{ marginTop: 10 }}>
                  <div style={{
                    height: 6, background: '#334155', borderRadius: 3, overflow: 'hidden',
                  }}>
                    <div style={{
                      height: '100%', background: '#2563eb', borderRadius: 3,
                      width: `${job.progress}%`, transition: 'width 0.3s',
                    }} />
                  </div>
                  <span style={{ color: '#64748b', fontSize: 12, marginTop: 4, display: 'block' }}>
                    Epoch {job.current_epoch}/{job.total_epochs} ({job.progress}%)
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Models */}
      <h3 style={{ color: '#94a3b8', fontSize: 14, marginBottom: 12 }}>Modelos Treinados</h3>
      {models.length === 0 ? (
        <p style={{ color: '#64748b' }}>Nenhum modelo treinado ainda.</p>
      ) : (
        <div style={{ display: 'grid', gap: 10 }}>
          {models.map(model => (
            <div key={model.id} style={{
              padding: 16, background: '#1e293b', borderRadius: 12,
              border: model.is_active ? '2px solid #22c55e' : '1px solid #334155',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{model.name}</span>
                {model.is_active && <StatusBadge status="active" />}
              </div>
              {model.map50 != null && (
                <div style={{ color: '#64748b', fontSize: 13, marginTop: 6 }}>
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
