/**
 * TabletTransition — peça aprovada na Bancada A, aguardando movimentação para Bancada B.
 *
 * Exibida quando status = 'waiting_bench_b' na Bancada A.
 * Operador confirma que a peça foi fisicamente movida via POST .../release.
 */
import { useState, type FC } from 'react'
import type { QualityPiece } from '../types/gate'

interface Props {
  piece: QualityPiece | null
}

export const TabletTransition: FC<Props> = ({ piece }) => {
  const [loading, setLoading] = useState(false)
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001'

  // Libera a peça para a Bancada B — backend atualiza status e emite station_state
  const handleRelease = async () => {
    if (!piece || loading) return
    setLoading(true)
    try {
      await fetch(`${API_URL}/api/v1/quality/gate/pieces/${piece.id}/release`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    } catch (e) {
      console.error('tablet:release_error', e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: '#1E3A5F',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff',
      }}
    >
      {/* Seta indicando movimentação */}
      <div style={{ fontSize: 72, marginBottom: 24 }}>➡</div>

      <div style={{ fontSize: 36, fontWeight: 700, color: '#60A5FA', marginBottom: 12 }}>
        V1 e V2 Aprovadas
      </div>

      <div style={{ fontSize: 22, color: '#93C5FD', marginBottom: 40 }}>
        Mover peça para Bancada B
      </div>

      {piece && (
        <div style={{ fontSize: 18, color: '#60A5FA', marginBottom: 40 }}>
          Peça {piece.piece_number}
        </div>
      )}

      <button
        onClick={handleRelease}
        disabled={loading}
        style={{
          fontSize: 22,
          fontWeight: 700,
          padding: '20px 60px',
          background: loading ? '#374151' : '#2563EB',
          color: '#fff',
          border: 'none',
          borderRadius: 12,
          cursor: loading ? 'not-allowed' : 'pointer',
          minHeight: 70,
        }}
      >
        {loading ? 'Liberando...' : '✓ CONFIRMAR MOVIMENTAÇÃO'}
      </button>
    </div>
  )
}
