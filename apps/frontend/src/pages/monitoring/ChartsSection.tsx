/**
 * ChartsSection — séries da janela consultada (CPU/RAM/GPU, temperatura
 * máxima e rede) alimentadas pelos samples já carregados — NENHUM polling
 * próprio por gráfico (estilo do TimeseriesChart do admin, dados locais).
 */
import { useMemo } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Card, CardBody, CardHeader, CardTitle } from '../../components/ui/Card/Card'
import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import { chartColors, chartSeries } from '../../theme/chartColors'
import { vars } from '../../styles/theme.css'
import type { MonitoringSample, MonitoringWindow } from '../../types/monitoring'
import { fmtEpoch, maxTemp, pctOf } from './health'
import * as s from './monitoring.css'

interface SeriesDef {
  key: string
  label: string
  color: string
}

interface MetricChartProps {
  title: string
  data: Record<string, number | string | null>[]
  series: SeriesDef[]
  unit?: string
  height?: number
}

function MetricChart({ title, data, series, unit = '', height = 200 }: MetricChartProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardBody>
        {data.length === 0 ? (
          <EmptyState
            title="Sem pontos na janela"
            description="Aguarde a resposta do box ou troque a janela"
          />
        ) : (
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
                formatter={(v: unknown, name: unknown) => [
                  typeof v === 'number' ? `${v.toFixed(1)}${unit}` : '—',
                  String(name),
                ]}
              />
              {series.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
              {series.map((serie) => (
                <Line
                  key={serie.key}
                  type="monotone"
                  dataKey={serie.key}
                  name={serie.label}
                  stroke={serie.color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardBody>
    </Card>
  )
}

interface ChartsSectionProps {
  samples: MonitoringSample[]
  windowSel: MonitoringWindow
}

export function ChartsSection({ samples, windowSel }: ChartsSectionProps) {
  const { utilData, tempData, netData } = useMemo(() => {
    const util: Record<string, number | string | null>[] = []
    const temp: Record<string, number | string | null>[] = []
    const net: Record<string, number | string | null>[] = []
    for (const sample of samples) {
      const time = fmtEpoch(sample.ts, windowSel)
      util.push({
        time,
        cpu: sample.hw?.cpu_pct ?? null,
        ram: pctOf(sample.hw?.ram_used_mb, sample.hw?.ram_total_mb),
        gpu: sample.hw?.gpu_pct ?? null,
      })
      temp.push({ time, temp: maxTemp(sample.hw?.temps_c) })
      net.push({
        time,
        tx: sample.net?.tx_kbps ?? null,
        rx: sample.net?.rx_kbps ?? null,
      })
    }
    const hasAny = (rows: Record<string, number | string | null>[], keys: string[]) =>
      rows.some((r) => keys.some((k) => r[k] != null))
    return {
      utilData: hasAny(util, ['cpu', 'ram', 'gpu']) ? util : [],
      tempData: hasAny(temp, ['temp']) ? temp : [],
      netData: hasAny(net, ['tx', 'rx']) ? net : [],
    }
  }, [samples, windowSel])

  return (
    <div className={s.chartsGrid}>
      <MetricChart
        title="Utilização (%)"
        data={utilData}
        unit="%"
        series={[
          { key: 'cpu', label: 'CPU', color: chartSeries[0] },
          { key: 'ram', label: 'RAM', color: chartSeries[1] },
          { key: 'gpu', label: 'GPU', color: chartSeries[2] },
        ]}
      />
      <MetricChart
        title="Temperatura máxima (°C)"
        data={tempData}
        unit="°C"
        series={[{ key: 'temp', label: 'Temp. máx', color: chartColors.danger }]}
      />
      <MetricChart
        title="Rede (kbps)"
        data={netData}
        unit=" kbps"
        series={[
          { key: 'tx', label: 'Upload (tx)', color: chartSeries[0] },
          { key: 'rx', label: 'Download (rx)', color: chartSeries[3] },
        ]}
      />
    </div>
  )
}
