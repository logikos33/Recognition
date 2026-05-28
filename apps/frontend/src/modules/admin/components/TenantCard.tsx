import { Building2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import * as s from './admin.css'
import { WorkerStatusBadge } from './WorkerStatusBadge'
import type { Tenant } from '../types/admin'

export function TenantCard({ tenant }: { tenant: Tenant }) {
  const nav = useNavigate()

  return (
    <div className={s.card} style={{ cursor: 'pointer' }} onClick={() => nav(`/admin/tenants/${tenant.id}`)}>
      <div className={s.flex}>
        <Building2 size={16} />
        <span style={{ fontWeight: 600, flex: 1 }}>{tenant.name}</span>
        {tenant.worker_status && <WorkerStatusBadge status={tenant.worker_status} />}
      </div>
      <div className={s.muted} style={{ marginTop: 6 }}>
        {tenant.slug} · {tenant.plan} · {tenant.contract_cameras} câmeras
      </div>
      {!tenant.is_active && (
        <div className={s.alertBanner.danger} style={{ marginTop: 8, marginBottom: 0 }}>
          Tenant suspenso
        </div>
      )}
    </div>
  )
}
