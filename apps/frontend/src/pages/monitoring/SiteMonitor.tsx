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
import { evaluateHealth, fmtDurationS } from './health'
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
import * as s from './monitoring.css'

const STALE_AFTER_S = 45
const MAX_LIVE_SAMPLES = 720

interface SiteMonitorProps {
  site: MonitoringSite
  windowSel: MonitoringWindow
  thresholds: MonitoringThresholds
}

export function SiteMonitor({ site, windowSel, thresholds }: SiteMonitorProps) {
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
      const res = await monitoringService.querySite(siteId, windowSel)
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

  const loadDetections = useCallback(async () => {
    setDetections(await monitoringService.getDetections(siteId, 60))
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

  const latest = samples.length ? samples[samples.length - 1] : null
  const freshest = live ?? history
  const collector = freshest?.collector ?? null

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
    const dev = freshest.device_ts ? Date.parse(freshest.device_ts) : Number.NaN
    let baseS: number | null = null
    const lastIso = freshest.collector?.last_sample_ts
    if (lastIso) {
      const last = Date.parse(lastIso)
      if (!Number.isNaN(last)) {
        baseS = Number.isNaN(dev) ? 0 : Math.max(0, (dev - last) / 1000)
      }
    } else if (latest && !Number.isNaN(dev)) {
      baseS = Math.max(0, dev / 1000 - latest.ts)
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Banner de frescor — SEMPRE visível (sticky) */}
      <div className={s.freshnessBar}>
        <Banner variant={collectorDown ? 'danger' : sampleAgeS != null && sampleAgeS > STALE_AFTER_S ? 'warning' : 'info'}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            {collectorDown ? (
              <strong>Coletor parado — os dados abaixo são históricos, não atuais.</strong>
            ) : (
              <>
                Última amostra do coletor:{' '}
                {sampleAgeS != null ? <strong>há {fmtDurationS(sampleAgeS)}</strong> : 'sem amostra ainda'}
                {sampleAgeS != null && sampleAgeS > STALE_AFTER_S && (
                  <Badge variant="warning">dado velho</Badge>
                )}
              </>
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

      <Semaphore summary={summary} hasData={hasData} />

      {queryLoading && !history ? (
        <div className={s.chartsGrid}>
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} variant="rect" height={240} />
          ))}
        </div>
      ) : (
        <ChartsSection samples={samples} windowSel={windowSel} />
      )}

      <div className={s.cardsGrid}>
        <HardwarePanel
          latest={latest}
          samples={samples}
          events={events}
          collector={collector}
          thresholds={thresholds}
          windowSel={windowSel}
        />
        <ServicesPanel latest={latest} thresholds={thresholds} onViewLog={setLogUnit} />
        <PipelinePanel latest={latest} />
        <CollectionPanel latest={latest} samples={samples} windowSel={windowSel} />
        <NetworkPanel latest={latest} thresholds={thresholds} />
        <VersionPanel site={site} latest={latest} />
        <InferencePanel
          latest={latest}
          detections={detections}
          thresholds={thresholds}
          nowMs={nowMs}
        />
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
