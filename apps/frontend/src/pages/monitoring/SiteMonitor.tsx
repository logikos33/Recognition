/**
 * SiteMonitor — orquestração de dados de UM site na janela selecionada.
 * O pai remonta este componente com key={siteId}:{window} (padrão da casa,
 * ver TimeseriesChart) — todo efeito/polling reinicia limpo na troca.
 *
 * Fluxos:
 *  - Histórico: POST /query → se pending, GET /commands/<id> a cada 2,5 s
 *    (o agente no box faz poll de comandos a cada 60 s — "acordando o box").
 *  - Ao vivo: POST /snapshot a cada ~10 s via usePolling — que PAUSA com a
 *    aba oculta: zero egress do box sem a página aberta.
 *  - Heartbeat de detecção: GET /detections (cloud-side) a cada 30 s.
 *
 * Honestidade temporal (requisito 9): banner sticky sempre visível com a
 * idade da última amostra do coletor — nunca dado velho com cara de novo.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Radio } from 'lucide-react'
import { Banner } from '../../components/ui/Banner/Banner'
import { Badge } from '../../components/ui/Badge/Badge'
import { Button } from '../../components/ui/Button/Button'
import { Skeleton } from '../../components/ui/Skeleton/Skeleton'
import { Tooltip } from '../../components/ui/Tooltip/Tooltip'
import { usePolling } from '../../hooks/usePolling'
import { monitoringService } from '../../services/monitoringService'
import type {
  DetectionsHealth,
  MonitoringResult,
  MonitoringSample,
  MonitoringSite,
  MonitoringThresholds,
  MonitoringWindow,
} from '../../types/monitoring'
import { evaluateHealth, fmtDurationS, toEpochMs } from './health'
import { Semaphore } from './Semaphore'
import { ChartsSection } from './ChartsSection'
import { HardwarePanel } from './HardwarePanel'
import { ServicesPanel } from './ServicesPanel'
import { PipelinePanel } from './PipelinePanel'
import { CollectionPanel } from './CollectionPanel'
import { NetworkPanel } from './NetworkPanel'
import { VersionPanel } from './VersionPanel'
import { InferencePanel } from './InferencePanel'
import { LogtailModal } from './LogtailModal'
import { PanelBoundary } from './parts'
import * as s from './monitoring.css'

const STALE_AFTER_S = 45
const MAX_LIVE_SAMPLES = 720
/** Teto de pontos na série histórica — downsample no box antes do egress. */
const QUERY_MAX_POINTS = 500
/**
 * Camadas que a SÉRIE temporal realmente consome (gráficos = hw/net; duração
 * de throttle = hw; delta de coleta = collection). svc/pipeline/versions/
 * inference só interessam no ÚLTIMO ponto — vêm do snapshot completo. Filtrar
 * aqui derruba o payload da janela (o pesado é pipeline por-câmera × N amostras)
 * sem esvaziar nenhum painel. Ver monitoringService.QueryOptions.layers.
 */
const SERIES_LAYERS = ['hw', 'net', 'collection']

/** Span de cada janela em segundos — para navegação sob demanda (pan/zoom). */
const WINDOW_SPAN_S: Record<MonitoringWindow, number> = {
  '2h': 2 * 3600,
  '24h': 24 * 3600,
  '7d': 7 * 86400,
  '30d': 30 * 86400,
}
const WINDOW_ORDER: MonitoringWindow[] = ['2h', '24h', '7d', '30d']

interface SiteMonitorProps {
  site: MonitoringSite
  windowSel: MonitoringWindow
  thresholds: MonitoringThresholds
  /** Widen a janela quando o usuário navega para antes do que está carregado. */
  onExpandWindow?: (window: MonitoringWindow) => void
}

export function SiteMonitor({ site, windowSel, thresholds, onExpandWindow }: SiteMonitorProps) {
  const siteId = site.id

  // ── Histórico (janela) ────────────────────────────────────────────────────
  const [history, setHistory] = useState<MonitoringResult | null>(null)
  const [historyReceivedAt, setHistoryReceivedAt] = useState<number | null>(null)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [historyWaking, setHistoryWaking] = useState(false)
  const [historyPolling, setHistoryPolling] = useState(false)
  const [queryLoading, setQueryLoading] = useState(true)
  const historyCmdRef = useRef<string | null>(null)

  const startQuery = useCallback(async () => {
    setQueryLoading(true)
    setHistoryError(null)
    setHistoryWaking(false)
    setHistoryPolling(false)
    historyCmdRef.current = null
    try {
      const res = await monitoringService.querySite(siteId, windowSel, {
        maxPoints: QUERY_MAX_POINTS,
        layers: SERIES_LAYERS,
      })
      if (res.state === 'done' && res.result) {
        setHistory(res.result)
        setHistoryReceivedAt(Date.now())
        setQueryLoading(false)
      } else if (res.state === 'failed') {
        setHistoryError('O box respondeu com falha à consulta da janela.')
        setQueryLoading(false)
      } else if (res.command_id) {
        historyCmdRef.current = res.command_id
        setHistoryWaking(true)
        setHistoryPolling(true)
      } else {
        setHistoryError('Resposta sem comando para acompanhar.')
        setQueryLoading(false)
      }
    } catch (e: unknown) {
      setHistoryError(e instanceof Error ? e.message : 'Falha ao consultar o box.')
      setQueryLoading(false)
    }
  }, [siteId, windowSel])

  useEffect(() => {
    void startQuery()
  }, [startQuery])

  const pollHistoryCmd = useCallback(async () => {
    const id = historyCmdRef.current
    if (!id) return
    const res = await monitoringService.getCommand(id)
    if (res.state === 'done') {
      historyCmdRef.current = null
      setHistoryPolling(false)
      setHistoryWaking(false)
      setQueryLoading(false)
      if (res.result) {
        setHistory(res.result)
        setHistoryReceivedAt(Date.now())
      }
    } else if (res.state === 'failed') {
      historyCmdRef.current = null
      setHistoryPolling(false)
      setHistoryWaking(false)
      setQueryLoading(false)
      setHistoryError('O box respondeu com falha à consulta da janela.')
    }
  }, [])

  usePolling(pollHistoryCmd, 2500, { enabled: historyPolling })

  // ── Ao vivo (snapshot ~10 s; pausa com aba oculta ⇒ zero egress) ─────────
  const [live, setLive] = useState<MonitoringResult | null>(null)
  const [liveReceivedAt, setLiveReceivedAt] = useState<number | null>(null)
  const [liveSamples, setLiveSamples] = useState<MonitoringSample[]>([])
  const [liveCmdPolling, setLiveCmdPolling] = useState(false)
  const liveCmdRef = useRef<string | null>(null)

  const applyLive = useCallback((result: MonitoringResult) => {
    setLive(result)
    setLiveReceivedAt(Date.now())
    const incoming = result.samples ?? []
    if (incoming.length) {
      setLiveSamples((prev) => {
        const next = [...prev, ...incoming]
        return next.length > MAX_LIVE_SAMPLES ? next.slice(-MAX_LIVE_SAMPLES) : next
      })
    }
  }, [])

  const snapshotTick = useCallback(async () => {
    if (liveCmdRef.current) return // comando em voo — não empilhar snapshots
    const res = await monitoringService.snapshot(siteId)
    if (res.state === 'done' && res.result) {
      applyLive(res.result)
    } else if (res.state === 'pending' && res.command_id) {
      liveCmdRef.current = res.command_id
      setLiveCmdPolling(true)
    }
    // failed: silencioso — o banner de frescor denuncia a ausência de dado novo
  }, [siteId, applyLive])

  usePolling(snapshotTick, 10_000)

  const pollLiveCmd = useCallback(async () => {
    const id = liveCmdRef.current
    if (!id) return
    const res = await monitoringService.getCommand(id)
    if (res.state === 'done') {
      liveCmdRef.current = null
      setLiveCmdPolling(false)
      if (res.result) applyLive(res.result)
    } else if (res.state === 'failed') {
      liveCmdRef.current = null
      setLiveCmdPolling(false)
    }
  }, [applyLive])

  usePolling(pollLiveCmd, 2500, { enabled: liveCmdPolling })

  // ── Heartbeat de detecção (cloud-side) ────────────────────────────────────
  const [detections, setDetections] = useState<DetectionsHealth | null>(null)
  const [detectionsError, setDetectionsError] = useState<string | null>(null)

  const loadDetections = useCallback(async () => {
    // try/catch explícito: antes o erro era engolido pelo usePolling e o
    // heartbeat ficava mudo (null) sem denunciar a falha — agora vira estado.
    try {
      setDetections(await monitoringService.getDetections(siteId, 60))
      setDetectionsError(null)
    } catch (e: unknown) {
      setDetectionsError(e instanceof Error ? e.message : 'Falha ao consultar detecções.')
    }
  }, [siteId])

  usePolling(loadDetections, 30_000)

  // ── Relógio local p/ idades ("há Xs") ─────────────────────────────────────
  const [nowMs, setNowMs] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 5000)
    return () => clearInterval(id)
  }, [])

  // ── Derivados ─────────────────────────────────────────────────────────────
  const samples = useMemo(() => {
    const hist = history?.samples ?? []
    if (!liveSamples.length) return hist
    const lastTs = hist.length ? hist[hist.length - 1].ts : Number.NEGATIVE_INFINITY
    const extra = liveSamples.filter((sample) => sample.ts > lastTs)
    return extra.length ? [...hist, ...extra] : hist
  }, [history, liveSamples])

  // O snapshot ao vivo é sempre COMPLETO (todas as camadas); a série
  // histórica vem filtrada por SERIES_LAYERS. Preferimos o snapshot para
  // "latest" — assim svc/pipeline/versões/inferência preenchem com dado real.
  const latestFull = live?.samples?.length ? live.samples[live.samples.length - 1] : null
  const latest = latestFull ?? (samples.length ? samples[samples.length - 1] : null)
  const freshest = live ?? history
  const collector = freshest?.collector ?? null

  // Span de histórico carregado (para o banner de frescor dizer "N de histórico")
  const historySpanS = useMemo(() => {
    if (samples.length < 2) return 0
    return Math.max(0, samples[samples.length - 1].ts - samples[0].ts)
  }, [samples])

  const events = useMemo(() => {
    const all = [...(history?.events ?? []), ...(live?.events ?? [])]
    const seen = new Set<string>()
    return all.filter((ev) => {
      const key = `${ev.ts}:${ev.kind}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }, [history, live])

  // Idade da última amostra do coletor: skew-free (device_ts − last_sample_ts,
  // ambos relógio do box) + tempo decorrido desde que a resposta chegou aqui.
  const sampleAgeS = useMemo(() => {
    if (!freshest) return null
    const receivedAt = live ? liveReceivedAt : historyReceivedAt
    // device_ts/last_sample_ts vêm do box como epoch em SEGUNDOS (int) —
    // toEpochMs aceita epoch ou ISO (Date.parse puro dava NaN e o banner
    // ficava "sem amostra ainda" mesmo com dado fresco; visto no box real).
    const devMs = toEpochMs(freshest.device_ts)
    let baseS: number | null = null
    const lastMs = toEpochMs(freshest.collector?.last_sample_ts)
    if (lastMs != null) {
      baseS = devMs == null ? 0 : Math.max(0, (devMs - lastMs) / 1000)
    } else if (latest && devMs != null) {
      baseS = Math.max(0, devMs / 1000 - latest.ts)
    }
    if (baseS == null) return null
    const elapsedS = receivedAt != null ? Math.max(0, (nowMs - receivedAt) / 1000) : 0
    return baseS + elapsedS
  }, [freshest, live, liveReceivedAt, historyReceivedAt, latest, nowMs])

  const collectorDown = collector?.status === 'down' || collector?.alive === false
  const hasData = latest != null || collector != null

  const summary = useMemo(
    () =>
      evaluateHealth({
        latest, samples, collector, detections, thresholds, site, sampleAgeS, nowMs,
      }),
    [latest, samples, collector, detections, thresholds, site, sampleAgeS, nowMs],
  )

  const [logUnit, setLogUnit] = useState<string | null>(null)

  // Navegação sob demanda: quando o usuário faz pan/zoom para ANTES do que
  // está carregado, sobe para a menor janela que cobre o intervalo pedido.
  // Só dispara em interação do usuário (o ChartsSection debounce+deduplica) —
  // zero-egress sem a página aberta continua valendo.
  const handleRequestRange = useCallback(
    (startEpochSec: number) => {
      if (!onExpandWindow) return
      const nowS = Date.now() / 1000
      const neededSpan = Math.max(0, nowS - startEpochSec)
      if (neededSpan <= WINDOW_SPAN_S[windowSel]) return
      const wider = WINDOW_ORDER.find((w) => WINDOW_SPAN_S[w] >= neededSpan) ?? '30d'
      if (wider !== windowSel) onExpandWindow(wider)
    },
    [onExpandWindow, windowSel],
  )

  // resetKey das fronteiras de painel: uma nova amostra "re-arma" um painel
  // que tenha quebrado no render (contrato divergiu e depois normalizou).
  const panelResetKey = latest?.ts ?? historyReceivedAt ?? 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Banner de frescor — SEMPRE visível (sticky) */}
      <div className={s.freshnessBar}>
        <Banner variant={collectorDown ? 'danger' : sampleAgeS != null && sampleAgeS > STALE_AFTER_S ? 'warning' : 'info'}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            {collectorDown ? (
              <strong>
                Coletor parado
                {sampleAgeS != null ? ` — sem amostra há ${fmtDurationS(sampleAgeS)}` : ''} — os
                dados abaixo são históricos, não atuais.
              </strong>
            ) : sampleAgeS != null ? (
              <>
                Última amostra do coletor: <strong>há {fmtDurationS(sampleAgeS)}</strong>
                {sampleAgeS > STALE_AFTER_S && <Badge variant="warning">dado velho</Badge>}
                {historySpanS > 0 && (
                  <span className={s.muted}>· {fmtDurationS(historySpanS)} de histórico</span>
                )}
              </>
            ) : (
              <>Coletando — aguardando a primeira amostra do box…</>
            )}
            <Tooltip label="Snapshot a cada ~10 s enquanto a página está aberta. Com a aba oculta ou fechada o polling PARA — egress só com a página aberta.">
              <span className={s.liveBadge}>
                <span className={s.liveDot} aria-hidden="true" />
                <Radio size={12} aria-hidden="true" />
                Ao vivo · 10 s
              </span>
            </Tooltip>
          </span>
        </Banner>
      </div>

      {historyWaking && (
        <Banner variant="info">
          Acordando o box — o agente faz poll de comandos a cada 60 s.
          Aguardando a resposta da janela {windowSel}...
        </Banner>
      )}

      {historyError && (
        <Banner variant="danger">
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            {historyError}
            <Button size="sm" variant="secondary" onClick={() => void startQuery()}>
              Tentar de novo
            </Button>
          </span>
        </Banner>
      )}

      <PanelBoundary title="Semáforo" resetKey={panelResetKey}>
        <Semaphore summary={summary} hasData={hasData} />
      </PanelBoundary>

      {queryLoading && !history ? (
        <div className={s.chartsGrid}>
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} variant="rect" height={240} />
          ))}
        </div>
      ) : (
        <PanelBoundary title="Gráficos" resetKey={panelResetKey}>
          <ChartsSection
            samples={samples}
            windowSel={windowSel}
            onRequestRange={handleRequestRange}
          />
        </PanelBoundary>
      )}

      <div className={s.cardsGrid}>
        <PanelBoundary title="Hardware" resetKey={panelResetKey}>
          <HardwarePanel
            latest={latest}
            samples={samples}
            events={events}
            collector={collector}
            thresholds={thresholds}
            windowSel={windowSel}
          />
        </PanelBoundary>
        <PanelBoundary title="Serviços" resetKey={panelResetKey}>
          <ServicesPanel latest={latest} thresholds={thresholds} onViewLog={setLogUnit} />
        </PanelBoundary>
        <PanelBoundary title="Pipeline de vídeo" resetKey={panelResetKey}>
          <PipelinePanel latest={latest} />
        </PanelBoundary>
        <PanelBoundary title="Coleta de frames" resetKey={panelResetKey}>
          <CollectionPanel latest={latest} samples={samples} windowSel={windowSel} />
        </PanelBoundary>
        <PanelBoundary title="Rede" resetKey={panelResetKey}>
          <NetworkPanel latest={latest} thresholds={thresholds} />
        </PanelBoundary>
        <PanelBoundary title="OTA / Versão" resetKey={panelResetKey}>
          <VersionPanel site={site} latest={latest} />
        </PanelBoundary>
        <PanelBoundary title="Inferência" resetKey={panelResetKey}>
          <InferencePanel
            latest={latest}
            detections={detections}
            detectionsError={detectionsError}
            thresholds={thresholds}
            nowMs={nowMs}
          />
        </PanelBoundary>
      </div>

      <LogtailModal
        open={logUnit != null}
        siteId={siteId}
        unit={logUnit}
        onClose={() => setLogUnit(null)}
      />
    </div>
  )
}
