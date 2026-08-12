/**
 * Contrato box↔API↔front do /monitoring (observabilidade do Jetson).
 *
 * Regressão-âncora: o InferencePanel lia `detections.chain.*` no TOPO, mas o
 * endpoint /detections aninha `chain` POR CÂMERA. Em objeto sem `chain` no topo
 * isso lançava TypeError no render → o ErrorBoundary global apagava a PÁGINA
 * INTEIRA (sintoma: "abre e fica em branco"). Este teste falha-antes/passa-
 * depois e trava os renomes de campo (last_occurred_at, detections_in_window,
 * net.api_ok/api_status_age_s, collection.available).
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { InferencePanel } from './InferencePanel'
import { NetworkPanel } from './NetworkPanel'
import { CollectionPanel } from './CollectionPanel'
import { DEFAULT_THRESHOLDS } from './health'
import type { DetectionsHealth, MonitoringSample } from '../../types/monitoring'

const NOW = 1_786_500_000_000 // epoch ms fixo (Date.now indisponível nos scripts)
const recentIso = new Date(NOW - 2 * 60_000).toISOString()

describe('/monitoring — contrato de detecções (não pode derrubar a página)', () => {
  it('renderiza com chain POR CÂMERA e SEM chain no topo (o bug antigo)', () => {
    const detections: DetectionsHealth = {
      cameras: [
        {
          camera_id: 'cam-1',
          last_occurred_at: recentIso,
          last_received_at: recentIso,
          detections_in_window: 7,
          ingest_lag_s: 1.2,
          chain: { detection_to_ingest_s: 1.2, ingest_to_notification_s: null },
        },
      ],
      window_minutes: 60,
      count: 1,
    }
    // Se o acesso ainda fosse detections.chain.*, isto lançaria e o teste quebra.
    render(
      <InferencePanel latest={null} detections={detections} thresholds={DEFAULT_THRESHOLDS} nowMs={NOW} />,
    )
    expect(screen.queryByText('cam-1')).not.toBeNull()
    expect(screen.queryByText('7')).not.toBeNull() // detections_in_window
  })

  it('não lança quando a câmera vem SEM chain (campo ausente)', () => {
    const detections: DetectionsHealth = {
      cameras: [
        { camera_id: 'cam-x', last_occurred_at: null, detections_in_window: null, ingest_lag_s: null },
      ],
    }
    expect(() =>
      render(
        <InferencePanel latest={null} detections={detections} thresholds={DEFAULT_THRESHOLDS} nowMs={NOW} />,
      ),
    ).not.toThrow()
  })

  it('erro do heartbeat é DISTINTO de "sem detecção" (fail-loud)', () => {
    render(
      <InferencePanel
        latest={null}
        detections={null}
        detectionsError="A API não está servindo o monitoramento (resposta inesperada)."
        thresholds={DEFAULT_THRESHOLDS}
        nowMs={NOW}
      />,
    )
    expect(screen.getByRole('alert').textContent).toMatch(/Falha ao consultar o heartbeat/i)
  })
})

describe('/monitoring — renomes de campo alinhados ao coletor real', () => {
  it('NetworkPanel: "Último OK" vem de api_ok + api_status_age_s (não de api_last_ok_ts)', () => {
    const latest = {
      ts: NOW / 1000,
      net: { api_ok: true, api_status_age_s: 30, api_rtt_ms: 42, gw_rtt_ms: 5, gw_loss_pct: 0, tx_kbps: 100, rx_kbps: 50, tailscale_up: true },
    } as MonitoringSample
    render(<NetworkPanel latest={latest} thresholds={DEFAULT_THRESHOLDS} />)
    expect(screen.queryByText(/Último OK: há/i)).not.toBeNull()
    expect(screen.queryByText(/42 ms/)).not.toBeNull()
  })

  it('CollectionPanel: badge de coleta lê collection.available', () => {
    const latest = {
      ts: NOW / 1000,
      collection: { available: true, cameras: { 'cam-1': { frames_uploaded: 120, target: 200 } } },
    } as MonitoringSample
    render(<CollectionPanel latest={latest} samples={[latest]} windowSel="2h" />)
    expect(screen.queryByText('Ativo')).not.toBeNull() // AliveBadge de available=true
    expect(screen.queryByText('cam-1')).not.toBeNull()
  })
})
