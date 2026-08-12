/**
 * InferencePanel — a razão da página: modelo/versão/FPS/latência/descartes/
 * detecções por classe POR CÂMERA. Enquanto os modelos não rodam na operação
 * assistida, mostra um EmptyState honesto MAS mantém o heartbeat de detecção
 * (endpoint cloud-side /detections) — silêncio ≠ sem violação.
 */
import { BrainCircuit } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '../../components/ui/Card/Card'
import { Badge } from '../../components/ui/Badge/Badge'
import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import type {
  DetectionsHealth,
  MonitoringSample,
  MonitoringThresholds,
} from '../../types/monitoring'
import { RUNBOOK, agoMinutes, asRatio, fmtDurationS, fmtHeartbeatAge, fmtNum } from './health'
import { ErrorState, MiniTable } from './parts'
import * as s from './monitoring.css'

interface InferencePanelProps {
  latest: MonitoringSample | null
  detections: DetectionsHealth | null
  /** Falha ao consultar o heartbeat cloud-side — erro ≠ "sem detecção". */
  detectionsError?: string | null
  thresholds: MonitoringThresholds
  nowMs: number
}

export function InferencePanel({
  latest,
  detections,
  detectionsError,
  thresholds,
  nowMs,
}: InferencePanelProps) {
  const inf = latest?.inference
  const available = inf != null && asRatio(inf.available) > 0
  const cams = inf?.cameras
    ? Object.entries(inf.cameras).sort(([a], [b]) => a.localeCompare(b))
    : []
  const detCams = detections?.cameras ?? []
  // A "chain" é POR CÂMERA no contrato real (não no topo). Agregamos o maior
  // lag detecção→ingest da janela — acesso opcional em cada nível para nunca
  // derrubar a página se um campo faltar. (Bug antigo: detections.chain.* em
  // objeto sem chain lançava TypeError → ErrorBoundary global apagava tudo.)
  const chainLag = detCams.reduce<number | null>((max, c) => {
    const v = c.chain?.detection_to_ingest_s ?? c.ingest_lag_s
    return v != null && (max == null || v > max) ? v : max
  }, null)

  return (
    <Card className={s.cardFull}>
      <CardHeader>
        <CardTitle>
          <BrainCircuit size={15} aria-hidden="true" style={{ verticalAlign: -2, marginRight: 6 }} />
          Inferência
        </CardTitle>
        {available ? (
          <Badge variant="success">Rodando</Badge>
        ) : (
          <Badge variant="neutral">Aguardando modelos</Badge>
        )}
      </CardHeader>
      <CardBody>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {available && cams.length > 0 ? (
            <MiniTable
              headers={['Câmera', 'Modelo', 'Versão', 'FPS', 'Latência', 'Descartes', 'Detecções/min por classe']}
            >
              {cams.map(([cam, c]) => (
                <tr key={cam}>
                  <td className={`${s.td} ${s.mono}`}>{cam}</td>
                  <td className={s.td}>{c.model ?? '—'}</td>
                  <td className={`${s.td} ${s.mono}`}>{c.model_version ?? '—'}</td>
                  <td className={s.td}>{fmtNum(c.fps, 1)}</td>
                  <td className={s.td}>{c.latency_ms != null ? `${fmtNum(c.latency_ms)} ms` : '—'}</td>
                  <td className={s.td}>{c.dropped_total ?? '—'}</td>
                  <td className={s.td} style={{ whiteSpace: 'normal' }}>
                    {c.detections_per_min && Object.keys(c.detections_per_min).length > 0 ? (
                      <span className={s.chipRow}>
                        {Object.entries(c.detections_per_min).map(([cls, n]) => (
                          <span key={cls} className={s.chip}>
                            {cls}: {fmtNum(n, 1)}
                          </span>
                        ))}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))}
            </MiniTable>
          ) : (
            <EmptyState
              title="Modelos ainda não rodando na operação assistida"
              description="Painéis prontos — preenchem automaticamente quando a inferência ligar no box. O heartbeat de detecção abaixo continua valendo."
            />
          )}

          {/* Heartbeat de detecção — sempre visível (cloud-side, sem egress do box) */}
          <div>
            <div className={s.sectionLabel}>Heartbeat de detecção (última hora)</div>
            {detectionsError ? (
              <ErrorState
                title="Falha ao consultar o heartbeat de detecção"
                detail={detectionsError}
              />
            ) : detCams.length === 0 ? (
              <p className={s.muted} style={{ margin: '6px 0 0' }}>
                Nenhuma câmera com registro de detecção no período.
              </p>
            ) : (
              <MiniTable headers={['Câmera', 'Última detecção', 'Detecções na janela', 'Lag de ingest']}>
                {detCams.map((c) => {
                  const age = agoMinutes(c.last_occurred_at, nowMs)
                  const silent = age == null || age > thresholds.heartbeat_max_min
                  return (
                    <tr key={c.camera_id ?? '?'}>
                      <td className={`${s.td} ${s.mono}`}>{c.camera_id ?? '—'}</td>
                      <td className={s.td}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                          {c.last_occurred_at
                            ? `há ${fmtHeartbeatAge(c.last_occurred_at, nowMs)}`
                            : 'nunca'}
                          {silent && (
                            <Badge variant="danger">
                              Sem detecção &gt; {thresholds.heartbeat_max_min} min
                            </Badge>
                          )}
                        </span>
                      </td>
                      <td className={s.td}>{c.detections_in_window ?? '—'}</td>
                      <td className={s.td}>
                        {c.ingest_lag_s != null ? fmtDurationS(c.ingest_lag_s) : '—'}
                      </td>
                    </tr>
                  )
                })}
              </MiniTable>
            )}
            <p className={s.muted} style={{ margin: '8px 0 0' }}>
              Corrente detecção → ingest:{' '}
              {chainLag != null ? fmtDurationS(chainLag) : '—'} · ingest → notificação: —
            </p>
            {detCams.some((c) => {
              const age = agoMinutes(c.last_occurred_at, nowMs)
              return age == null || age > thresholds.heartbeat_max_min
            }) && <p className={s.runbookText} style={{ margin: '4px 0 0' }}>{RUNBOOK.heartbeat}</p>}
          </div>
        </div>
      </CardBody>
    </Card>
  )
}
