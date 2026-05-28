/**
 * Gráfico CEP (Controle Estatístico de Processo) de NOK rate.
 * Implementação SVG pura — sem biblioteca de gráficos externa.
 * Exibe UCL, média, LCL e a série temporal de NOK rates horárias.
 */
import type { CepBaseline } from '../types/quality'

interface DataPoint {
  hour: string
  nok_rate: number
}

interface CepChartProps {
  baseline: CepBaseline | null
  data: DataPoint[]
  height?: number
}

export function CepChart({ baseline, data, height = 180 }: CepChartProps) {
  if (!data || !baseline && data.length === 0) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: '#888', fontSize: '13px' }}>
        Dados CEP insuficientes. São necessários ao menos 5 dias de operação.
      </div>
    )
  }

  const width = 600
  const padL = 40
  const padR = 12
  const padT = 16
  const padB = 28
  const chartW = width - padL - padR
  const chartH = height - padT - padB

  const ucl = baseline?.control_limit_upper ?? 0.2
  const lcl = baseline?.control_limit_lower ?? 0
  const mean = baseline?.mean_nok_rate ?? 0

  // Calcular domínio Y: max entre UCL e dados reais
  const maxY = Math.max(ucl * 1.2, ...data.map(d => d.nok_rate), 0.01)
  const minY = 0

  const toX = (i: number) => padL + (i / Math.max(data.length - 1, 1)) * chartW
  const toY = (v: number) => padT + chartH - ((v - minY) / (maxY - minY)) * chartH

  const points = data.map((d, i) => `${toX(i).toFixed(1)},${toY(d.nok_rate).toFixed(1)}`).join(' ')

  // Linha de rótulos no eixo X (a cada ~4 pontos)
  const xLabels = data
    .map((d, i) => ({ i, label: d.hour.slice(11, 16) }))
    .filter((_, i) => i % Math.max(1, Math.floor(data.length / 6)) === 0)

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      style={{ width: '100%', height: 'auto', display: 'block' }}
      aria-label="Gráfico CEP de taxa NOK"
    >
      {/* Grid */}
      {[0, 0.25, 0.5, 0.75, 1].map(pct => {
        const y = padT + pct * chartH
        const val = maxY * (1 - pct)
        return (
          <g key={pct}>
            <line x1={padL} y1={y} x2={padL + chartW} y2={y} stroke="#333" strokeWidth={0.5} />
            <text x={padL - 4} y={y + 4} fontSize={9} fill="#666" textAnchor="end">
              {(val * 100).toFixed(0)}%
            </text>
          </g>
        )
      })}

      {/* UCL */}
      <line
        x1={padL} y1={toY(ucl)} x2={padL + chartW} y2={toY(ucl)}
        stroke="#EF5350" strokeWidth={1.5} strokeDasharray="6 3"
      />
      <text x={padL + chartW + 2} y={toY(ucl) + 4} fontSize={9} fill="#EF5350">UCL</text>

      {/* Média */}
      <line
        x1={padL} y1={toY(mean)} x2={padL + chartW} y2={toY(mean)}
        stroke="#4FC3F7" strokeWidth={1} strokeDasharray="4 2"
      />
      <text x={padL + chartW + 2} y={toY(mean) + 4} fontSize={9} fill="#4FC3F7">μ</text>

      {/* LCL (só se > 0) */}
      {lcl > 0 && (
        <>
          <line
            x1={padL} y1={toY(lcl)} x2={padL + chartW} y2={toY(lcl)}
            stroke="#43D186" strokeWidth={1} strokeDasharray="4 2"
          />
          <text x={padL + chartW + 2} y={toY(lcl) + 4} fontSize={9} fill="#43D186">LCL</text>
        </>
      )}

      {/* Série de dados */}
      {data.length > 1 && (
        <polyline
          points={points}
          fill="none"
          stroke="#FFB74D"
          strokeWidth={1.5}
          strokeLinejoin="round"
        />
      )}

      {/* Pontos — vermelho se acima de UCL */}
      {data.map((d, i) => (
        <circle
          key={i}
          cx={toX(i)}
          cy={toY(d.nok_rate)}
          r={3}
          fill={d.nok_rate > ucl ? '#EF5350' : '#FFB74D'}
        />
      ))}

      {/* Labels eixo X */}
      {xLabels.map(({ i, label }) => (
        <text key={i} x={toX(i)} y={padT + chartH + 16} fontSize={9} fill="#666" textAnchor="middle">
          {label}
        </text>
      ))}

      {/* Eixo Y label */}
      <text
        x={12}
        y={padT + chartH / 2}
        fontSize={9}
        fill="#666"
        textAnchor="middle"
        transform={`rotate(-90, 12, ${padT + chartH / 2})`}
      >
        NOK%
      </text>
    </svg>
  )
}
