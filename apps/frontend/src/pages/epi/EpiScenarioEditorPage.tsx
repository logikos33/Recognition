/**
 * Página de editor visual de cenário para módulo EPI.
 * Rota: /epi/cameras/:cameraId/scenario
 */
import { useParams, useNavigate } from 'react-router-dom'
import { ScenarioEditor } from '../../components/scenario/ScenarioEditor'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export function EpiScenarioEditorPage() {
  const { cameraId } = useParams<{ cameraId: string }>()
  const navigate = useNavigate()

  if (!cameraId) {
    return (
      <div style={{ padding: 32, color: '#888', fontSize: 13 }}>
        Câmera não encontrada
      </div>
    )
  }

  // NÃO anexar o JWT em query string (vaza credencial de 24h em logs/histórico).
  // Ver SECURITY_AUDIT.md (serve_hls / token de stream escopado, pendente).
  const hlsUrl = `${API_BASE}/api/cameras/${cameraId}/stream/stream.m3u8`

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
