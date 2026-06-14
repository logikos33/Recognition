import { RefreshCw } from 'lucide-react'
import { useWorkerMonitor } from '../hooks/useWorkerMonitor'
import { WorkerStatusBadge } from '../components/WorkerStatusBadge'
import { adminService } from '../services/adminService'
import * as s from '../components/admin.css'

export function AdminWorkersPage() {
  const { workers, loading, error } = useWorkerMonitor({ intervalMs: 10_000 })

  const handleRestart = async (schema: string) => {
    if (!confirm(`Reiniciar worker de ${schema}?`)) return
    try {
      const res = await adminService.restartWorker(schema)
      alert(`Comando enviado: ${res.command_sent}`)
    } catch (e: unknown) { alert(e instanceof Error ? e.message : 'Erro') }
  }

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Workers On-Premise</div>
          <div className={s.pageSubtitle}>Atualizado a cada 10s · {workers.length} registrados</div>
        </div>
      </div>

      {error && <div className={s.alertBanner.danger}>{error}</div>}

      <div className={s.card}>
        {loading && workers.length === 0 ? <div className={s.muted}>Carregando...</div> : (
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
                <tr key={w.id} className={s.trHover}>
                  <td className={s.td}>
                    <div style={{ fontWeight: 600 }}>{w.tenant_name ?? w.tenant_schema}</div>
                    <div className={s.muted}>{w.tenant_slug}</div>
                  </td>
                  <td className={s.td}><span className={s.mono}>{w.hostname ?? '—'}</span></td>
                  <td className={s.td}><span className={s.muted}>{w.gpu_model ?? '—'}</span></td>
                  <td className={s.td}><WorkerStatusBadge status={w.status} /></td>
                  <td className={s.td}>{w.live_metrics ? `${w.live_metrics.gpu_pct.toFixed(1)}%` : <span className={s.muted}>—</span>}</td>
                  <td className={s.td}>{w.live_metrics ? `${w.live_metrics.vram_used_gb.toFixed(1)} GB` : <span className={s.muted}>—</span>}</td>
                  <td className={s.td}>{w.live_metrics ? w.live_metrics.fps_avg.toFixed(1) : <span className={s.muted}>—</span>}</td>
                  <td className={s.td}>{w.live_metrics ? w.live_metrics.cameras_active : <span className={s.muted}>—</span>}</td>
                  <td className={s.td}><span className={s.muted}>{w.last_heartbeat_at ? new Date(w.last_heartbeat_at).toLocaleTimeString('pt-BR') : '—'}</span></td>
                  <td className={s.td}>
                    {w.status === 'onpremise' && (
                      <button className={s.btnGhost} style={{ fontSize: 11, padding: '3px 8px' }} onClick={() => handleRestart(w.tenant_schema)}>
                        <RefreshCw size={11} /> Restart
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {workers.length === 0 && (
                <tr><td colSpan={10} className={s.td} style={{ textAlign: 'center' }}><span className={s.muted}>Nenhum worker registrado</span></td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
