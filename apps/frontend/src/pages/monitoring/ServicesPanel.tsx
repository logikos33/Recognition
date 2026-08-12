/**
 * ServicesPanel — units systemd do box: estado, uptime, restarts (destaque),
 * RAM/CPU vs teto e botão "Ver log" (logtail redigido no box).
 */
import { ServerCog } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '../../components/ui/Card/Card'
import { Badge } from '../../components/ui/Badge/Badge'
import { Button } from '../../components/ui/Button/Button'
import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import type { MonitoringSample, MonitoringThresholds } from '../../types/monitoring'
import { LOGTAIL_UNITS, fmtDurationS, fmtMb, fmtPct } from './health'
import { MiniTable, levelColor } from './parts'
import * as s from './monitoring.css'

interface ServicesPanelProps {
  latest: MonitoringSample | null
  thresholds: MonitoringThresholds
  onViewLog: (unit: string) => void
}

function unitStateBadge(active: string | undefined, sub: string | undefined) {
  if (!active) return <Badge variant="neutral">—</Badge>
  const label = sub ? `${active} (${sub})` : active
  if (active === 'active') return <Badge variant="success">{label}</Badge>
  if (active === 'activating' || active === 'reloading') return <Badge variant="warning">{label}</Badge>
  return <Badge variant="danger">{label}</Badge>
}

export function ServicesPanel({ latest, thresholds, onViewLog }: ServicesPanelProps) {
  const svc = latest?.svc
  const units = svc ? Object.entries(svc).sort(([a], [b]) => a.localeCompare(b)) : []

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <ServerCog size={15} aria-hidden="true" style={{ verticalAlign: -2, marginRight: 6 }} />
          Serviços
        </CardTitle>
      </CardHeader>
      <CardBody>
        {units.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <EmptyState
              title="Sem dados de serviços"
              description="Aguardando amostra do coletor com o estado das units"
            />
            <div className={s.chipRow} style={{ justifyContent: 'center' }}>
              {LOGTAIL_UNITS.map((unit) => (
                <Button key={unit} size="sm" variant="ghost" onClick={() => onViewLog(unit)}>
                  Log {unit}
                </Button>
              ))}
            </div>
          </div>
        ) : (
          <MiniTable headers={['Unit', 'Estado', 'Uptime', 'Restarts', 'RAM', 'CPU', '']}>
            {units.map(([unit, u]) => {
              const restartsBad = (u.nrestarts ?? 0) >= thresholds.restarts_warn
              const memOver =
                u.mem_mb != null && u.mem_max_mb != null && u.mem_max_mb > 0 &&
                u.mem_mb / u.mem_max_mb >= 0.9
              return (
                <tr key={unit}>
                  <td className={`${s.td} ${s.mono}`}>{unit}</td>
                  <td className={s.td}>{unitStateBadge(u.active, u.sub)}</td>
                  <td className={s.td}>{u.uptime_s != null ? fmtDurationS(u.uptime_s) : '—'}</td>
                  <td className={s.td}>
                    <span
                      style={restartsBad ? { color: levelColor('warn'), fontWeight: 700 } : undefined}
                    >
                      {u.nrestarts ?? '—'}
                    </span>
                  </td>
                  <td className={s.td}>
                    <span style={memOver ? { color: levelColor('warn'), fontWeight: 600 } : undefined}>
                      {fmtMb(u.mem_mb)}
                      {u.mem_max_mb != null && ` / ${fmtMb(u.mem_max_mb)}`}
                    </span>
                  </td>
                  <td className={s.td}>{fmtPct(u.cpu_pct)}</td>
                  <td className={s.td}>
                    <Button size="sm" variant="ghost" onClick={() => onViewLog(unit)}>
                      Ver log
                    </Button>
                  </td>
                </tr>
              )
            })}
          </MiniTable>
        )}
      </CardBody>
    </Card>
  )
}
