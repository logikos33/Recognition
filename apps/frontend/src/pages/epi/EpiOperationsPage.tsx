/**
 * Página de operações para módulo EPI.
 * Usa TrainingModeLayout com moduleId='ppe'.
 * Obtém cameraId via useParams.
 */
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { TrainingModeLayout } from '../../components/training/TrainingModeLayout'
import { getToken } from '../../services/api'
import { vars } from '../../styles/theme.css'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export function EpiOperationsPage() {
  const { cameraId } = useParams<{ cameraId: string }>()
  const navigate = useNavigate()
  const token = getToken()

  if (!cameraId) {
    return (
      <div style={{ padding: 32, color: vars.color.textMuted }}>
        Câmera não encontrada
      </div>
    )
  }

  const hlsUrl = `${API_BASE}/api/cameras/${cameraId}/stream/stream.m3u8?token=${token ?? ''}`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: vars.color.bgBase }}>
      {/* Breadcrumb */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '10px 16px',
          borderBottom: `1px solid ${vars.color.borderDefault}`,
          background: vars.color.bgBase,
        }}
      >
        <button
          onClick={() => navigate('/epi/cameras')}
          style={{
            display: 'flex', alignItems: 'center', gap: 4,
            background: 'transparent', border: 'none', color: vars.color.textMuted,
            cursor: 'pointer', fontSize: 13, padding: '2px 4px',
          }}
        >
          <ArrowLeft size={14} />
          Câmeras
        </button>
        <span style={{ color: vars.color.textPrimary }}>/</span>
        <span style={{ fontSize: 13, color: vars.color.textMuted }}>Câmera {cameraId}</span>
        <span style={{ color: vars.color.textPrimary }}>/</span>
        <span style={{ fontSize: 13, color: vars.color.textSecondary }}>Operações</span>
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
