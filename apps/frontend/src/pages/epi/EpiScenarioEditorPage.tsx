/**
 * Página de editor visual de cenário para módulo EPI.
 * Rota: /epi/cameras/:cameraId/scenario
 */
import { useParams, useNavigate } from 'react-router-dom'
import { ScenarioEditor } from '../../components/scenario/ScenarioEditor'
import { useLiveView } from '../../hooks/useLiveView'
import { vars } from '../../styles/theme.css'

export function EpiScenarioEditorPage() {
  const { cameraId } = useParams<{ cameraId: string }>()
  const navigate = useNavigate()
  // Antes do early return — Rules of Hooks.
  const { hlsUrl: liveViewUrl } = useLiveView(cameraId, !!cameraId)

  if (!cameraId) {
    return (
      <div style={{ padding: 32, color: vars.color.textMuted, fontSize: 13 }}>
        Câmera não encontrada
      </div>
    )
  }

  // O token de playback viaja no PATH, não em query — `?token=` era ignorado
  // pelo serve_hls e a tela caía em 404. A URL vem pronta do backend.
  const hlsUrl = liveViewUrl ?? undefined

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: vars.color.bgBase }}>
      <ScenarioEditor
        cameraId={cameraId}
        hlsUrl={hlsUrl}
        onBack={() => navigate(`/epi/cameras/${cameraId}/operations`)}
      />
    </div>
  )
}
