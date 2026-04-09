/**
 * MonitoringPage — Player HLS + overlay de detecções em tempo real.
 */
import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CameraPlayer } from '../components/monitoring/CameraPlayer'
import { DetectionOverlay } from '../components/monitoring/DetectionOverlay'
import { useMonitoringSocket } from '../hooks/useMonitoringSocket'
import { api, getToken } from '../services/api'
import type { Camera, ApiResponse } from '../types'

const WS_URL = (import.meta as any).env?.VITE_WS_URL
  || (import.meta as any).env?.VITE_API_URL
  || ''

export function MonitoringPage() {
  const [searchParams] = useSearchParams()
  const selectedId = searchParams.get('camera')
  const token = getToken()

  const [cameras, setCameras] = useState<Camera[]>([])
  const [activeCameraId, setActiveCameraId] = useState<string | null>(selectedId)

  const { connected, detections, alerts, subscribeCamera, unsubscribeCamera } =
    useMonitoringSocket({ wsUrl: WS_URL, token: token || '', enabled: !!token })

  useEffect(() => {
    api.get<ApiResponse<any>>('/cameras').then(res => {
      const data = res.data as any
      const list: Camera[] = Array.isArray(data) ? data : (data?.cameras || [])
      setCameras(list.filter((c: Camera) => c.stream_status === 'active'))
    }).catch(console.error)
  }, [])

  useEffect(() => {
    if (!activeCameraId) return
    subscribeCamera(activeCameraId)
    return () => unsubscribeCamera(activeCameraId)
  }, [activeCameraId, subscribeCamera, unsubscribeCamera])

  const apiBase = (import.meta as any).env?.VITE_API_URL || ''
  const hlsUrl = activeCameraId
    ? `${apiBase}/api/cameras/${activeCameraId}/stream/stream.m3u8`
    : ''
  const currentDetections = activeCameraId ? (detections[activeCameraId] || []) : []

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ color: '#e2e8f0', margin: 0 }}>Monitoramento</h2>
        <span style={{ fontSize: 12, fontWeight: 600, color: connected ? '#22c55e' : '#ef4444' }}>
          ● {connected ? 'WebSocket conectado' : 'Desconectado'}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 16 }}>
        {/* Lista de streams ativos */}
        <div>
          <p style={{ color: '#64748b', fontSize: 11, fontWeight: 700, letterSpacing: 1, marginBottom: 8 }}>
            STREAMS ATIVOS
          </p>
          {cameras.length === 0 ? (
            <p style={{ color: '#475569', fontSize: 13 }}>Nenhum stream ativo</p>
          ) : (
            cameras.map(cam => (
              <button
                key={cam.id}
                onClick={() => setActiveCameraId(cam.id)}
                style={{
                  width: '100%', padding: '10px 12px', marginBottom: 6,
                  borderRadius: 8, border: 'none', cursor: 'pointer',
                  textAlign: 'left', fontSize: 13,
                  background: activeCameraId === cam.id ? '#1e40af' : '#1e293b',
                  color: activeCameraId === cam.id ? '#fff' : '#94a3b8',
                }}
              >
                {cam.name}
                {(detections[cam.id]?.length ?? 0) > 0 && (
                  <span style={{ marginLeft: 6, fontSize: 11, color: '#fbbf24' }}>
                    {detections[cam.id].length}det
                  </span>
                )}
              </button>
            ))
          )}

          {alerts.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <p style={{ color: '#ef4444', fontSize: 11, fontWeight: 700, letterSpacing: 1, marginBottom: 8 }}>
                ⚠ ALERTAS ({alerts.length})
              </p>
              {alerts.slice(0, 5).map((a, i) => (
                <div key={i} style={{
                  padding: '8px 10px', background: '#1e293b', borderRadius: 6,
                  border: '1px solid #dc262655', marginBottom: 6,
                }}>
                  <p style={{ color: '#fca5a5', fontSize: 11, margin: 0 }}>
                    {a.violations.map(v => v.class).join(', ')}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Player + overlay */}
        <div>
          {activeCameraId && hlsUrl ? (
            <div style={{ position: 'relative', display: 'inline-block' }}>
              <CameraPlayer
                cameraId={activeCameraId}
                hlsUrl={hlsUrl}
                width={640}
                height={360}
              />
              <DetectionOverlay
                detections={currentDetections}
                videoWidth={640}
                videoHeight={360}
                displayWidth={640}
                displayHeight={360}
              />
            </div>
          ) : (
            <div style={{
              width: 640, height: 360, background: '#1e293b', borderRadius: 12,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#475569', fontSize: 14,
            }}>
              Selecione uma câmera com stream ativo
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
