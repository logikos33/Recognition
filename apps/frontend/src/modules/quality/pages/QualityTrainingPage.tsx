/**
 * Página de treinamento do módulo de qualidade.
 * Banner de sugestões pendentes + stepper de jobs + polling a cada 5s + ativar modelo.
 */
import { useState, useEffect, useCallback } from 'react'
import { qualityService } from '../services/qualityService'
import { Skeleton } from '../../../components/ui/Skeleton/Skeleton'
import { card, cardTitle, cardHeader } from '../components/quality.css'
import type { QualityTrainingJob, QualityCamera } from '../types/quality'
import { vars } from '../../../styles/theme.css'

const STATUS_LABELS: Record<string, string> = {
  queued: 'Na fila',
  running: 'Treinando…',
  completed: 'Concluído',
  failed: 'Falhou',
}

const STATUS_COLORS: Record<string, string> = {
  queued: vars.color.textMuted,
  running: '#FFB74D',
  completed: vars.color.success,
  failed: vars.color.danger,
}

export function QualityTrainingPage() {
  const [jobs, setJobs] = useState<QualityTrainingJob[]>([])
  const [cameras, setCameras] = useState<QualityCamera[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [activatingModel, setActivatingModel] = useState<string | null>(null)
  const [selectedCamera, setSelectedCamera] = useState<string>('')

  const loadJobs = useCallback(async () => {
    try {
      const res = await qualityService.getTrainingJobs()
      setJobs(res.data.jobs)
    } catch { /* silent */ }
  }, [])

  useEffect(() => {
    async function init() {
      try {
        const [jobsRes, camsRes] = await Promise.all([
          qualityService.getTrainingJobs(),
          qualityService.getCameras(),
        ])
        setJobs(jobsRes.data.jobs)
        setCameras(camsRes.data.cameras)
        if (camsRes.data.cameras.length > 0) {
          setSelectedCamera(camsRes.data.cameras[0].id)
        }
      } catch { /* silent */ }
      setLoading(false)
    }
    init()
  }, [])

  // Polling a cada 5s se houver job running
  useEffect(() => {
    const hasActive = jobs.some(j => j.status === 'running' || j.status === 'queued')
    if (!hasActive) return
    const interval = setInterval(loadJobs, 5_000)
    return () => clearInterval(interval)
  }, [jobs, loadJobs])

  async function handleCreateJob() {
    setCreating(true)
    try {
      const res = await qualityService.createTrainingJob()
      setJobs(prev => [res.data.job, ...prev])
    } catch { /* silent */ }
    setCreating(false)
  }

  async function handleActivate(modelId: string) {
    if (!selectedCamera) return
    setActivatingModel(modelId)
    try {
      await qualityService.activateModel(modelId, selectedCamera)
      alert('Modelo ativado com sucesso!')
    } catch {
      alert('Erro ao ativar modelo.')
    }
    setActivatingModel(null)
  }

  const runningJob = jobs.find(j => j.status === 'running' || j.status === 'queued')

  if (loading) return (
    <div style={{ padding: 32, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Skeleton variant="title" width={200} />
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: 16 }}>
          <Skeleton variant="text" width="70%" />
          <Skeleton variant="text" width="45%" />
          <Skeleton variant="rect" width={160} height={28} style={{ marginTop: 4 }} />
        </div>
      ))}
    </div>
  )

  return (
    <div style={{ padding: '24px', maxWidth: '800px' }}>
      <h2 style={{ marginBottom: '20px', fontSize: '18px', fontWeight: 700 }}>Treinamento de Qualidade</h2>

      {/* Criar novo job */}
      <div className={card} style={{ marginBottom: '24px' }}>
        <div className={cardHeader}>
          <span className={cardTitle}>Novo Job de Treinamento</span>
        </div>
        <p style={{ fontSize: '13px', color: vars.color.textMuted, marginBottom: '16px' }}>
          Usa todos os frames com status "anotado" disponíveis. São necessários ao menos 10 frames anotados.
        </p>
        <button
          onClick={handleCreateJob}
          disabled={creating || !!runningJob}
          style={{
            padding: '8px 20px',
            borderRadius: '6px',
            border: 'none',
            background: creating || runningJob ? vars.color.borderDefault : '#4FC3F7',
            color: creating || runningJob ? vars.color.textMuted : '#000',
            fontWeight: 600,
            fontSize: '13px',
            cursor: creating || runningJob ? 'not-allowed' : 'pointer',
          }}
        >
          {creating ? 'Criando…' : runningJob ? 'Job em andamento' : 'Iniciar Treinamento'}
        </button>
      </div>

      {/* Lista de jobs */}
      <div className={cardHeader}>
        <span className={cardTitle}>Histórico de Jobs</span>
      </div>

      {jobs.length === 0 && (
        <div style={{ color: vars.color.textMuted, fontSize: '13px', padding: '16px 0' }}>
          Nenhum job de treinamento iniciado ainda.
        </div>
      )}

      <div style={{ display: 'grid', gap: '12px', marginBottom: '32px' }}>
        {jobs.map(job => (
          <div key={job.id} className={card}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span
                    style={{
                      width: '8px', height: '8px', borderRadius: '50%',
                      background: STATUS_COLORS[job.status] ?? vars.color.textMuted,
                      display: 'inline-block',
                      animation: job.status === 'running' ? 'pulse 1.5s infinite' : undefined,
                    }}
                  />
                  <span style={{ fontWeight: 600, fontSize: '14px' }}>{STATUS_LABELS[job.status] ?? job.status}</span>
                </div>
                <div style={{ fontSize: '12px', color: vars.color.textMuted }}>
                  Frames: {job.frame_count} · Criado: {new Date(job.created_at).toLocaleString('pt-BR')}
                </div>
                {job.error_message && (
                  <div style={{ fontSize: '12px', color: vars.color.danger, marginTop: '4px' }}>
                    Erro: {job.error_message}
                  </div>
                )}
                {job.status === 'running' && (
                  <div style={{ fontSize: '12px', color: '#FFB74D', marginTop: '4px' }}>
                    Treinamento em andamento…
                  </div>
                )}
              </div>

              {/* Ativar modelo completado */}
              {job.status === 'completed' && job.model_id && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'flex-end' }}>
                  {cameras.length > 1 && (
                    <select
                      id="activate-camera-select"
                      name="activate-camera-select"
                      value={selectedCamera}
                      onChange={e => setSelectedCamera(e.target.value)}
                      style={{ padding: '4px 8px', borderRadius: '4px', border: `1px solid ${vars.color.borderStrong}`, background: vars.color.bgSurface, color: vars.color.textSecondary, fontSize: '12px' }}
                    >
                      {cameras.map(c => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  )}
                  <button
                    onClick={() => handleActivate(job.model_id!)}
                    disabled={activatingModel === job.model_id}
                    style={{
                      padding: '6px 14px',
                      borderRadius: '4px',
                      border: 'none',
                      background: '#43D18622',
                      color: vars.color.success,
                      fontWeight: 600,
                      fontSize: '12px',
                      cursor: 'pointer',
                    }}
                  >
                    {activatingModel === job.model_id ? 'Ativando…' : 'Ativar Modelo'}
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
