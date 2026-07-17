/**
 * DashboardIntegradoPage — Dashboard Integrado (task-112, ADR-0053).
 *
 * Duas seções, ambas DENTRO da plataforma (consome só dashboardEdgeService →
 * api.ts, envelope {status,data}; zero raw fetch novo; tenant-scoped no backend):
 *
 *   a) Observabilidade de MODELOS (Training Studio analytics): curvas por época
 *      por modelo — mAP@0.5:0.95 e mAP_small em destaque (juiz da Qualidade),
 *      loss e LR — com comparação lado a lado (multi-seleção de modelos).
 *   b) Telemetria do EDGE ao vivo: gauges (GPU/temp/VDD_IN/RAM) + sparklines +
 *      FPS por módulo; SocketIO namespace /monitor, evento "edge_telemetry".
 *
 * Rota: /epi/edge-observability.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, Boxes, Cpu, MemoryStick, Thermometer, Zap } from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { PageHeader } from '../components/ui/PageHeader/PageHeader'
import { EmptyState } from '../components/ui/EmptyState/EmptyState'
import { Skeleton } from '../components/ui/Skeleton/Skeleton'
import { vars } from '../styles/theme.css'
import { chartColors, chartSeries } from '../theme/chartColors'
import { getToken } from '../services/api'
import {
  dashboardEdgeService,
  type EpochMetrics,
  type ModelSummary,
  type TelemetrySample,
  type TelemetrySeries,
  type TelemetryWindow,
  type TrainingCurves,
} from '../services/dashboardEdgeService'
import { useEdgeTelemetrySocket } from '../hooks/useEdgeTelemetrySocket'
import * as s from './DashboardIntegradoPage.css'

const WS_URL = import.meta.env.VITE_WS_URL || import.meta.env.VITE_API_URL || ''

const WINDOWS: TelemetryWindow[] = ['15m', '1h', '6h', '24h']

// --------------------------------------------------------------------------- //
// Helpers                                                                     //
// --------------------------------------------------------------------------- //

function colorForIndex(i: number): string {
  return chartSeries[i % chartSeries.length]
}

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

// --------------------------------------------------------------------------- //
// MODELOS — gráfico de uma métrica comparando modelos                         //
// --------------------------------------------------------------------------- //

interface MetricChartProps {
  title: string
  highlight?: boolean
  unit?: string
  curves: TrainingCurves
  selected: string[]
  colorMap: Record<string, string>
  accessor: (m: EpochMetrics) => number | null | undefined
}

function MetricChart({
  title, highlight, unit = '', curves, selected, colorMap, accessor,
}: MetricChartProps) {
  // União das épocas dos modelos selecionados → linha por modelo.
  const data = useMemo(() => {
    const byEpoch = new Map<number, Record<string, number | string>>()
    for (const model of selected) {
      for (const p of curves[model] ?? []) {
        const value = accessor(p.metrics)
        if (value == null || !Number.isFinite(value)) continue
        const row = byEpoch.get(p.epoch) ?? { epoch: p.epoch }
        row[model] = value
        byEpoch.set(p.epoch, row)
      }
    }
    return [...byEpoch.values()].sort(
      (a, b) => (a.epoch as number) - (b.epoch as number),
    )
  }, [curves, selected, accessor])

  return (
    <div className={`${s.card}${highlight ? ` ${s.cardHighlight}` : ''}`}>
      <div className={s.cardTitle}>
        <span>{title}</span>
        {highlight && <span className={s.cardBadge}>métrica-chave</span>}
      </div>
      {data.length === 0 ? (
        <EmptyState title="Sem dados" description="Nenhuma época com esta métrica nos modelos selecionados." />
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
            <XAxis
              dataKey="epoch"
              tick={{ fontSize: 10, fill: chartColors.axis }}
              label={{ value: 'época', position: 'insideBottomRight', offset: -2, fontSize: 10, fill: chartColors.axis }}
            />
            <YAxis tick={{ fontSize: 10, fill: chartColors.axis }} domain={['auto', 'auto']} />
            <ChartTooltip
              contentStyle={{
                background: vars.color.bgElevated,
                border: `1px solid ${vars.color.borderDefault}`,
                borderRadius: '8px',
                fontSize: '12px',
              }}
              formatter={(v) => [typeof v === 'number' ? `${v.toFixed(3)}${unit}` : '—']}
            />
            {selected.map((model) => (
              <Line
                key={model}
                type="monotone"
                dataKey={model}
                name={model}
                stroke={colorMap[model]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------- //
// EDGE — gauge + sparkline                                                     //
// --------------------------------------------------------------------------- //

interface GaugeProps {
  label: string
  icon: React.ReactNode
  value: number | null
  unit: string
  max: number
  spark: number[]
}

function Gauge({ label, icon, value, unit, max, spark }: GaugeProps) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, (value / max) * 100))
  const sparkData = spark.map((v, i) => ({ i, v }))
  return (
    <div className={s.gauge}>
      <div className={s.gaugeLabel} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {icon}
        {label}
      </div>
      <div className={s.gaugeValue}>
        {value == null ? '—' : value.toFixed(unit === '%' ? 0 : 1)}
        <span className={s.gaugeUnit}>{unit}</span>
      </div>
      <div className={s.gaugeBar}>
        <div className={s.gaugeFill} style={{ width: `${pct}%` }} />
      </div>
      {sparkData.length > 1 && (
        <ResponsiveContainer width="100%" height={32}>
          <LineChart data={sparkData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
            <Line type="monotone" dataKey="v" stroke={chartColors.accent} strokeWidth={1.5} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Page                                                                        //
// --------------------------------------------------------------------------- //

export function DashboardIntegradoPage() {
  const token = getToken()

  // -- Modelos --
  const [models, setModels] = useState<ModelSummary[]>([])
  const [modelsLoading, setModelsLoading] = useState(true)
  const [modelsError, setModelsError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [curves, setCurves] = useState<TrainingCurves>({})
  const [curvesLoading, setCurvesLoading] = useState(false)

  // -- Telemetria histórica --
  const [telWindow, setTelWindow] = useState<TelemetryWindow>('1h')
  const [history, setHistory] = useState<TelemetrySeries | null>(null)
  const [telLoading, setTelLoading] = useState(true)
  const [telError, setTelError] = useState<string | null>(null)

  // -- Telemetria ao vivo --
  const { connected, samples: liveSamples, latest: liveLatest } = useEdgeTelemetrySocket({
    wsUrl: WS_URL,
    token: token ?? '',
    enabled: !!token,
  })

  const colorMap = useMemo(() => {
    const map: Record<string, string> = {}
    models.forEach((m, i) => { map[m.model_name] = colorForIndex(i) })
    return map
  }, [models])

  // Carrega modelos + auto-seleção dos 2 primeiros
  useEffect(() => {
    let alive = true
    setModelsLoading(true)
    setModelsError(null)
    dashboardEdgeService.getModels()
      .then((list) => {
        if (!alive) return
        setModels(list)
        setSelected(list.slice(0, 2).map((m) => m.model_name))
      })
      .catch((err) => alive && setModelsError(err instanceof Error ? err.message : 'Erro ao carregar modelos'))
      .finally(() => alive && setModelsLoading(false))
    return () => { alive = false }
  }, [])

  // Carrega curvas dos modelos selecionados
  useEffect(() => {
    if (selected.length === 0) { setCurves({}); return }
    let alive = true
    setCurvesLoading(true)
    dashboardEdgeService.getTrainingCurves(selected)
      .then((c) => alive && setCurves(c))
      .catch(() => alive && setCurves({}))
      .finally(() => alive && setCurvesLoading(false))
    return () => { alive = false }
  }, [selected])

  // Carrega telemetria histórica na janela escolhida
  const loadTelemetry = useCallback(() => {
    let alive = true
    setTelLoading(true)
    setTelError(null)
    dashboardEdgeService.getEdgeTelemetry(telWindow)
      .then((series) => alive && setHistory(series))
      .catch((err) => alive && setTelError(err instanceof Error ? err.message : 'Erro ao carregar telemetria'))
      .finally(() => alive && setTelLoading(false))
    return () => { alive = false }
  }, [telWindow])

  useEffect(() => loadTelemetry(), [loadTelemetry])

  const toggleModel = (name: string) => {
    setSelected((prev) =>
      prev.includes(name) ? prev.filter((m) => m !== name) : [...prev, name],
    )
  }

  // Amostra corrente = última ao vivo, senão última do histórico
  const current: TelemetrySample | null = useMemo(() => {
    if (liveLatest) {
      return {
        site_id: liveLatest.site_id,
        label: liveLatest.label,
        sampled_at: liveLatest.sampled_at,
        payload: liveLatest.payload,
      }
    }
    const hist = history?.samples
    return hist && hist.length > 0 ? hist[hist.length - 1] : null
  }, [liveLatest, history])

  // Série p/ sparklines: ao vivo se houver, senão histórico
  const gpuSpark = useMemo(() => {
    const live = liveSamples.map((x) => num(x.payload.gpu_load_pct)).filter((v): v is number => v != null)
    if (live.length > 1) return live.slice(-60)
    return (history?.samples ?? []).map((x) => num(x.payload.gpu_load_pct)).filter((v): v is number => v != null).slice(-60)
  }, [liveSamples, history])

  const p = current?.payload
  const gpu = num(p?.gpu_load_pct)
  const tempGpu = num(p?.temps_c?.gpu)
  const vddInW = p?.power_mw?.VDD_IN != null ? p.power_mw.VDD_IN / 1000 : null
  const ramGb = p?.ram_used_mb != null ? p.ram_used_mb / 1024 : null
  const fpsPerModule = p?.fps_per_module ?? {}
  const fpsEntries = Object.entries(fpsPerModule)

  return (
    <div className={s.page}>
      <PageHeader
        title="Observabilidade de Modelos & Edge"
        subtitle="Curvas de treino por modelo (Training Studio) + telemetria do Jetson ao vivo — dentro da plataforma (task-112, ADR-0053)"
      />

      {/* ---------------- Seção A: Modelos ---------------- */}
      <div className={s.section}>
        <div className={s.sectionHead}>
          <h2 className={s.sectionTitle}><Boxes size={18} /> Observabilidade de Modelos</h2>
        </div>

        {modelsLoading ? (
          <div className={s.chartGrid}>
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} variant="rect" height={200} />)}
          </div>
        ) : modelsError ? (
          <EmptyState icon={<Boxes size={28} />} title="Erro ao carregar modelos" description={modelsError} />
        ) : models.length === 0 ? (
          <EmptyState
            icon={<Boxes size={28} />}
            title="Nenhum modelo com métricas"
            description="Ingira curvas de treino via POST /api/v1/dashboard/training-metrics (ver scripts/seed_dashboard_observability.py)."
          />
        ) : (
          <>
            <div className={s.chips}>
              {models.map((m) => {
                const active = selected.includes(m.model_name)
                return (
                  <button
                    key={m.model_name}
                    type="button"
                    className={`${s.chip}${active ? ` ${s.chipActive}` : ''}`}
                    onClick={() => toggleModel(m.model_name)}
                    aria-pressed={active}
                  >
                    <span className={s.chipSwatch} style={{ background: colorMap[m.model_name] }} />
                    {m.model_name}
                    {m.ap_small != null && <span style={{ color: vars.color.textMuted }}>· small {m.ap_small.toFixed(3)}</span>}
                  </button>
                )
              })}
            </div>

            {selected.length === 0 ? (
              <EmptyState title="Selecione um modelo" description="Clique num modelo acima para ver suas curvas." />
            ) : curvesLoading ? (
              <div className={s.chartGrid}>
                {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} variant="rect" height={200} />)}
              </div>
            ) : (
              <div className={s.chartGrid}>
                <MetricChart title="mAP@0.5:0.95" highlight curves={curves} selected={selected} colorMap={colorMap} accessor={(m) => m.ap5095} />
                <MetricChart title="mAP_small (juiz da Qualidade)" highlight curves={curves} selected={selected} colorMap={colorMap} accessor={(m) => m.ap_small} />
                <MetricChart title="Loss total" curves={curves} selected={selected} colorMap={colorMap} accessor={(m) => m.losses?.total} />
                <MetricChart title="Learning rate" curves={curves} selected={selected} colorMap={colorMap} accessor={(m) => m.lr} />
              </div>
            )}
          </>
        )}
      </div>

      {/* ---------------- Seção B: Telemetria Edge ---------------- */}
      <div className={s.section}>
        <div className={s.sectionHead}>
          <h2 className={s.sectionTitle}><Activity size={18} /> Telemetria do Edge</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: vars.space.md }}>
            <span className={s.connBadge}>
              <span className={`${s.dot} ${connected ? s.dotOn : s.dotOff}`} />
              {connected ? 'ao vivo' : 'offline'}
            </span>
            <select
              className={s.select}
              value={telWindow}
              onChange={(e) => setTelWindow(e.target.value as TelemetryWindow)}
              aria-label="Janela histórica de telemetria"
            >
              {WINDOWS.map((w) => <option key={w} value={w}>{w}</option>)}
            </select>
          </div>
        </div>

        {telLoading && !current ? (
          <div className={s.gaugeGrid}>
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} variant="rect" height={120} />)}
          </div>
        ) : telError && !current ? (
          <EmptyState icon={<Activity size={28} />} title="Erro ao carregar telemetria" description={telError} />
        ) : !current ? (
          <EmptyState
            icon={<Activity size={28} />}
            title="Sem amostras de telemetria"
            description="Aguardando o edge publicar (ao vivo) ou ingira histórico via POST /api/v1/dashboard/edge-telemetry."
          />
        ) : (
          <>
            <div className={s.gaugeGrid}>
              <Gauge label="GPU" icon={<Cpu size={14} />} value={gpu} unit="%" max={100} spark={gpuSpark} />
              <Gauge label="Temp GPU" icon={<Thermometer size={14} />} value={tempGpu} unit="°C" max={100} spark={[]} />
              <Gauge label="VDD_IN" icon={<Zap size={14} />} value={vddInW} unit="W" max={40} spark={[]} />
              <Gauge label="RAM" icon={<MemoryStick size={14} />} value={ramGb} unit="GB" max={16} spark={[]} />
            </div>

            <div className={s.card}>
              <div className={s.cardTitle}><span>FPS por módulo</span></div>
              {fpsEntries.length === 0 ? (
                <EmptyState title="Sem FPS por módulo" description="O payload da amostra atual não traz fps_per_module." />
              ) : (
                <div>
                  {fpsEntries.map(([mod, fps]) => (
                    <div key={mod} className={s.fpsRow}>
                      <span className={s.fpsName}>{mod}</span>
                      <span className={s.fpsVal}>{typeof fps === 'number' ? fps.toFixed(1) : String(fps)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
