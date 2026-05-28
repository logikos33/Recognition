import { Wifi, WifiOff, Server } from 'lucide-react'
import * as s from './admin.css'
import type { WorkerStatus } from '../types/admin'

const icons: Record<WorkerStatus, React.ReactNode> = {
  onpremise: <Server size={11} />,
  railway:   <Wifi size={11} />,
  offline:   <WifiOff size={11} />,
}

const labels: Record<WorkerStatus, string> = {
  onpremise: 'On-premise',
  railway:   'Railway',
  offline:   'Offline',
}

export function WorkerStatusBadge({ status }: { status: WorkerStatus }) {
  return (
    <span className={s.workerBadge[status]}>
      {icons[status]}
      {labels[status]}
    </span>
  )
}
