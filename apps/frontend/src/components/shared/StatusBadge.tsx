import { Badge, statusToBadgeVariant } from '../ui/Badge/Badge'

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={statusToBadgeVariant(status)}>
      {status}
    </Badge>
  )
}
