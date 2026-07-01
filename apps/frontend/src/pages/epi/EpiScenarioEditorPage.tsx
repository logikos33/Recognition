/**
 * Página de editor visual de cenário para módulo EPI.
 * Rota: /epi/cameras/:cameraId/scenario
 */
import { useParams, useNavigate } from 'react-router-dom'
import { ScenarioEditor } from '../../components/scenario/ScenarioEditor'
import { getToken } from '../../services/api'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export function EpiScenarioEditorPage() {
  const { cameraId } = useParams<{ cameraId: string }>()
  const navigate = useNavigate()
  const token = getToken()

  if (!cameraId) {
    return (
      <div style={{ padding: 32, color: '#888', fontSize: 13 }}>
        Câmera não encontrada
      </div>
    )
  }

  const hlsUrl = token
    ? `${API_BASE}/api/cameras/${cameraId}/stream/stream.m3u8?token=${token}`
    : undefined

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0a0a0a' }}>
      <ScenarioEditor
        cameraId={cameraId}
        hlsUrl={hlsUrl}
        onBack={() => navigate(`/epi/cameras/${cameraId}/operations`)}
      />
    </div>
  )
}
