/**
 * VersionPanel — OTA/versão: release atual no box vs target do canal.
 * Divergência = badge de alerta + linha de runbook.
 */
import { GitBranch } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '../../components/ui/Card/Card'
import { Badge } from '../../components/ui/Badge/Badge'
import type { MonitoringSample, MonitoringSite } from '../../types/monitoring'
import { RUNBOOK, fmtIsoShort, siteDivergent, siteTargetRef } from './health'
import { Stat } from './parts'
import * as s from './monitoring.css'

interface VersionPanelProps {
  site: MonitoringSite | null
  latest: MonitoringSample | null
}

export function VersionPanel({ site, latest }: VersionPanelProps) {
  const versions = latest?.versions
  const currentRef = versions?.current_ref ?? null
  const targetRef = siteTargetRef(site)
  // Compara o SHA REAL do symlink do box (amostra) com o target do canal —
  // não o edge_version do heartbeat (rótulo manual, geraria alerta falso).
  const divergentState = siteDivergent(site, currentRef)
  const divergent = divergentState === true

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <GitBranch size={15} aria-hidden="true" style={{ verticalAlign: -2, marginRight: 6 }} />
          OTA / Versão
        </CardTitle>
        {divergentState == null ? (
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
              value={<span className={s.mono}>{targetRef ?? '—'}</span>}
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
