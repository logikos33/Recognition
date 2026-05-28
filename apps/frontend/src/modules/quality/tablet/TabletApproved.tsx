/**
 * TabletApproved — peça aprovada em todas as 3 validações (3/3).
 *
 * Tela celebratória verde. Exibe contagem de retrabalhos e tempo total se houve.
 * Indica que a foto de qualidade foi gerada e exportação para Wiser iniciou.
 */
import type { FC } from 'react'
import type { QualityPiece } from '../types/gate'

interface Props {
  piece: QualityPiece | null
}

export const TabletApproved: FC<Props> = ({ piece }) => {
  // Formata tempo de retrabalho em minutos arredondados
  const reworkTime =
    piece?.total_rework_time_seconds && piece.total_rework_time_seconds > 0
      ? `${Math.ceil(piece.total_rework_time_seconds / 60)} min retrabalho`
      : null

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
      {/* Troféu comemorativo */}
      <div style={{ fontSize: 100, marginBottom: 24 }}>🏆</div>

      <div
        style={{
          fontSize: 48,
          fontWeight: 900,
          color: '#4ADE80',
          letterSpacing: 4,
          marginBottom: 12,
        }}
      >
        APROVADA 3/3
      </div>

      <div style={{ fontSize: 24, color: '#86EFAC', marginBottom: 8 }}>
        Todas as validações passaram
      </div>

      {/* Número da peça e OP */}
      {piece && (
        <div style={{ fontSize: 32, fontWeight: 700, color: '#4ADE80', marginTop: 16 }}>
          Peça {piece.piece_number}
        </div>
      )}
      {piece?.work_order && (
        <div style={{ fontSize: 18, color: '#86EFAC', marginTop: 8 }}>
          OP: {piece.work_order}
        </div>
      )}

      {/* Métricas de retrabalho (exibidas apenas se houve) */}
      {(piece?.total_rework_count ?? 0) > 0 && (
        <div style={{ marginTop: 32, display: 'flex', gap: 32 }}>
          <div style={{ textAlign: 'center', color: '#86EFAC' }}>
            <div style={{ fontSize: 28, fontWeight: 700 }}>{piece!.total_rework_count}</div>
            <div style={{ fontSize: 14 }}>retrabalhos</div>
          </div>
          {reworkTime && (
            <div style={{ textAlign: 'center', color: '#86EFAC' }}>
              <div style={{ fontSize: 28, fontWeight: 700 }}>{reworkTime}</div>
            </div>
          )}
        </div>
      )}

      {/* Indicador de exportação Wiser */}
      <div style={{ marginTop: 48, fontSize: 16, color: '#4ADE80', opacity: 0.5 }}>
        Foto de qualidade gerada → Exportando para Wiser...
      </div>
    </div>
  )
}
