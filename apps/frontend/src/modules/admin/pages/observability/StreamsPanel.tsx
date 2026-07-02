/**
 * StreamsPanel — aba Streams do dashboard de observability (WS11).
 *
 * Consome GET /admin/observability/streams: status de TODAS as câmeras
 * ativas em UMA request agregada (mata o N+1 da antiga StreamHealthPage,
 * que fazia um GET /cameras/<id>/stream/status por câmera a cada 15s).
 */
import { useCallback, useState } from 'react'
import { usePolling } from '../../../../hooks/usePolling'
import { Badge } from '../../../../components/ui/Badge/Badge'
import { Banner } from '../../../../components/ui/Banner/Banner'
import { Skeleton } from '../../../../components/ui/Skeleton/Skeleton'
import { Tooltip } from '../../../../components/ui/Tooltip/Tooltip'
import { DataTable } from '../../../../components/ui/DataTable/DataTable'
import type { Column } from '../../../../components/ui/DataTable/DataTable'
import { adminService } from '../../services/adminService'
import * as s from '../../components/admin.css'
import type { ObsCeleryWorker, ObsStreamCamera, ObsStreamsAggregate } from '../../types/admin'

const cameraColumns: Column<ObsStreamCamera & Record<string, unknown>>[] = [
  { key: 'name', header: 'Câmera', sortable: true },
  {
    key: 'tenant_name',
    header: 'Tenant',
    sortable: true,
    render: (row) => row.tenant_name ?? '—',
  },
  {
    key: 'location',
    header: 'Local',
    render: (row) => row.location ?? '—',
  },
  {
    key: 'streaming',
    header: 'Stream',
    render: (row) =>
      row.streaming == null ? (
        <Badge variant="neutral">—</Badge>
      ) : row.streaming ? (
        <Badge variant="success">Transmitindo</Badge>
      ) : (
        <Badge variant="neutral">Parada</Badge>
      ),
  },
  {
    key: 'ttl_seconds',
    header: 'TTL',
    render: (row) => (row.ttl_seconds != null ? `${row.ttl_seconds}s` : '—'),
  },
]

const workerColumns: Column<ObsCeleryWorker & Record<string, unknown>>[] = [
  {
    key: 'worker_id',
    header: 'Worker',
    render: (row) => <span className={s.mono}>{row.worker_id}</span>,
  },
  {
    key: 'status',
    header: 'Status',
    render: (row) =>
      row.status === 'online' ? (
        <Badge variant="success">online</Badge>
      ) : (
        <Badge variant="neutral">{row.status}</Badge>
      ),
  },
  { key: 'active_tasks', header: 'Tarefas ativas', sortable: true },
  { key: 'pool', header: 'Pool' },
]

interface StreamsPanelProps {
  refreshMs: number
}

export function StreamsPanel({ refreshMs }: StreamsPanelProps) {
  const [data, setData] = useState<ObsStreamsAggregate | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setData(await adminService.getObservabilityStreams())
      setError(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar streams')
      throw e
    }
  }, [])

  usePolling(load, refreshMs > 0 ? refreshMs : 30_000, { enabled: refreshMs > 0 })

  if (!data) {
    if (refreshMs <= 0) {
      return (
        <Banner variant="info">
          Atualização pausada — selecione um intervalo de atualização para
          carregar o status dos streams.
        </Banner>
      )
    }
    return <Skeleton variant="rect" height={240} />
  }

  return (
    <div>
      {error && <div className={s.alertBanner.danger}>{error}</div>}

      {/* Resumo */}
      <div className={s.card} style={{ marginBottom: 16 }}>
        <div className={s.flex} style={{ flexWrap: 'wrap', gap: 12 }}>
          <Tooltip label="Serviço que converte o vídeo das câmeras (RTSP) para o navegador (HLS) — offline significa nenhum stream ao vivo">
            <span>
              <Badge variant={data.gateway_online ? 'success' : 'danger'}>
                Gateway {data.gateway_online ? 'online' : 'offline'}
              </Badge>
            </span>
          </Tooltip>
          <Tooltip label="Câmeras com stream HLS ativo agora sobre o total de câmeras ativas cadastradas">
            <span className={s.muted}>
              {data.cameras_streaming} de {data.cameras_total} câmeras transmitindo
            </span>
          </Tooltip>
        </div>
      </div>

      {/* Câmeras */}
      <div className={s.card} style={{ marginBottom: 16 }}>
        <div className={s.cardTitle}>Câmeras</div>
        <DataTable
          columns={cameraColumns}
          data={data.cameras as (ObsStreamCamera & Record<string, unknown>)[]}
          rowKey={(row) => row.id}
          emptyTitle="Nenhuma câmera ativa"
          emptyDescription="Cadastre e ative câmeras para acompanhar o status dos streams aqui"
        />
      </div>

      {/* Workers Celery */}
      <div className={s.card}>
        <div className={s.flex} style={{ marginBottom: 8 }}>
          <span className={s.cardTitle} style={{ marginBottom: 0 }}>Workers de processamento (Celery)</span>
          <Tooltip label="Processos que executam as tarefas das filas (inferência, extração, treino) — consultado a cada 30s com cache">
            <Badge variant="neutral">{data.celery_workers.length}</Badge>
          </Tooltip>
        </div>
        <DataTable
          columns={workerColumns}
          data={data.celery_workers as (ObsCeleryWorker & Record<string, unknown>)[]}
          rowKey={(row) => row.worker_id}
          emptyTitle="Nenhum worker detectado"
          emptyDescription="O serviço worker pode estar iniciando ou fora do ar"
        />
      </div>
    </div>
  )
}
