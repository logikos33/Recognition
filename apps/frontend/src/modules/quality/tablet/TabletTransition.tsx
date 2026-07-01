/**
 * TabletTransition — peça aprovada na Bancada A, aguardando movimentação para Bancada B.
 *
 * Exibida quando status = 'waiting_bench_b' na Bancada A.
 * Operador confirma que a peça foi fisicamente movida via POST .../release.
 */
import { useState, type FC } from 'react'
import { api } from '../../../services/api'
import type { QualityPiece } from '../types/gate'
import { wrapper, arrow, heading, subheading, pieceLabel, confirmBtn } from './TabletTransition.css'

interface Props {
  piece: QualityPiece | null
}

export const TabletTransition: FC<Props> = ({ piece }) => {
  const [loading, setLoading] = useState(false)

  // Libera a peça para a Bancada B — backend atualiza status e emite station_state
  const handleRelease = async () => {
    if (!piece || loading) return
    setLoading(true)
    try {
      await api.post(`/v1/quality/gate/pieces/${piece.id}/release-to-bench-b`)
    } catch (e) {
      console.error('tablet:release_error', e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={wrapper}>
      <div className={arrow}>➡</div>

      <div className={heading}>V1 e V2 Aprovadas</div>

      <div className={subheading}>Mover peça para Bancada B</div>

      {piece && (
        <div className={pieceLabel}>Peça {piece.piece_number}</div>
      )}

      <button
        onClick={handleRelease}
        disabled={loading}
        className={confirmBtn({ loading })}
      >
        {loading ? 'Liberando...' : '✓ CONFIRMAR MOVIMENTAÇÃO'}
      </button>
    </div>
  )
}
