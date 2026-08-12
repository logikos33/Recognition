/**
 * ChartsSection — séries da janela consultada (CPU/RAM/GPU, temperatura
 * máxima e rede) alimentadas pelos samples já carregados — NENHUM polling
 * próprio por gráfico (estilo do TimeseriesChart do admin, dados locais).
 *
 * Interatividade (recharts ^3.8): os três gráficos compartilham um `syncId`,
 * então o crosshair/tooltip aparece no MESMO instante em todos (permite
 * cruzar throttle térmico × queda de FPS no mesmo tick). O eixo X é numérico
 * (epoch em ms) com `domain` controlado por estado:
 *   • arraste horizontal no plot → zoom na faixa selecionada (ReferenceArea);
 *   • Shift+arraste ou "Modo mover" → pan (desloca a janela no tempo);
 *   • Ctrl/Alt+scroll → zoom centrado no cursor;
 *   • "Resetar zoom" → volta ao domínio cheio dos samples.
 * Quando o usuário navega ALÉM dos samples carregados, dispara (debounced)
 * `onRequestRange(start, end)` — nunca no mount/poll, só em interação real —
 * preservando o "só puxa dado quando ele mexe" (zero-egress-safe).
 */
import { type MouseEvent as ReactMouseEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
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

/** Todos os gráficos com o mesmo syncId → tooltip/crosshair no mesmo tick. */
const SYNC_ID = 'edge-monitoring-charts'
/** Debounce da requisição de faixa fora dos samples carregados. */
const RANGE_REQUEST_DEBOUNCE_MS = 400

type ChartRow = Record<string, number | null>
type NumDomain = [number, number]
/** Estado mínimo do evento de mouse do recharts que consumimos. */
type ChartMouseState = { activeLabel?: string | number }
type ChartMouseHandler = (state: ChartMouseState, event: ReactMouseEvent<SVGElement>) => void

interface SeriesDef {
  key: string
  label: string
  color: string
}

interface MetricChartProps {
  title: string
  data: ChartRow[]
  series: SeriesDef[]
  unit?: string
  height?: number
  windowSel: MonitoringWindow
  xDomain: [number | string, number | string]
  refArea: { left: number | null; right: number | null } | null
  onDown: ChartMouseHandler
  onMove: ChartMouseHandler
  onUp: () => void
}

function MetricChart({
  title,
  data,
  series,
  unit = '',
  height = 200,
  windowSel,
  xDomain,
  refArea,
  onDown,
  onMove,
  onUp,
}: MetricChartProps) {
  const dragging = refArea != null && refArea.left != null && refArea.right != null
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
            <LineChart
              data={data}
              margin={{ top: 4, right: 8, left: -16, bottom: 0 }}
              syncId={SYNC_ID}
              syncMethod="value"
              accessibilityLayer
              onMouseDown={onDown}
              onMouseMove={onMove}
              onMouseUp={onUp}
              style={{ cursor: dragging ? 'ew-resize' : 'crosshair', userSelect: 'none' }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
              <XAxis
                dataKey="ts"
                type="number"
                scale="time"
                domain={xDomain}
                allowDataOverflow
                tick={{ fontSize: 10, fill: chartColors.axis }}
                tickFormatter={(v: number) => fmtEpoch(Number(v) / 1000, windowSel)}
                interval="preserveStartEnd"
                minTickGap={40}
              />
              <YAxis tick={{ fontSize: 10, fill: chartColors.axis }} domain={['auto', 'auto']} />
              <ChartTooltip
                cursor={{ stroke: chartColors.axis, strokeDasharray: '3 3' }}
                contentStyle={{
                  background: vars.color.bgElevated,
                  border: `1px solid ${vars.color.borderDefault}`,
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                labelFormatter={(label: unknown) =>
                  typeof label === 'number' ? fmtEpoch(label / 1000, windowSel) : '—'
                }
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
                  isAnimationActive={false}
                />
              ))}
              {dragging && (
                <ReferenceArea
                  x1={Math.min(refArea!.left!, refArea!.right!)}
                  x2={Math.max(refArea!.left!, refArea!.right!)}
                  strokeOpacity={0.3}
                  fill={chartColors.primary}
                  fillOpacity={0.12}
                />
              )}
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
  /**
   * Chamado (debounced ~400ms) quando o usuário navega para uma faixa que
   * extrapola os samples já carregados — antes do ts mais antigo ou depois do
   * mais novo. NÃO dispara no mount/poll: só em interação real. `start`/`end`
   * são epoch em SEGUNDOS. O fetch em si é do chamador (zero-egress-safe).
   */
  onRequestRange?: (startEpochSec: number, endEpochSec: number) => void
}

export function ChartsSection({ samples, windowSel, onRequestRange }: ChartsSectionProps) {
  const { utilData, tempData, netData, minTs, maxTs } = useMemo(() => {
    const util: ChartRow[] = []
    const temp: ChartRow[] = []
    const net: ChartRow[] = []
    let lo = Number.POSITIVE_INFINITY
    let hi = Number.NEGATIVE_INFINITY
    for (const sample of samples) {
      const ts = sample.ts * 1000
      if (ts < lo) lo = ts
      if (ts > hi) hi = ts
      util.push({
        ts,
        cpu: sample.hw?.cpu_pct ?? null,
        ram: pctOf(sample.hw?.ram_used_mb, sample.hw?.ram_total_mb),
        gpu: sample.hw?.gpu_pct ?? null,
      })
      temp.push({ ts, temp: maxTemp(sample.hw?.temps_c) })
      net.push({
        ts,
        tx: sample.net?.tx_kbps ?? null,
        rx: sample.net?.rx_kbps ?? null,
      })
    }
    const hasAny = (rows: ChartRow[], keys: string[]) =>
      rows.some((r) => keys.some((k) => r[k] != null))
    return {
      utilData: hasAny(util, ['cpu', 'ram', 'gpu']) ? util : [],
      tempData: hasAny(temp, ['temp']) ? temp : [],
      netData: hasAny(net, ['tx', 'rx']) ? net : [],
      minTs: Number.isFinite(lo) ? lo : 0,
      maxTs: Number.isFinite(hi) ? hi : 0,
    }
  }, [samples])

  const hasData = utilData.length > 0 || tempData.length > 0 || netData.length > 0

  // ── Estado de interação ────────────────────────────────────────────────────
  const [domain, setDomain] = useState<NumDomain | null>(null)
  const [refArea, setRefArea] = useState<{ left: number | null; right: number | null } | null>(null)
  const [panMode, setPanMode] = useState(false)

  // Refs espelham o estado atual para os handlers estáveis (useCallback []).
  const ctxRef = useRef({ minTs, maxTs, domain, onRequestRange })
  ctxRef.current = { minTs, maxTs, domain, onRequestRange }
  const panModeRef = useRef(panMode)
  panModeRef.current = panMode

  const rootRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ active: boolean; left: number | null; right: number | null }>({
    active: false,
    left: null,
    right: null,
  })
  const panRef = useRef<{ x: number; w: number; d0: number; d1: number } | null>(null)
  const lastLabelRef = useRef<number | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastReqKeyRef = useRef<string | null>(null)

  const getEff = useCallback((): NumDomain => {
    const c = ctxRef.current
    return c.domain ?? [c.minTs, c.maxTs]
  }, [])

  /** Agenda (debounced) o pedido de faixa quando ela extrapola o carregado. */
  const scheduleRangeRequest = useCallback((next: NumDomain) => {
    const { minTs: lo0, maxTs: hi0, onRequestRange: cb } = ctxRef.current
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
    if (!cb) return
    const lo = Math.min(next[0], next[1])
    const hi = Math.max(next[0], next[1])
    // Dentro do já carregado → nada a buscar (e cancela pendências).
    if (lo >= lo0 && hi <= hi0) return
    const startSec = Math.floor(lo / 1000)
    const endSec = Math.ceil(hi / 1000)
    const key = `${startSec}:${endSec}`
    if (key === lastReqKeyRef.current) return
    debounceRef.current = setTimeout(() => {
      debounceRef.current = null
      lastReqKeyRef.current = key
      cb(startSec, endSec)
    }, RANGE_REQUEST_DEBOUNCE_MS)
  }, [])

  const handleDown = useCallback<ChartMouseHandler>((state, event) => {
    const panning = panModeRef.current || event.shiftKey
    if (panning) {
      const eff = getEff()
      const target = event.currentTarget
      const w =
        target && typeof target.getBoundingClientRect === 'function'
          ? target.getBoundingClientRect().width
          : 0
      panRef.current = { x: event.clientX, w, d0: eff[0], d1: eff[1] }
      return
    }
    if (state.activeLabel == null) return
    const x = Number(state.activeLabel)
    dragRef.current = { active: true, left: x, right: x }
    setRefArea({ left: x, right: x })
  }, [getEff])

  const handleMove = useCallback<ChartMouseHandler>((state, event) => {
    if (state.activeLabel != null) lastLabelRef.current = Number(state.activeLabel)
    const pan = panRef.current
    if (pan) {
      const span = pan.d1 - pan.d0
      if (span <= 0 || pan.w <= 0) return
      const dt = ((event.clientX - pan.x) / pan.w) * span
      const next: NumDomain = [pan.d0 - dt, pan.d1 - dt]
      setDomain(next)
      scheduleRangeRequest(next)
      return
    }
    const d = dragRef.current
    if (d.active && state.activeLabel != null) {
      const x = Number(state.activeLabel)
      d.right = x
      setRefArea({ left: d.left, right: x })
    }
  }, [scheduleRangeRequest])

  const finishInteraction = useCallback(() => {
    if (panRef.current) {
      panRef.current = null
      return
    }
    const d = dragRef.current
    if (!d.active) return
    dragRef.current = { active: false, left: null, right: null }
    setRefArea(null)
    let { left, right } = d
    if (left == null || right == null || left === right) return
    if (left > right) {
      const t = left
      left = right
      right = t
    }
    const next: NumDomain = [left, right]
    setDomain(next)
    scheduleRangeRequest(next)
  }, [scheduleRangeRequest])

  const resetView = useCallback(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
    panRef.current = null
    dragRef.current = { active: false, left: null, right: null }
    lastReqKeyRef.current = null
    setDomain(null)
    setRefArea(null)
  }, [])

  // Solturas fora do plot (ex.: soltou o mouse sobre outro elemento).
  useEffect(() => {
    const up = () => finishInteraction()
    window.addEventListener('mouseup', up)
    return () => window.removeEventListener('mouseup', up)
  }, [finishInteraction])

  // Ctrl/Alt+scroll → zoom centrado no cursor (listener nativo não-passivo).
  useEffect(() => {
    const el = rootRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.altKey) return
      e.preventDefault()
      const eff = getEff()
      const span = eff[1] - eff[0]
      if (span <= 0) return
      const center = lastLabelRef.current ?? (eff[0] + eff[1]) / 2
      const factor = e.deltaY > 0 ? 1.25 : 0.8
      const next: NumDomain = [center - (center - eff[0]) * factor, center + (eff[1] - center) * factor]
      setDomain(next)
      scheduleRangeRequest(next)
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [getEff, scheduleRangeRequest])

  // Troca de janela zera o zoom (domínio em ms da janela antiga não faz sentido).
  useEffect(() => {
    resetView()
  }, [windowSel, resetView])

  // Limpa debounce pendente ao desmontar.
  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
  }, [])

  const isZoomed = domain != null
  const xDomain: [number | string, number | string] = domain ?? ['dataMin', 'dataMax']

  const toolbarBtn = (active: boolean, disabled: boolean): React.CSSProperties => ({
    fontSize: 12,
    fontWeight: 600,
    padding: '4px 10px',
    borderRadius: vars.radius.md,
    border: `1px solid ${active ? vars.color.primary : vars.color.borderStrong}`,
    background: active ? vars.color.primaryAlpha : vars.color.bgSurface,
    color: disabled ? vars.color.textMuted : vars.color.textPrimary,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
  })

  return (
    <div ref={rootRef}>
      {hasData && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexWrap: 'wrap',
            marginBottom: vars.space.sm,
          }}
        >
          <button
            type="button"
            aria-pressed={panMode}
            onClick={() => setPanMode((p) => !p)}
            style={toolbarBtn(panMode, false)}
          >
            {panMode ? 'Modo mover: ativo' : 'Modo mover'}
          </button>
          <button
            type="button"
            onClick={resetView}
            disabled={!isZoomed}
            style={toolbarBtn(false, !isZoomed)}
          >
            Resetar zoom
          </button>
          {isZoomed && (
            <span style={{ fontSize: 12, color: vars.color.textSecondary, fontVariantNumeric: 'tabular-nums' }}>
              {fmtEpoch(Math.min(domain[0], domain[1]) / 1000, windowSel)} –{' '}
              {fmtEpoch(Math.max(domain[0], domain[1]) / 1000, windowSel)}
            </span>
          )}
          <span style={{ fontSize: 11, color: vars.color.textMuted }}>
            Arraste para dar zoom · Shift+arraste (ou "Modo mover") para deslocar · Ctrl/Alt+scroll
            para zoom
          </span>
        </div>
      )}

      <div className={s.chartsGrid}>
        <MetricChart
          title="Utilização (%)"
          data={utilData}
          unit="%"
          windowSel={windowSel}
          xDomain={xDomain}
          refArea={refArea}
          onDown={handleDown}
          onMove={handleMove}
          onUp={finishInteraction}
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
          windowSel={windowSel}
          xDomain={xDomain}
          refArea={refArea}
          onDown={handleDown}
          onMove={handleMove}
          onUp={finishInteraction}
          series={[{ key: 'temp', label: 'Temp. máx', color: chartColors.danger }]}
        />
        <MetricChart
          title="Rede (kbps)"
          data={netData}
          unit=" kbps"
          windowSel={windowSel}
          xDomain={xDomain}
          refArea={refArea}
          onDown={handleDown}
          onMove={handleMove}
          onUp={finishInteraction}
          series={[
            { key: 'tx', label: 'Upload (tx)', color: chartSeries[0] },
            { key: 'rx', label: 'Download (rx)', color: chartSeries[3] },
          ]}
        />
      </div>
    </div>
  )
}
