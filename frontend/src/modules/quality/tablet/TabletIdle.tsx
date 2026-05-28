/**
 * TabletIdle — tela de espera do tablet de bancada.
 *
 * Exibida quando não há peça na bancada (station sem current_piece).
 * Fundo navy escuro com indicação da bancada atual.
 */
import type { FC } from 'react'

interface Props {
  /** Código da bancada: 'bench_a' | 'bench_b' */
  station: string
}

export const TabletIdle: FC<Props> = ({ station }) => (
  <div
    style={{
      width: '100%',
      height: '100%',
      background: '#1B2A4A', // allow: tablet kiosk navy palette
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#8BA7CC', // allow: tablet kiosk navy palette
    }}
  >
    {/* Ícone de espera */}
    <div style={{ fontSize: 80, marginBottom: 24 }}>⏳</div>

    <div style={{ fontSize: 32, fontWeight: 700, color: '#C5D8F0', marginBottom: 12 }}>{/* allow: tablet kiosk navy palette */}
      Aguardando Peça
    </div>

    <div style={{ fontSize: 18, opacity: 0.7 }}>
      {station === 'bench_a' ? 'Bancada A — V1 e V2' : 'Bancada B — V3'}
    </div>

    {/* Rodapé de branding */}
    <div style={{ marginTop: 48, fontSize: 14, opacity: 0.4, letterSpacing: 2 }}>
      RECOGNITION · QUALITY GATE
    </div>
  </div>
)
