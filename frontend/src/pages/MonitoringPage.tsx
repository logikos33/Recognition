/**
 * MonitoringPage — Player HLS + overlay de detecções em tempo real.
 * Lógica de WebSocket e HLS preservada integralmente.
 */
import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CameraPlayer } from '../components/monitoring/CameraPlayer'
import { DetectionOverlay } from '../components/monitoring/DetectionOverlay'
import { useMonitoringSocket } from '../hooks/useMonitoringSocket'
import { api, getToken } from '../services/api'
import type { Camera, ApiResponse } from '../types'
import {
  page, pageHeader, pageTitle, wsStatus, layout, sidebarLabel,
  emptyText, cameraBtn, detectionCount, alertsLabel, alertItem, alertText,
  playerWrapper, noStream,
} from './MonitoringPage.css'

const WS_URL = import.meta.env.VITE_WS_URL || import.meta.env.VITE_API_URL || ''

export function MonitoringPage() {
  const [searchParams] = useSearchParams()
  const selectedId = searchParams.get('camera')
  const token = getToken()

  const [cameras, setCameras] = useState<Camera[]>([])
  const [activeCameraId, setActiveCameraId] = useState<string | null>(selectedId)

  const { connected, detections, alerts, subscribeCamera, unsubscribeCamera } =
    useMonitoringSocket({ wsUrl: WS_URL, token: token || '', enabled: !!token })

  useEffect(() => {
    api.get<ApiResponse<unknown>>('/cameras').then(res => {
      const data = res.data as { cameras?: Camera[] }
      const list: Camera[] = Array.isArray(res.data) ? (res.data as Camera[]) : (data?.cameras || [])
      setCameras(list.filter((c: Camera) => c.stream_status === 'active'))
    }).catch(console.error)
  }, [])

  useEffect(() => {
    if (!activeCameraId) return
    subscribeCamera(activeCameraId)
    return () => unsubscribeCamera(activeCameraId)
  }, [activeCameraId, subscribeCamera, unsubscribeCamera])

  const apiBase = import.meta.env.VITE_API_URL || ''
  const hlsUrl = activeCameraId ? `${apiBase}/api/cameras/${activeCameraId}/stream/stream.m3u8` : ''
  const currentDetections = activeCameraId ? (detections[activeCameraId] || []) : []

  return (
    <div className={page}>
      <div className={pageHeader}>
        <h2 className={pageTitle}>Monitoramento</h2>
        <span className={wsStatus({ connected })}>
          ● {connected ? 'WebSocket conectado' : 'Desconectado'}
        </span>
      </div>

      <div className={layout}>
        {/* Sidebar: lista de streams */}
        <div>
          <p className={sidebarLabel}>STREAMS ATIVOS</p>
          {cameras.length === 0 ? (
            <p className={emptyText}>Nenhum stream ativo</p>
          ) : cameras.map(cam => (
            <button
              key={cam.id}
              className={cameraBtn({ active: activeCameraId === cam.id })}
              onClick={() => setActiveCameraId(cam.id)}
            >
              {cam.name}
              {(detections[cam.id]?.length ?? 0) > 0 && (
                <span className={detectionCount}>{detections[cam.id].length}det</span>
              )}
            </button>
          ))}

          {alerts.length > 0 && (
            <div>
              <p className={alertsLabel}>⚠ ALERTAS ({alerts.length})</p>
              {alerts.slice(0, 5).map((a, i) => (
                <div key={i} className={alertItem}>
                  <p className={alertText}>{a.violations.map(v => v.class).join(', ')}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Player + overlay */}
        <div>
          {activeCameraId && hlsUrl ? (
            <div className={playerWrapper}>
              <CameraPlayer cameraId={activeCameraId} hlsUrl={hlsUrl} width={640} height={360} />
              <DetectionOverlay detections={currentDetections}
                videoWidth={640} videoHeight={360} displayWidth={640} displayHeight={360} />
            </div>
          ) : (
            <div className={noStream}>Selecione uma câmera com stream ativo</div>
          )}
        </div>
      </div>
    </div>
  )
}
