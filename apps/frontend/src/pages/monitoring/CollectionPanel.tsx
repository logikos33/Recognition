/**
 * CollectionPanel — coleta de frames por câmera vs cota.
 * "Na janela" = delta dos contadores CUMULATIVOS entre a primeira e a última
 * amostra da janela consultada (reset de contador ⇒ usa o valor final).
 */
import { Images } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '../../components/ui/Card/Card'
import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import type { MonitoringSample, MonitoringWindow } from '../../types/monitoring'
import { fmtDurationS } from './health'
import { AliveBadge, Meter, MiniTable, levelFor } from './parts'
import * as s from './monitoring.css'

interface CollectionPanelProps {
  latest: MonitoringSample | null
  samples: MonitoringSample[]
  windowSel: MonitoringWindow
}

/** Delta do contador cumulativo de uma câmera ao longo da janela. */
function deltaInWindow(samples: MonitoringSample[], cam: string): number | null {
  let first: number | null = null
  let last: number | null = null
  for (const sample of samples) {
    const v = sample.collection?.cameras?.[cam]?.frames_uploaded
    if (v == null) continue
    if (first == null) first = v
    last = v
  }
  if (first == null || last == null) return null
  const delta = last - first
  // Contador reiniciou no meio da janela (box rebootou): delta negativo
  // mentiria — o valor final é o piso honesto do que subiu desde o reset.
  return delta >= 0 ? delta : last
}

export function CollectionPanel({ latest, samples, windowSel }: CollectionPanelProps) {
  const col = latest?.collection
  const cams = col?.cameras
    ? Object.entries(col.cameras).sort(([a], [b]) => a.localeCompare(b))
    : []
  const windowLabel = windowSel === '24h' ? 'hoje (24h)' : `na janela (${windowSel})`

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <Images size={15} aria-hidden="true" style={{ verticalAlign: -2, marginRight: 6 }} />
          Coleta de frames
        </CardTitle>
        <AliveBadge value={col?.enabled} />
      </CardHeader>
      <CardBody>
        {cams.length === 0 ? (
          <EmptyState
            title="Sem dados de coleta"
            description="Coleta desligada ou sem câmeras reportadas na última amostra"
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <MiniTable headers={['Câmera', 'Enviados (total)', `Enviados ${windowLabel}`, 'Cota', 'Progresso']}>
              {cams.map(([cam, c]) => {
                const delta = deltaInWindow(samples, cam)
                const pct =
                  c.target != null && c.target > 0 && c.frames_uploaded != null
                    ? (c.frames_uploaded / c.target) * 100
                    : null
                return (
                  <tr key={cam}>
                    <td className={`${s.td} ${s.mono}`}>{cam}</td>
                    <td className={s.td}>{c.frames_uploaded ?? '—'}</td>
                    <td className={s.td}>{delta ?? '—'}</td>
                    <td className={s.td}>{c.target ?? '—'}</td>
                    <td className={s.td} style={{ minWidth: 120 }}>
                      {pct != null ? (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ flex: 1, minWidth: 60 }}>
                            <Meter pct={pct} level={levelFor(100 - pct, 100)} />
                          </span>
                          <span className={s.muted}>{pct.toFixed(0)}%</span>
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                )
              })}
            </MiniTable>
            {col?.state_age_s != null && (
              <span className={s.muted}>
                Estado da coleta atualizado há {fmtDurationS(col.state_age_s)}
              </span>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
