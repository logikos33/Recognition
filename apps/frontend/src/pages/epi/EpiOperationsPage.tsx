/**
 * Página de operações para módulo EPI.
 * Usa TrainingModeLayout com moduleId='ppe'.
 * Obtém cameraId via useParams.
 */
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { TrainingModeLayout } from '../../components/training/TrainingModeLayout'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export function EpiOperationsPage() {
  const { cameraId } = useParams<{ cameraId: string }>()
  const navigate = useNavigate()

  if (!cameraId) {
    return (
      <div style={{ padding: 32, color: '#888' }}>
        Câmera não encontrada
      </div>
    )
  }

  // NÃO anexar o JWT em query string (vaza credencial de 24h em logs/histórico).
  // Autenticação do HLS deve usar token de stream de curta duração escopado ao
  // camera_id (pendente — ver SECURITY_AUDIT.md, serve_hls).
  const hlsUrl = `${API_BASE}/api/cameras/${cameraId}/stream/stream.m3u8`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0a0a0a' }}>
      {/* Breadcrumb */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '10px 16px',
          borderBottom: '1px solid #1e1e1e',
          background: '#0d0d0d',
        }}
      >
        <button
          onClick={() => navigate('/epi/cameras')}
          style={{
            display: 'flex', alignItems: 'center', gap: 4,
            background: 'transparent', border: 'none', color: '#888',
            cursor: 'pointer', fontSize: 13, padding: '2px 4px',
          }}
        >
          <ArrowLeft size={14} />
          Câmeras
        </button>
        <span style={{ color: '#444' }}>/</span>
        <span style={{ fontSize: 13, color: '#666' }}>Câmera {cameraId}</span>
        <span style={{ color: '#444' }}>/</span>
        <span style={{ fontSize: 13, color: '#e0e0e0' }}>Operações</span>
      </div>

      {/* Main layout */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <TrainingModeLayout
          moduleId="ppe"
          cameraId={cameraId}
          hlsUrl={hlsUrl}
          title={`Operações — Câmera ${cameraId}`}
        />
      </div>
    </div>
  )
}
