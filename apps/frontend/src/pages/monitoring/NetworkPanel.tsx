/**
 * NetworkPanel — Tailscale, RTT até a API, RTT/perda do gateway e taxa
 * de upload/download no NIC do box.
 */
import { Network } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '../../components/ui/Card/Card'
import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import type { MonitoringSample, MonitoringThresholds } from '../../types/monitoring'
import { fmtIsoShort, fmtKbps, fmtNum } from './health'
import { AliveBadge, Stat, levelColor, levelFor } from './parts'
import * as s from './monitoring.css'

interface NetworkPanelProps {
  latest: MonitoringSample | null
  thresholds: MonitoringThresholds
}

function fmtApiLastOk(v: number | string | null | undefined): string {
  if (v == null) return '—'
  if (typeof v === 'number') return fmtIsoShort(new Date(v * 1000).toISOString())
  return fmtIsoShort(v)
}

export function NetworkPanel({ latest, thresholds }: NetworkPanelProps) {
  const net = latest?.net

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <Network size={15} aria-hidden="true" style={{ verticalAlign: -2, marginRight: 6 }} />
          Rede
        </CardTitle>
        <AliveBadge value={net?.tailscale_up} />
      </CardHeader>
      <CardBody>
        {!net ? (
          <EmptyState
            title="Sem dados de rede"
            description="Aguardando amostra do coletor com métricas de rede"
          />
        ) : (
          <div className={s.statGrid}>
            <Stat
              label="RTT até a API"
              value={
                <span
                  style={
                    levelFor(net.api_rtt_ms, thresholds.api_rtt_warn_ms) !== 'ok'
                      ? { color: levelColor('warn') }
                      : undefined
                  }
                >
                  {net.api_rtt_ms != null ? `${fmtNum(net.api_rtt_ms)} ms` : '—'}
                </span>
              }
              sub={`Último OK: ${fmtApiLastOk(net.api_last_ok_ts)}`}
            />
            <Stat
              label="RTT gateway"
              value={net.gw_rtt_ms != null ? `${fmtNum(net.gw_rtt_ms, 1)} ms` : '—'}
            />
            <Stat
              label="Perda gateway"
              value={
                <span
                  style={
                    levelFor(net.gw_loss_pct, thresholds.gw_loss_warn_pct) !== 'ok'
                      ? { color: levelColor('warn') }
                      : undefined
                  }
                >
                  {net.gw_loss_pct != null ? `${fmtNum(net.gw_loss_pct, 1)}%` : '—'}
                </span>
              }
            />
            <Stat label="Upload (tx)" value={fmtKbps(net.tx_kbps)} sub={net.nic ? `NIC ${net.nic}` : undefined} />
            <Stat label="Download (rx)" value={fmtKbps(net.rx_kbps)} />
          </div>
        )}
      </CardBody>
    </Card>
  )
}
