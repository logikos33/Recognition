/**
 * TabletValidating — análise em andamento no Quality Gate.
 *
 * Exibida enquanto o worker YOLO processa a inspeção.
 * Mostra spinner CSS + label da validação atual (V1/V2/V3).
 */
import type { FC } from 'react'
import type { QualityPiece } from '../types/gate'

interface Props {
  piece: QualityPiece | null
}

// Mapeamento de status → texto descritivo da validação
const VALIDATION_LABEL: Record<string, string> = {
  validating_v1: 'V1 — Fio Alinhado no Anel',
  validating_v2: 'V2 — Saída Isolada',
  validating_v3: 'V3 — Anel Encapado',
}

export const TabletValidating: FC<Props> = ({ piece }) => {
  const label = VALIDATION_LABEL[piece?.status ?? ''] ?? 'Analisando...'

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: '#0F172A',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff',
      }}
    >
      {/* Spinner via CSS keyframe injetado inline */}
      <style>{`@keyframes tablet-spin { to { transform: rotate(360deg) } }`}</style>
      <div
        style={{
          width: 80,
          height: 80,
          borderRadius: '50%',
          border: '6px solid #1E3A5F',
          borderTopColor: '#3B82F6',
          animation: 'tablet-spin 1s linear infinite',
          marginBottom: 32,
        }}
      />

      <div style={{ fontSize: 28, fontWeight: 700, marginBottom: 12 }}>Analisando</div>
      <div style={{ fontSize: 20, color: '#60A5FA' }}>{label}</div>

      {/* Número da peça em processo */}
      {piece && (
        <div style={{ marginTop: 40, fontSize: 16, color: '#4A6080' }}>
          Peça {piece.piece_number}
        </div>
      )}
    </div>
  )
}
