/**
 * InfraPanel — aba Infra do dashboard de observability (WS11).
 *
 * USE (Utilization/Saturation/Errors) da infraestrutura: conexões do
 * PostgreSQL, Redis, R2 e filas Celery (profundidade + idade do item mais
 * antigo + falhas 24h) com drill-down de gráfico por fila.
 */
import { useState } from 'react'
import { HelpCircle } from 'lucide-react'
import { Tooltip } from '../../../../components/ui/Tooltip/Tooltip'
import { Badge } from '../../../../components/ui/Badge/Badge'
import { Banner } from '../../../../components/ui/Banner/Banner'
import { Skeleton } from '../../../../components/ui/Skeleton/Skeleton'
import { chartColors } from '../../../../theme/chartColors'
import { vars } from '../../../../styles/theme.css'
import * as s from '../../components/admin.css'
import type { ObsQueueInfo, ObsWindow, ObservabilitySummary } from '../../types/admin'
import { TimeseriesChart } from './TimeseriesChart'

function fmtAge(seconds: number | null): string {
  if (seconds == null) return '—'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const mins = Math.floor(seconds / 60)
  if (mins < 60) return `${mins}min`
  return `${Math.floor(mins / 60)}h`
}

function HeaderWithTooltip({ label, tooltip }: { label: string; tooltip: string }) {
  return (
    <span className={s.flex} style={{ gap: 4 }}>
      {label}
      <Tooltip label={tooltip}>
        <HelpCircle size={12} aria-label={`Ajuda: ${label}`} style={{ color: vars.color.textMuted }} />
      </Tooltip>
    </span>
  )
}

interface InfraPanelProps {
  summary: ObservabilitySummary | null
  windowSel: ObsWindow
  refreshMs: number
}

export function InfraPanel({ summary, windowSel, refreshMs }: InfraPanelProps) {
  const [selectedQueue, setSelectedQueue] = useState<string | null>(null)

  if (!summary) {
    if (refreshMs <= 0) {
      return (
        <Banner variant="info">
          Atualização pausada — selecione um intervalo de atualização para
          carregar os dados de infraestrutura.
        </Banner>
      )
    }
    return (
      <div className={s.metricsGrid}>
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} variant="rect" height={120} />
        ))}
      </div>
    )
  }

  const conn = summary.db.connections
  const redis = summary.services.redis
  const r2 = summary.services.r2
  const queues: ObsQueueInfo[] = summary.celery.queues

  return (
    <div>
      {/* Cards de infraestrutura */}
      <div className={s.metricsGrid} style={{ marginBottom: 16 }}>
        <Tooltip label="Conexões abertas no PostgreSQL: ativas executando query + ociosas no pool, sobre o máximo permitido — perto do limite, novas requisições começam a falhar">
          <div className={s.metricCard} aria-label="Conexões do banco de dados">
            <div className={s.metricValue}>
              {conn ? `${conn.active + conn.idle}/${conn.max}` : '—'}
            </div>
            <div className={s.metricLabel}>Conexões DB</div>
            <div className={s.muted}>
              {conn ? `${conn.active} ativas · ${conn.idle} ociosas` : 'sem dados'}
              {summary.db.latency_ms != null && ` · ${summary.db.latency_ms} ms`}
            </div>
          </div>
        </Tooltip>

        <Tooltip label="Redis: memória usada e clientes conectados — é o coração das filas e do tempo real; latência alta afeta todo o sistema">
          <div className={s.metricCard} aria-label="Redis">
            <div className={s.metricValue}>
              {redis?.mem_mb != null ? `${redis.mem_mb} MB` : '—'}
            </div>
            <div className={s.metricLabel}>Redis</div>
            <div className={s.muted}>
              {redis?.clients != null && `${redis.clients} clientes`}
              {redis?.latency_ms != null && ` · ping ${redis.latency_ms} ms`}
            </div>
          </div>
        </Tooltip>

        <Tooltip label="Tempo de resposta do armazenamento de evidências (R2) — lentidão atrasa upload de imagens e clipes">
          <div className={s.metricCard} aria-label="Armazenamento R2">
            <div className={s.metricValue}>
              {r2?.latency_ms != null ? `${r2.latency_ms} ms` : '—'}
            </div>
            <div className={s.metricLabel}>Armazenamento (R2)</div>
            <div className={s.muted}>{r2?.status === 'healthy' ? 'operacional' : r2?.status ?? 'sem dados'}</div>
          </div>
        </Tooltip>
      </div>

      {/* Série de conexões DB */}
      <div style={{ marginBottom: 16 }}>
        <TimeseriesChart
          key={`conn-${windowSel}`}
          title="Conexões ativas no banco"
          tooltip="Conexões executando queries ao longo do tempo — crescimento constante pode indicar vazamento de conexões"
          scope="db"
          metric="conn_active"
          window={windowSel}
          refreshMs={refreshMs}
          color={chartColors.accent}
        />
      </div>

      {/* Filas Celery */}
      <div className={s.card} style={{ marginBottom: 16 }}>
        <div className={s.cardTitle}>Filas de processamento (Celery)</div>
        <table className={s.table}>
          <thead>
            <tr>
              <th className={s.th}>Fila</th>
              <th className={s.th}>
                <HeaderWithTooltip
                  label="Profundidade"
                  tooltip="Profundidade da fila: tarefas aguardando processamento — cresce quando os workers não dão vazão"
                />
              </th>
              <th className={s.th}>
                <HeaderWithTooltip
                  label="Mais antigo"
                  tooltip="Há quanto tempo a tarefa mais antiga espera na fila — '—' quando a fila está vazia ou o dado não pôde ser lido"
                />
              </th>
              <th className={s.th}>
                <HeaderWithTooltip
                  label="OK 24h"
                  tooltip="Tarefas concluídas com sucesso nas últimas 24 horas"
                />
              </th>
              <th className={s.th}>
                <HeaderWithTooltip
                  label="Falhas 24h"
                  tooltip="Tarefas que falharam nas últimas 24 horas — falhas repetidas indicam problema no worker ou nos dados"
                />
              </th>
              <th className={s.th}></th>
            </tr>
          </thead>
          <tbody>
            {queues.map((q) => (
              <tr key={q.name} className={s.trHover}>
                <td className={s.td}>
                  <span className={s.mono}>{q.name}</span>
                  {q.dynamic && (
                    <Tooltip label="Fila dedicada de um worker GPU on-premise (roteamento por tenant)">
                      <Badge variant="accent" className={s.mono}>on-premise</Badge>
                    </Tooltip>
                  )}
                </td>
                <td className={s.td}>
                  {q.depth > 0 ? <Badge variant="warning">{q.depth}</Badge> : q.depth}
                </td>
                <td className={s.td}>{fmtAge(q.oldest_age_s)}</td>
                <td className={s.td}>{q.ok_24h}</td>
                <td className={s.td}>
                  {q.fail_24h > 0 ? <Badge variant="danger">{q.fail_24h}</Badge> : q.fail_24h}
                </td>
                <td className={s.td}>
                  <button
                    className={s.btnGhost}
                    style={{ fontSize: 11, padding: '3px 8px' }}
                    onClick={() => setSelectedQueue(selectedQueue === q.name ? null : q.name)}
                    aria-pressed={selectedQueue === q.name}
                  >
                    {selectedQueue === q.name ? 'Ocultar gráfico' : 'Ver gráfico'}
                  </button>
                </td>
              </tr>
            ))}
            {queues.length === 0 && (
              <tr>
                <td colSpan={6} className={s.td} style={{ textAlign: 'center' }}>
                  <span className={s.muted}>
                    {summary.celery.details ?? 'Nenhuma fila visível'}
                  </span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Drill-down por fila */}
      {selectedQueue && (
        <TimeseriesChart
          key={`queue-${selectedQueue}-${windowSel}`}
          title={`Profundidade da fila ${selectedQueue}`}
          tooltip="Tarefas aguardando nesta fila ao longo do tempo — platôs altos significam represamento"
          scope="celery"
          metric="queue_depth"
          window={windowSel}
          refreshMs={refreshMs}
          queue={selectedQueue}
          color={chartColors.warning}
        />
      )}
    </div>
  )
}
