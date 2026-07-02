import { Badge, statusToBadgeVariant } from '../ui/Badge/Badge'
import { statusToLabel } from '../../utils/labels'

/**
 * StatusBadge — badge de status com rótulo humano pt-BR.
 * `title` mantém a chave técnica crua para suporte/debug
 * (e estabilidade de seletores de teste).
 */
export function StatusBadge({ status }: { status: string }) {
  return (
    <span title={status}>
      <Badge variant={statusToBadgeVariant(status)}>
        {statusToLabel(status)}
      </Badge>
    </span>
  )
}
