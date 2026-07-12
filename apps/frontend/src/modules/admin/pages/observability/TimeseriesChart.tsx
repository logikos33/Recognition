/**
 * TimeseriesChart — gráfico de linha de uma métrica de platform_metrics (WS11).
 *
 * Busca GET /admin/observability/timeseries com o próprio usePolling
 * (respeita o seletor global de intervalo; refreshMs=0 ⇒ nenhum request).
 * O pai deve remontar com key={window} para reiniciar o polling ao trocar
 * a janela histórica.
 */
import { useCallback, useState } from 'react'
import { HelpCircle } from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { usePolling } from '../../../../hooks/usePolling'
import { chartColors } from '../../../../theme/chartColors'
import { vars } from '../../../../styles/theme.css'
import { Tooltip } from '../../../../components/ui/Tooltip/Tooltip'
import { EmptyState } from '../../../../components/ui/EmptyState/EmptyState'
import { Skeleton } from '../../../../components/ui/Skeleton/Skeleton'
import { adminService } from '../../services/adminService'
import * as s from '../../components/admin.css'
import type { ObsTimeseriesPoint, ObsWindow } from '../../types/admin'

function fmtBucket(bucket: string, window: ObsWindow): string {
  const d = new Date(bucket)
  if (window === '7d') {
    return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}h`
  }
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

interface TimeseriesChartProps {
  title: string
  /** Explicação pt-BR para leigo (Tooltip do kit no título). */
  tooltip: string
  scope: string
  metric: string
  window: ObsWindow
  refreshMs: number
  queue?: string
  color?: string
  unit?: string
  height?: number
}

export function TimeseriesChart({
  title, tooltip, scope, metric, window: windowSel, refreshMs,
  queue, color = chartColors.primary, unit = '', height = 200,
}: TimeseriesChartProps) {
  const [points, setPoints] = useState<ObsTimeseriesPoint[]>([])
  const [loaded, setLoaded] = useState(false)

  const load = useCallback(async () => {
    const res = await adminService.getObservabilityTimeseries({
      scope, metric, window: windowSel, queue,
    })
    setPoints(res.points)
    setLoaded(true)
  }, [scope, metric, windowSel, queue])

  usePolling(load, refreshMs > 0 ? refreshMs : 60_000, { enabled: refreshMs > 0 })

  const data = points
    .filter((p) => p.avg != null)
    .map((p) => ({ time: fmtBucket(p.bucket, windowSel), value: p.avg as number }))

  return (
    <div className={s.card}>
      <div className={s.flex} style={{ marginBottom: 12 }}>
        <span className={s.cardTitle} style={{ marginBottom: 0 }}>{title}</span>
        <Tooltip label={tooltip}>
          <HelpCircle size={13} aria-label={`Ajuda: ${title}`} style={{ color: vars.color.textMuted }} />
        </Tooltip>
      </div>

      {!loaded && refreshMs > 0 && (
        <Skeleton variant="rect" height={height} />
      )}

      {!loaded && refreshMs <= 0 && (
        <EmptyState
          title="Atualização pausada"
          description="Selecione um intervalo de atualização para carregar o gráfico"
        />
      )}

      {loaded && data.length === 0 && (
        <EmptyState
          title="Sem pontos na janela"
          description="Aguarde o coletor (ciclo de 60s) ou clique em 'Coletar agora'"
        />
      )}

      {loaded && data.length > 0 && (
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 10, fill: chartColors.axis }}
              interval="preserveStartEnd"
            />
            <YAxis tick={{ fontSize: 10, fill: chartColors.axis }} domain={['auto', 'auto']} />
            <ChartTooltip
              contentStyle={{
                background: vars.color.bgElevated,
                border: `1px solid ${vars.color.borderDefault}`,
                borderRadius: '8px',
                fontSize: '12px',
              }}
              formatter={(v) => [
                typeof v === 'number' ? `${v.toFixed(1)}${unit}` : '—',
                title,
              ]}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
