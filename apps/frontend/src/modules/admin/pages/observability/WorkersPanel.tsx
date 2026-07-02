/**
 * WorkersPanel — tabela de workers GPU on-premise (WS11).
 *
 * Extraído da AdminWorkersPage para viver também como aba do dashboard de
 * observability. Restart preservado, mas com ConfirmDialog + Toast do kit
 * (elimina confirm()/alert() nativos). Polling via usePolling respeitando
 * o seletor global de intervalo (refreshMs=0 ⇒ nenhum request).
 */
import { useCallback, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { usePolling } from '../../../../hooks/usePolling'
import { Banner } from '../../../../components/ui/Banner/Banner'
import { ConfirmDialog } from '../../../../components/ui/ConfirmDialog/ConfirmDialog'
import { Skeleton } from '../../../../components/ui/Skeleton/Skeleton'
import { Tooltip } from '../../../../components/ui/Tooltip/Tooltip'
import { useToast } from '../../../../components/ui/Toast/useToast'
import { WorkerStatusBadge } from '../../components/WorkerStatusBadge'
import { adminService } from '../../services/adminService'
import * as s from '../../components/admin.css'
import type { WorkerInfo } from '../../types/admin'

interface WorkersPanelProps {
  refreshMs?: number
}

export function WorkersPanel({ refreshMs = 10_000 }: WorkersPanelProps) {
  const [workers, setWorkers] = useState<WorkerInfo[]>([])
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmSchema, setConfirmSchema] = useState<string | null>(null)
  const [restarting, setRestarting] = useState(false)
  const toast = useToast()

  const load = useCallback(async () => {
    try {
      const list = await adminService.getWorkers()
      setWorkers(list)
      setError(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar workers')
      throw e
    } finally {
      setLoaded(true)
    }
  }, [])

  usePolling(load, refreshMs > 0 ? refreshMs : 10_000, { enabled: refreshMs > 0 })

  const handleConfirmRestart = async () => {
    if (!confirmSchema) return
    setRestarting(true)
    try {
      const res = await adminService.restartWorker(confirmSchema)
      toast.success('Comando enviado', `Restart solicitado: ${res.command_sent}`)
      setConfirmSchema(null)
    } catch (e: unknown) {
      toast.error(
        'Falha ao reiniciar worker',
        e instanceof Error ? e.message : 'Erro inesperado',
      )
    } finally {
      setRestarting(false)
    }
  }

  if (!loaded) {
    if (refreshMs <= 0) {
      return (
        <Banner variant="info">
          Atualização pausada — selecione um intervalo de atualização para
          carregar os workers.
        </Banner>
      )
    }
    return <Skeleton variant="rect" height={200} />
  }

  return (
    <div>
      {error && <div className={s.alertBanner.danger}>{error}</div>}

      <div className={s.card}>
        <div className={s.flex} style={{ marginBottom: 8 }}>
          <span className={s.cardTitle} style={{ marginBottom: 0 }}>
            Workers On-Premise ({workers.length})
          </span>
          <Tooltip label="Máquinas com GPU instaladas no cliente que processam a inferência localmente — sem heartbeat há 90s, o processamento cai para a nuvem (Railway)">
            <span className={s.muted}>heartbeat a cada 30s</span>
          </Tooltip>
        </div>
        <table className={s.table}>
          <thead>
            <tr>
              <th className={s.th}>Tenant</th>
              <th className={s.th}>Hostname</th>
              <th className={s.th}>GPU</th>
              <th className={s.th}>Status</th>
              <th className={s.th}>GPU%</th>
              <th className={s.th}>VRAM</th>
              <th className={s.th}>FPS</th>
              <th className={s.th}>Câmeras</th>
              <th className={s.th}>Último heartbeat</th>
              <th className={s.th}></th>
            </tr>
          </thead>
          <tbody>
            {workers.map((w) => (
              <tr key={w.id ?? w.tenant_schema} className={s.trHover}>
                <td className={s.td}>
                  <div style={{ fontWeight: 600 }}>{w.tenant_name ?? w.tenant_schema}</div>
                  <div className={s.muted}>{w.tenant_slug}</div>
                </td>
                <td className={s.td}><span className={s.mono}>{w.hostname ?? '—'}</span></td>
                <td className={s.td}><span className={s.muted}>{w.gpu_model ?? '—'}</span></td>
                <td className={s.td}><WorkerStatusBadge status={w.status} /></td>
                <td className={s.td}>
                  {w.live_metrics ? `${w.live_metrics.gpu_pct.toFixed(1)}%` : <span className={s.muted}>—</span>}
                </td>
                <td className={s.td}>
                  {w.live_metrics ? `${w.live_metrics.vram_used_gb.toFixed(1)} GB` : <span className={s.muted}>—</span>}
                </td>
                <td className={s.td}>
                  {w.live_metrics ? w.live_metrics.fps_avg.toFixed(1) : <span className={s.muted}>—</span>}
                </td>
                <td className={s.td}>
                  {w.live_metrics ? w.live_metrics.cameras_active : <span className={s.muted}>—</span>}
                </td>
                <td className={s.td}>
                  <span className={s.muted}>
                    {w.last_heartbeat_at
                      ? new Date(w.last_heartbeat_at).toLocaleTimeString('pt-BR')
                      : '—'}
                  </span>
                </td>
                <td className={s.td}>
                  {w.status === 'onpremise' && (
                    <button
                      className={s.btnGhost}
                      style={{ fontSize: 11, padding: '3px 8px' }}
                      onClick={() => setConfirmSchema(w.tenant_schema)}
                    >
                      <RefreshCw size={11} /> Restart
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {workers.length === 0 && (
              <tr>
                <td colSpan={10} className={s.td} style={{ textAlign: 'center' }}>
                  <span className={s.muted}>Nenhum worker registrado</span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        open={confirmSchema != null}
        onClose={() => setConfirmSchema(null)}
        onConfirm={handleConfirmRestart}
        title="Reiniciar worker"
        description={`Reiniciar o worker on-premise de "${confirmSchema ?? ''}"? A inferência desse tenant cai para a nuvem até o worker voltar.`}
        confirmLabel="Reiniciar"
        variant="danger"
        loading={restarting}
      />
    </div>
  )
}
