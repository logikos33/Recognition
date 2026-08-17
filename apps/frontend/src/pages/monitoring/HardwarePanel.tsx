/**
 * HardwarePanel — CPU por core, RAM/swap, GPU, temperaturas, throttling em
 * destaque, power mode, disco (com distância da reserva), uptime/load, OOM.
 */
import { Cpu } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '../../components/ui/Card/Card'
import { Badge } from '../../components/ui/Badge/Badge'
import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import type {
  CollectorStatus,
  MonitoringEvent,
  MonitoringSample,
  MonitoringThresholds,
} from '../../types/monitoring'
import {
  EVENT_LABELS,
  EXPECTED_POWER_MODE,
  asRatio,
  fmtBytes,
  fmtDurationS,
  fmtGhz,
  fmtMb,
  fmtNum,
  fmtPct,
  pctOf,
  throttleDurationS,
} from './health'
import { Meter, MiniTable, Stat, levelColor, levelFor } from './parts'
import * as s from './monitoring.css'

interface HardwarePanelProps {
  latest: MonitoringSample | null
  samples: MonitoringSample[]
  events: MonitoringEvent[]
  collector: CollectorStatus | null
  thresholds: MonitoringThresholds
  windowSel: '2h' | '24h' | '7d' | '30d'
}

export function HardwarePanel({
  latest, samples, events, collector, thresholds, windowSel,
}: HardwarePanelProps) {
  const hw = latest?.hw
  const throttleRatio = asRatio(hw?.throttle?.active)
  const throttleDur = throttleDurationS(samples)
  const ramPct = pctOf(hw?.ram_used_mb, hw?.ram_total_mb)
  const swapPct = pctOf(hw?.swap_used_mb, hw?.swap_total_mb)
  const diskFree = hw?.disk?.free_gb
  const diskReserve = hw?.disk?.min_free_gb
  const distToReserve = diskFree != null && diskReserve != null ? diskFree - diskReserve : null
  const powerModeBad =
    thresholds.alert_power_mode && hw?.power_mode != null && hw.power_mode !== EXPECTED_POWER_MODE

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <Cpu size={15} aria-hidden="true" style={{ verticalAlign: -2, marginRight: 6 }} />
          Hardware
        </CardTitle>
        {throttleRatio > 0 && (
          <Badge variant="danger">
            Throttling{throttleDur > 0 ? ` há ${fmtDurationS(throttleDur)}` : ' ativo'}
          </Badge>
        )}
      </CardHeader>
      <CardBody>
        {!hw ? (
          <EmptyState
            title="Sem amostra de hardware"
            description="Aguardando a primeira resposta do coletor no box"
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className={s.statGrid}>
              <Stat
                label="CPU"
                value={fmtPct(hw.cpu_pct)}
                sub={
                  hw.cpu_cores_pct?.length ? (
                    <span className={s.coreGrid} aria-label="Uso por core de CPU">
                      {hw.cpu_cores_pct.map((core, i) => (
                        <span key={i} className={s.coreBar} title={`Core ${i}: ${fmtPct(core)}`}>
                          <span
                            className={s.coreFill}
                            style={{
                              height: `${Math.min(100, Math.max(2, core))}%`,
                              background: levelColor(levelFor(core, 85, 95)),
                            }}
                          />
                        </span>
                      ))}
                    </span>
                  ) : undefined
                }
              />
              <Stat
                label="RAM"
                value={`${fmtMb(hw.ram_used_mb)} / ${fmtMb(hw.ram_total_mb)}`}
                sub={
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <span>{fmtPct(ramPct)}</span>
                    <Meter
                      pct={ramPct}
                      level={levelFor(ramPct, thresholds.ram_pct_warn, thresholds.ram_pct_crit)}
                    />
                  </span>
                }
              />
              <Stat
                label="Swap"
                value={`${fmtMb(hw.swap_used_mb)} / ${fmtMb(hw.swap_total_mb)}`}
                sub={
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <span>{fmtPct(swapPct)}</span>
                    <Meter pct={swapPct} level={levelFor(swapPct, thresholds.swap_warn_pct)} />
                  </span>
                }
              />
              <Stat
                label="GPU"
                value={fmtPct(hw.gpu_pct)}
                sub={
                  hw.gpu_freq_hz != null
                    ? `${fmtGhz(hw.gpu_freq_hz)}${hw.gpu_freq_max_hz != null ? ` / ${fmtGhz(hw.gpu_freq_max_hz)}` : ''}`
                    : undefined
                }
              />
              <Stat label="EMC (memória)" value={fmtPct(hw.emc_pct)} />
              <Stat
                label="Power mode"
                value={
                  hw.power_mode ? (
                    <Badge variant={powerModeBad ? 'warning' : 'success'}>{hw.power_mode}</Badge>
                  ) : (
                    '—'
                  )
                }
                sub={powerModeBad ? `Esperado: ${EXPECTED_POWER_MODE}` : undefined}
              />
              <Stat
                label="Disco livre"
                value={diskFree != null ? `${diskFree.toFixed(1)} GB` : '—'}
                sub={
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <span>
                      {hw.disk?.total_gb != null && `de ${hw.disk.total_gb.toFixed(0)} GB`}
                      {distToReserve != null && ` · ${distToReserve.toFixed(1)} GB até a reserva`}
                    </span>
                    {diskFree != null && hw.disk?.total_gb != null && (
                      <Meter
                        pct={100 - (diskFree / hw.disk.total_gb) * 100}
                        level={
                          distToReserve != null && distToReserve <= 0
                            ? 'crit'
                            : diskFree < thresholds.disk_min_free_gb
                              ? 'warn'
                              : 'ok'
                        }
                      />
                    )}
                  </span>
                }
              />
              <Stat
                label="Escrita em disco"
                value={hw.disk?.write_mbps != null ? `${fmtNum(hw.disk.write_mbps, 1)} MB/s` : '—'}
              />
              <Stat
                label="Uptime"
                value={hw.uptime_s != null ? fmtDurationS(hw.uptime_s) : '—'}
                sub={
                  hw.load1 != null
                    ? `load ${fmtNum(hw.load1, 2)} / ${fmtNum(hw.load5, 2)} / ${fmtNum(hw.load15, 2)}`
                    : undefined
                }
              />
              <Stat
                label="OOM kills"
                value={
                  hw.oom_kills_total != null ? (
                    <span style={hw.oom_kills_total > 0 ? { color: levelColor('crit') } : undefined}>
                      {hw.oom_kills_total}
                    </span>
                  ) : (
                    '—'
                  )
                }
              />
              {collector?.db_size_bytes != null && (
                <Stat label="Banco do coletor" value={fmtBytes(collector.db_size_bytes)} />
              )}
            </div>

            {/* Temperaturas por zona */}
            {hw.temps_c && Object.keys(hw.temps_c).length > 0 && (
              <div>
                <div className={s.sectionLabel}>Temperaturas (°C)</div>
                <div className={s.chipRow} style={{ marginTop: 6 }}>
                  {Object.entries(hw.temps_c).map(([zone, temp]) => (
                    <span
                      key={zone}
                      className={s.chip}
                      style={{
                        color: levelColor(levelFor(temp, thresholds.temp_warn_c, thresholds.temp_crit_c)),
                        borderColor:
                          levelFor(temp, thresholds.temp_warn_c, thresholds.temp_crit_c) === 'ok'
                            ? undefined
                            : levelColor(levelFor(temp, thresholds.temp_warn_c, thresholds.temp_crit_c)),
                      }}
                    >
                      {zone}: {temp.toFixed(1)}°
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Consumo (mW) */}
            {hw.power_mw && Object.keys(hw.power_mw).length > 0 && (
              <div>
                <div className={s.sectionLabel}>Consumo (W)</div>
                <div className={s.chipRow} style={{ marginTop: 6 }}>
                  {Object.entries(hw.power_mw).map(([rail, mw]) => (
                    <span key={rail} className={s.chip}>
                      {rail}: {(mw / 1000).toFixed(1)} W
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Eventos na janela — throttling em destaque */}
            {events.length > 0 && (
              <div>
                <div className={s.sectionLabel}>Eventos na janela ({windowSel})</div>
                <MiniTable headers={['Quando', 'Evento', 'Detalhe']}>
                  {[...events]
                    .sort((a, b) => b.ts - a.ts)
                    .slice(0, 30)
                    .map((ev, i) => {
                      const isThrottle = ev.kind.startsWith('throttle')
                      const isOom = ev.kind === 'oom_kill'
                      return (
                        <tr key={`${ev.ts}-${ev.kind}-${i}`}>
                          <td className={`${s.td} ${s.mono}`}>
                            {new Date(ev.ts * 1000).toLocaleString('pt-BR', {
                              day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
                            })}
                          </td>
                          <td className={s.td}>
                            <span
                              style={
                                isThrottle || isOom
                                  ? { color: levelColor('crit'), fontWeight: 600 }
                                  : undefined
                              }
                            >
                              {EVENT_LABELS[ev.kind] ?? ev.kind}
                            </span>
                          </td>
                          <td className={s.td}>{ev.detail ?? '—'}</td>
                        </tr>
                      )
                    })}
                </MiniTable>
              </div>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
