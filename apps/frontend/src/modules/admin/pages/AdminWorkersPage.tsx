/**
 * AdminWorkersPage — página dedicada de workers GPU on-premise.
 *
 * WS11: a tabela vive em observability/WorkersPanel (compartilhada com a aba
 * Workers do dashboard de Observability), com ConfirmDialog/Toast do kit no
 * lugar de confirm()/alert() nativos.
 */
import { WorkersPanel } from './observability/WorkersPanel'
import * as s from '../components/admin.css'

export function AdminWorkersPage() {
  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Workers On-Premise</div>
          <div className={s.pageSubtitle}>
            Máquinas GPU dos clientes · visão consolidada em Observability → Workers
          </div>
        </div>
      </div>

      <WorkersPanel refreshMs={10_000} />
    </div>
  )
}
