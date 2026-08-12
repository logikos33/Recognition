/**
 * VersionPanel — OTA/versão: release atual no box vs target do canal.
 * Divergência = badge de alerta + linha de runbook.
 */
import { GitBranch } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '../../components/ui/Card/Card'
import { Badge } from '../../components/ui/Badge/Badge'
import type { MonitoringSample, MonitoringSite } from '../../types/monitoring'
import { RUNBOOK, fmtIsoShort } from './health'
import { Stat } from './parts'
import * as s from './monitoring.css'

interface VersionPanelProps {
  site: MonitoringSite | null
  latest: MonitoringSample | null
}

export function VersionPanel({ site, latest }: VersionPanelProps) {
  const versions = latest?.versions
  const currentRef = versions?.current_ref ?? null
  const divergent = site?.divergent === true

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <GitBranch size={15} aria-hidden="true" style={{ verticalAlign: -2, marginRight: 6 }} />
          OTA / Versão
        </CardTitle>
        {site?.divergent == null ? (
          <Badge variant="neutral">Sem comparação</Badge>
        ) : divergent ? (
          <Badge variant="warning">Divergente do target</Badge>
        ) : (
          <Badge variant="success">Em dia</Badge>
        )}
      </CardHeader>
      <CardBody>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className={s.statGrid}>
            <Stat
              label="Release no box"
              value={<span className={s.mono}>{currentRef ?? '—'}</span>}
            />
            <Stat
              label="Target do canal"
              value={<span className={s.mono}>{site?.target_ref ?? '—'}</span>}
              sub={versions?.ota_channel ? `Canal: ${versions.ota_channel}` : undefined}
            />
            <Stat
              label="Versão do agente"
              value={versions?.edge_version ?? site?.last_heartbeat?.edge_version ?? '—'}
              sub={
                site?.last_heartbeat?.received_at
                  ? `Heartbeat: ${fmtIsoShort(site.last_heartbeat.received_at)}`
                  : undefined
              }
            />
          </div>
          {divergent && <span className={s.runbookText}>{RUNBOOK.ota}</span>}
        </div>
      </CardBody>
    </Card>
  )
}
