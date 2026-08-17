/**
 * PipelinePanel — pipeline de vídeo por câmera: ffmpeg vivo, seg/min,
 * p50/p95 do push, falhas de POST, idade da última imagem e reconexões.
 */
import { Video } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '../../components/ui/Card/Card'
import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import type { MonitoringSample } from '../../types/monitoring'
import { fmtDurationS, fmtNum } from './health'
import { AliveBadge, MiniTable, levelColor } from './parts'
import * as s from './monitoring.css'

interface PipelinePanelProps {
  latest: MonitoringSample | null
}

export function PipelinePanel({ latest }: PipelinePanelProps) {
  const cams = latest?.pipeline?.cameras
    ? Object.entries(latest.pipeline.cameras).sort(([a], [b]) => a.localeCompare(b))
    : []

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <Video size={15} aria-hidden="true" style={{ verticalAlign: -2, marginRight: 6 }} />
          Pipeline de vídeo
        </CardTitle>
      </CardHeader>
      <CardBody>
        {cams.length === 0 ? (
          <EmptyState
            title="Sem dados de pipeline"
            description="Nenhuma câmera reportada na última amostra do coletor"
          />
        ) : (
          <MiniTable
            headers={[
              'Câmera', 'FFmpeg', 'Seg/min', 'Push p50', 'Push p95',
              'Falhas', 'Última imagem', 'Reconexões', 'Estado',
            ]}
          >
            {cams.map(([cam, p]) => {
              const stalePush = (p.last_push_age_s ?? 0) > 60
              return (
                <tr key={cam}>
                  <td className={`${s.td} ${s.mono}`}>{cam}</td>
                  <td className={s.td}><AliveBadge value={p.ffmpeg_alive} /></td>
                  <td className={s.td}>{fmtNum(p.segments_per_min, 1)}</td>
                  <td className={s.td}>{p.push_p50_ms != null ? `${fmtNum(p.push_p50_ms)} ms` : '—'}</td>
                  <td className={s.td}>{p.push_p95_ms != null ? `${fmtNum(p.push_p95_ms)} ms` : '—'}</td>
                  <td className={s.td}>
                    <span
                      style={
                        (p.push_fail_total ?? 0) > 0
                          ? { color: levelColor('warn'), fontWeight: 600 }
                          : undefined
                      }
                    >
                      {p.push_fail_total ?? '—'}
                    </span>
                  </td>
                  <td className={s.td}>
                    <span
                      style={stalePush ? { color: levelColor('crit'), fontWeight: 600 } : undefined}
                    >
                      {p.last_push_age_s != null ? `há ${fmtDurationS(p.last_push_age_s)}` : '—'}
                    </span>
                  </td>
                  <td className={s.td}>{p.restarts_total ?? '—'}</td>
                  <td className={s.td}>{p.state ?? '—'}</td>
                </tr>
              )
            })}
          </MiniTable>
        )}
      </CardBody>
    </Card>
  )
}
