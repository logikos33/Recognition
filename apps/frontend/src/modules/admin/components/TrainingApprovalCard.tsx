import { CheckCircle, XCircle } from 'lucide-react'
import * as s from './admin.css'
import type { TrainingApproval } from '../types/admin'

interface Props {
  approval: TrainingApproval
  onApprove?: (id: string) => void
  onReject?: (id: string) => void
}

export function TrainingApprovalCard({ approval, onApprove, onReject }: Props) {
  const m = approval.metrics

  return (
    <div className={s.card}>
      <div className={s.flex} style={{ marginBottom: 8 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600 }}>{approval.job_name ?? approval.training_job_id.slice(0, 8)}</div>
          <div className={s.muted}>{approval.tenant_name} · módulo: {approval.module}</div>
        </div>
        <span className={s.badge} style={{ background: 'rgba(249,115,22,0.15)', color: '#ea580c' }}>Pendente</span>
      </div>

      <div className={s.twoColumn} style={{ fontSize: 12, marginBottom: 12 }}>
        {m.mAP50 !== undefined && <div><span className={s.muted}>mAP50</span> {(m.mAP50 * 100).toFixed(1)}%</div>}
        {m.mAP50_95 !== undefined && <div><span className={s.muted}>mAP50-95</span> {(m.mAP50_95 * 100).toFixed(1)}%</div>}
        {m.dataset_size !== undefined && <div><span className={s.muted}>Dataset</span> {m.dataset_size} imgs</div>}
        {m.epochs !== undefined && <div><span className={s.muted}>Épocas</span> {m.epochs}</div>}
      </div>

      {approval.status === 'pending' && (
        <div className={s.flex}>
          <button className={s.btnSuccess} onClick={() => onApprove?.(approval.id)}>
            <CheckCircle size={14} /> Aprovar
          </button>
          <button className={s.btnDanger} onClick={() => onReject?.(approval.id)}>
            <XCircle size={14} /> Rejeitar
          </button>
        </div>
      )}
    </div>
  )
}
