/**
 * TabletResultOK — validação aprovada. Tela inteira verde.
 *
 * Auto-avança para a próxima validação após 3 segundos via callback onAdvance.
 * Exibe: checkmark grande, label da validação aprovada, número da peça.
 */
import { useEffect, type FC } from 'react'
import type { QualityPiece, InspectionResultEvent } from '../types/gate'

interface Props {
  piece: QualityPiece | null
  result: InspectionResultEvent | null
  /** Chamado após 3s — volta para TabletValidating esperando próxima inspeção */
  onAdvance: () => void
}

export const TabletResultOK: FC<Props> = ({ piece, result, onAdvance }) => {
  // Auto-avança após 3 segundos
  useEffect(() => {
    const t = setTimeout(onAdvance, 3000)
    return () => clearTimeout(t)
  }, [onAdvance])

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: '#14532D',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff',
      }}
    >
      {/* Checkmark grande */}
      <div style={{ fontSize: 120, marginBottom: 24 }}>✓</div>

      <div
        style={{
          fontSize: 48,
          fontWeight: 900,
          color: '#4ADE80',
          letterSpacing: 4,
          marginBottom: 12,
        }}
      >
        CONFORME
      </div>

      <div style={{ fontSize: 22, color: '#86EFAC' }}>
        {result?.validation_type?.toUpperCase() ?? ''} — Aprovado
      </div>

      {piece && (
        <div style={{ marginTop: 24, fontSize: 18, color: '#4ADE80', opacity: 0.7 }}>
          Peça {piece.piece_number}
        </div>
      )}

      {/* Indicador de auto-avanço */}
      <div style={{ marginTop: 48, fontSize: 14, color: '#4ADE80', opacity: 0.5 }}>
        Próxima validação em 3s...
      </div>
    </div>
  )
}
