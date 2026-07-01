/**
 * TabletIdentified — peça identificada, aguardando operador iniciar inspeção.
 *
 * Exibe número da peça, OP e o progresso das validações (V1→V2→V3).
 * Botão "INICIAR INSPEÇÃO" chama POST /api/v1/quality/gate/pieces/:id/inspect.
 */
import { useState } from 'react'
import type { FC } from 'react'
import { api } from '../../../services/api'
import type { QualityPiece } from '../types/gate'

interface Props {
  piece: QualityPiece | null
  station: string
}

export const TabletIdentified: FC<Props> = ({ piece, station }) => {
  const [loading, setLoading] = useState(false)

  // Dispara inspeção — o backend vai emitir quality_gate_result via WebSocket
  const handleStart = async () => {
    if (!piece || loading) return
    setLoading(true)
    try {
      await api.post(`/v1/quality/gate/pieces/${piece.id}/inspect`, { station })
    } catch (e) {
      console.error('tablet:inspect_error', e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: '#1B2A4A', // allow: tablet kiosk navy palette
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff', // allow: tablet kiosk navy palette
      }}
    >
      {/* Indicador de progresso V1 → V2 → V3 */}
      <ValidationProgress status={piece?.status} />

      <div style={{ fontSize: 24, color: '#8BA7CC', marginBottom: 8 }}>{/* allow: tablet kiosk navy palette */}Peça Identificada</div>

      <div style={{ fontSize: 56, fontWeight: 900, letterSpacing: 4, marginBottom: 8 }}>
        {piece?.piece_number ?? '—'}
      </div>

      {piece?.work_order && (
        <div style={{ fontSize: 22, color: '#8BA7CC', marginBottom: 40 }}>{/* allow: tablet kiosk navy palette */}
          OP: {piece.work_order}
        </div>
      )}

      <button
        onClick={handleStart}
        disabled={loading}
        style={{
          fontSize: 24,
          fontWeight: 700,
          padding: '20px 60px',
          background: loading ? '#4A6080' : '#2563EB', // allow: tablet kiosk navy palette
          color: '#fff', // allow: tablet kiosk navy palette
          border: 'none',
          borderRadius: 12,
          cursor: loading ? 'not-allowed' : 'pointer',
          minHeight: 70,
          letterSpacing: 2,
          boxShadow: '0 4px 20px rgba(37,99,235,0.4)', // allow: tablet kiosk navy palette
        }}
      >
        {loading ? 'INICIANDO...' : '▶ INICIAR INSPEÇÃO'}
      </button>
    </div>
  )
}

// ── Subcomponente: barra de progresso das validações ─────────────────────────

function ValidationProgress({ status }: { status?: string }) {
  const approved = status === 'approved'

  // Cada círculo fica ativo se a peça chegou àquela etapa ou passou dela
  const v1Active =
    approved ||
    (status !== undefined &&
      ['validating_v1', 'rework_v1', 'validating_v2', 'rework_v2',
       'waiting_bench_b', 'validating_v3', 'rework_v3'].includes(status))
  const v2Active =
    approved ||
    (status !== undefined &&
      ['validating_v2', 'rework_v2', 'waiting_bench_b',
       'validating_v3', 'rework_v3'].includes(status))
  const v3Active =
    approved ||
    (status !== undefined && ['validating_v3', 'rework_v3'].includes(status))

  const steps = [
    { label: 'V1', active: v1Active },
    { label: 'V2', active: v2Active },
    { label: 'V3', active: v3Active },
  ]

  return (
    <div style={{ display: 'flex', gap: 24, marginBottom: 40, alignItems: 'center' }}>
      {steps.map((v, i) => (
        <div key={v.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Círculo da etapa */}
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: '50%',
              background: approved ? '#22C55E' : v.active ? '#2563EB' : '#1B2A4A', // allow: tablet kiosk navy palette
              border: `3px solid ${approved ? '#22C55E' : v.active ? '#60A5FA' : '#4A6080'}`, // allow: tablet kiosk navy palette
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff', // allow: tablet kiosk navy palette
              fontWeight: 700,
              fontSize: 14,
            }}
          >
            {v.label}
          </div>
          {/* Conector entre etapas */}
          {i < steps.length - 1 && (
            <div style={{ width: 40, height: 3, background: '#4A6080' /* allow: tablet kiosk navy palette */ }} />
          )}
        </div>
      ))}
    </div>
  )
}
