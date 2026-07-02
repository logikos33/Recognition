import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Activity, Server, Video } from 'lucide-react'
import { api } from '../services/api'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { vars } from '../styles/theme.css'

interface SystemHealth {
  status: string
  checks: { database: boolean; redis: boolean }
}

interface Worker {
  worker_id: string
  status: string
  active_tasks: number
}

interface WorkerStatus {
  workers: Worker[]
  status: string
}

interface Camera {
  id: string
  name: string
  is_streaming: boolean
  location?: string
  manufacturer?: string
}

interface StreamStatus {
  streaming: boolean
  gateway_online: boolean
  ttl_seconds?: number
}

interface CameraWithStatus extends Camera {
  streamStatus?: StreamStatus
}

interface HealthApiResponse {
  status: string
  checks: { database: boolean; redis: boolean }
}

interface WorkerApiResponse {
  workers: Worker[]
  status: string
}

interface CamerasApiResponse {
  status: string
  data: { cameras: Camera[] }
}

interface StreamStatusApiResponse {
  status: string
  data: StreamStatus
}

function StatusChip({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: '5px 12px',
      borderRadius: 999,
      fontSize: 12,
      fontWeight: 600,
      background: ok ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
      border: `1px solid ${ok ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
      color: ok ? vars.color.success : '#ef4444',
    }}>
      <span style={{
        width: 7,
        height: 7,
        borderRadius: '50%',
        background: ok ? vars.color.success : '#ef4444',
        flexShrink: 0,
      }} />
      {label}
    </div>
  )
}

function WorkerBadge({ status }: { status: string }) {
  const online = status === 'online'
  return (
    <span style={{
      padding: '2px 8px',
      borderRadius: 999,
      fontSize: 11,
      fontWeight: 700,
      background: online ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
      border: `1px solid ${online ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
      color: online ? vars.color.success : '#ef4444',
    }}>
      {online ? 'online' : 'offline'}
    </span>
  )
}

function SectionTitle({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
      {icon}
      <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#f1f5f9' }}>
        {title}
      </h3>
    </div>
  )
}

export function StreamHealthPage() {
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null)
  const [workerStatus, setWorkerStatus] = useState<WorkerStatus | null>(null)
  const [cameras, setCameras] = useState<CameraWithStatus[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const [healthRes, workerRes, camerasRes] = await Promise.all([
        api.get<HealthApiResponse>('/health').catch(() => null),
        api.get<WorkerApiResponse>('/streams/status').catch(() => null),
        api.get<CamerasApiResponse>('/cameras').catch(() => null),
      ])

      if (healthRes) {
        setSystemHealth({ status: healthRes.status, checks: healthRes.checks })
      }

      if (workerRes) {
        setWorkerStatus({ workers: workerRes.workers ?? [], status: workerRes.status })
      }

      const cameraList: Camera[] = camerasRes?.data?.cameras ?? []

      if (cameraList.length > 0) {
        const statusResults = await Promise.all(
          cameraList.map(cam =>
            api.get<StreamStatusApiResponse>(`/cameras/${cam.id}/stream/status`).catch(() => null)
          )
        )
        const camerasWithStatus: CameraWithStatus[] = cameraList.map((cam, i) => ({
          ...cam,
          streamStatus: statusResults[i]?.data ?? undefined,
        }))
        setCameras(camerasWithStatus)
      } else {
        setCameras([])
      }
    } catch (err) {
      console.error('StreamHealthPage load error:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const interval = setInterval(load, 15000)
    return () => clearInterval(interval)
  }, [load])

  if (loading) return <LoadingSpinner />

  const dbOk = systemHealth?.checks?.database ?? false
  const redisOk = systemHealth?.checks?.redis ?? false
  const gatewayOk = workerStatus?.status === 'ok'

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Activity size={22} style={{ color: vars.color.primaryLight }} />
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>
            Stream Health
          </h2>
        </div>
        <button
          onClick={load}
          style={{
            background: 'transparent',
            border: `1px solid ${vars.color.borderStrong}`,
            borderRadius: 6,
            color: vars.color.textSecondary,
            padding: '6px 12px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            fontSize: 12,
          }}
        >
          <RefreshCw size={13} /> Atualizar
        </button>
      </div>

      {/* Section 1 — System Status */}
      <div style={{
        background: vars.color.bgBase,
        border: `1px solid ${vars.color.bgSurface}`,
        borderRadius: 10,
        padding: 20,
        marginBottom: 20,
      }}>
        <SectionTitle icon={<Server size={16} style={{ color: vars.color.primaryLight }} />} title="Status do Sistema" />
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <StatusChip label="Database" ok={dbOk} />
          <StatusChip label="Redis" ok={redisOk} />
          <StatusChip label="Gateway" ok={gatewayOk} />
        </div>
      </div>

      {/* Section 2 — Celery Workers */}
      <div style={{
        background: vars.color.bgBase,
        border: `1px solid ${vars.color.bgSurface}`,
        borderRadius: 10,
        padding: 20,
        marginBottom: 20,
      }}>
        <SectionTitle icon={<Server size={16} style={{ color: vars.color.primaryLight }} />} title="Workers Celery" />

        {(!workerStatus || workerStatus.workers.length === 0) ? (
          <p style={{ margin: 0, color: vars.color.textMuted, fontSize: 13 }}>Nenhum worker detectado.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr>
                  {['Worker ID', 'Status', 'Tarefas Ativas'].map(col => (
                    <th key={col} style={{
                      textAlign: 'left',
                      padding: '8px 12px',
                      color: vars.color.textMuted,
                      fontWeight: 600,
                      borderBottom: `1px solid ${vars.color.bgSurface}`,
                      whiteSpace: 'nowrap',
                    }}>
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {workerStatus.workers.map(worker => (
                  <tr key={worker.worker_id} style={{ borderBottom: `1px solid ${vars.color.bgBase}` }}>
                    <td style={{ padding: '10px 12px', color: vars.color.textSecondary, fontFamily: 'monospace', fontSize: 12 }}>
                      {worker.worker_id}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <WorkerBadge status={worker.status} />
                    </td>
                    <td style={{ padding: '10px 12px', color: vars.color.textSecondary }}>
                      {worker.active_tasks}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Section 3 — Cameras */}
      <div style={{
        background: vars.color.bgBase,
        border: `1px solid ${vars.color.bgSurface}`,
        borderRadius: 10,
        padding: 20,
      }}>
        <SectionTitle icon={<Video size={16} style={{ color: '#34d399' }} />} title="Câmeras" />

        {cameras.length === 0 ? (
          <p style={{ margin: 0, color: vars.color.textMuted, fontSize: 13 }}>Nenhuma câmera cadastrada.</p>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: 12,
          }}>
            {cameras.map(cam => {
              const streaming = cam.streamStatus?.streaming ?? cam.is_streaming ?? false
              const gatewayOnline = cam.streamStatus?.gateway_online ?? false

              return (
                <div key={cam.id} style={{
                  background: vars.color.bgSurface,
                  border: `1px solid ${vars.color.borderStrong}`,
                  borderRadius: 8,
                  padding: 14,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                    <span style={{
                      fontWeight: 600,
                      fontSize: 13,
                      color: '#f1f5f9',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      flex: 1,
                      marginRight: 8,
                    }}>
                      {cam.name}
                    </span>
                    <span style={{
                      flexShrink: 0,
                      padding: '2px 8px',
                      borderRadius: 999,
                      fontSize: 11,
                      fontWeight: 700,
                      background: streaming ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                      border: `1px solid ${streaming ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
                      color: streaming ? vars.color.success : '#ef4444',
                    }}>
                      {streaming ? 'Online' : 'Offline'}
                    </span>
                  </div>

                  {cam.location && (
                    <div style={{ fontSize: 11, color: vars.color.textMuted, marginBottom: 6 }}>
                      {cam.location}
                    </div>
                  )}

                  <div style={{ fontSize: 12, color: vars.color.textMuted, display: 'flex', alignItems: 'center', gap: 4 }}>
                    Gateway:
                    <span style={{ color: gatewayOnline ? vars.color.success : '#ef4444', fontWeight: 600 }}>
                      {gatewayOnline ? '✓' : '✗'}
                    </span>
                    {cam.streamStatus?.ttl_seconds != null && (
                      <span style={{ color: vars.color.textMuted, marginLeft: 6 }}>
                        TTL {cam.streamStatus.ttl_seconds}s
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
