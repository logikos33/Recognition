/**
 * TabletResultNOK — validação reprovada. Tela inteira vermelha.
 *
 * Exibe foto do defeito (se disponível), classe do defeito e confiança.
 * Botões de ação:
 *   CORRIGIR       → POST /api/v1/quality/gate/rework/start, chama onCorrected
 *   FALSO POSITIVO → POST /api/v1/quality/gate/pieces/:id/false-positive
 */
import { useState, type FC } from 'react'
import { api, API_BASE } from '../../../services/api'
import type { QualityPiece, InspectionResultEvent } from '../types/gate'

interface Props {
  piece: QualityPiece | null
  result: InspectionResultEvent | null
  station: string
  /** Chamado após iniciar retrabalho — volta para TabletValidating */
  onCorrected: () => void
}

export const TabletResultNOK: FC<Props> = ({ piece, result, station, onCorrected }) => {
  // null = nenhuma ação em andamento, 'rework' | 'fp' = botão ativo
  const [loading, setLoading] = useState<string | null>(null)

  // Inicia retrabalho e notifica o kiosk
  const handleRework = async () => {
    if (!piece || loading) return
    setLoading('rework')
    try {
      await api.post('/v1/quality/gate/reworks', {
        piece_id: piece.id,
        validation_type: result?.validation_type,
        station,
      })
      onCorrected()
    } catch (e) {
      console.error('tablet:rework_error', e)
    } finally {
      setLoading(null)
    }
  }

  // Marca resultado como falso positivo — operador descartou a detecção
  const handleFalsePositive = async () => {
    if (!piece || !result || loading) return
    setLoading('fp')
    try {
      await api.post(`/v1/quality/gate/pieces/${piece.id}/false-positive`, {
        inspection_id: result.camera_id,
      })
    } catch (e) {
      console.error('tablet:false_positive_error', e)
    } finally {
      setLoading(null)
    }
  }

  // URL da foto do defeito (servida pela API com autenticação de rede interna)
  // API_BASE já inclui o prefixo /api — usar apenas o path a partir de /v1/
  const photoUrl = result?.photo_path
    ? `${API_BASE}/v1/quality/gate/photos/${encodeURIComponent(result.photo_path)}`
    : null

  // Primeiro defeito detectado para exibir na tela
  const primaryDefect = result?.detections?.find(d => d.is_defect) ?? result?.detections?.[0]

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: '#7F1D1D', // allow: tablet kiosk danger palette
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff', // allow: tablet kiosk danger palette
        padding: 24,
        boxSizing: 'border-box',
      }}
    >
      {/* X grande */}
      <div style={{ fontSize: 72, marginBottom: 16 }}>✗</div>

      <div
        style={{
          fontSize: 40,
          fontWeight: 900,
          color: '#FCA5A5', // allow: tablet kiosk danger palette
          letterSpacing: 3,
          marginBottom: 8,
        }}
      >
        NÃO CONFORME
      </div>

      <div style={{ fontSize: 20, color: '#FCA5A5' /* allow: tablet kiosk danger palette */, marginBottom: 24 }}>
        {result?.validation_type?.toUpperCase() ?? ''} — Reprovado
      </div>

      {/* Foto do defeito detectado */}
      {photoUrl && (
        <img
          src={photoUrl}
          alt="Defeito detectado"
          style={{
            maxWidth: 480,
            maxHeight: 280,
            borderRadius: 8,
            marginBottom: 24,
            border: '3px solid #EF4444', // allow: tablet kiosk danger palette
            objectFit: 'contain',
          }}
        />
      )}

      {/* Descrição do defeito principal */}
      {primaryDefect && (
        <div
          style={{
            fontSize: 16,
            color: '#FCA5A5', // allow: tablet kiosk danger palette
            marginBottom: 24,
            textAlign: 'center',
          }}
        >
          Defeito: {primaryDefect.class} ({(primaryDefect.confidence * 100).toFixed(0)}% confiança)
        </div>
      )}

      {/* Botões de ação do operador */}
      <div style={{ display: 'flex', gap: 24 }}>
        <button
          onClick={handleRework}
          disabled={!!loading}
          style={{
            fontSize: 20,
            fontWeight: 700,
            padding: '18px 40px',
            background: loading === 'rework' ? '#374151' : '#DC2626', // allow: tablet kiosk danger palette
            color: '#fff', // allow: white on colored button
            border: '2px solid #EF4444', // allow: tablet kiosk danger palette
            borderRadius: 10,
            cursor: loading ? 'not-allowed' : 'pointer',
            minHeight: 65,
          }}
        >
          🔧 CORRIGIR
        </button>

        <button
          onClick={handleFalsePositive}
          disabled={!!loading}
          style={{
            fontSize: 20,
            fontWeight: 700,
            padding: '18px 40px',
            background: 'transparent',
            color: '#FCA5A5', // allow: tablet kiosk danger palette
            border: '2px solid #FCA5A5', // allow: tablet kiosk danger palette
            borderRadius: 10,
            cursor: loading ? 'not-allowed' : 'pointer',
            minHeight: 65,
          }}
        >
          ⚠ FALSO POSITIVO
        </button>
      </div>
    </div>
  )
}
