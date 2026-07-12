/**
 * WidgetShell — invólucro sortable (@dnd-kit) de cada widget BI.
 *
 * Drag restrito à alça no header (listeners só no botão GripVertical) para
 * não conflitar com tooltips/hover do recharts. Container SEMPRE via Panel
 * do UI kit — zero container fora do kit.
 */
import type { CSSProperties, ReactNode } from 'react'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { EyeOff, GripVertical, Info } from 'lucide-react'
import { Button } from '../../ui/Button/Button'
import { EmptyState } from '../../ui/EmptyState/EmptyState'
import { Panel } from '../../ui/Panel/Panel'
import { Skeleton } from '../../ui/Skeleton/Skeleton'
import { Tooltip } from '../../ui/Tooltip/Tooltip'
import {
  dragHandle,
  errorText,
  iconButton,
  infoIcon,
  shellWrap,
  stateBox,
  widgetActions,
  widgetBody,
  widgetTitleRow,
} from './widgets.css'

interface WidgetShellProps {
  id: string
  title: string
  /** Texto do tooltip (i) explicando a métrica */
  info?: string
  onHide: () => void
  className?: string
  children: ReactNode
}

export function WidgetShell({ id, title, info, onHide, className, children }: WidgetShellProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id })

  const style: CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
    zIndex: isDragging ? 10 : undefined,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`${shellWrap}${className ? ` ${className}` : ''}`}
    >
      <Panel
        variant="card"
        title={
          <span className={widgetTitleRow}>
            {title}
            {info && (
              <Tooltip label={info}>
                <span className={infoIcon} aria-label={`Sobre: ${title}`}>
                  <Info size={13} />
                </span>
              </Tooltip>
            )}
          </span>
        }
        actions={
          <span className={widgetActions}>
            <Tooltip label="Arrastar para reordenar">
              <button
                type="button"
                className={dragHandle}
                aria-label={`Mover widget ${title}`}
                {...attributes}
                {...listeners}
              >
                <GripVertical size={14} />
              </button>
            </Tooltip>
            <Tooltip label="Ocultar widget">
              <button
                type="button"
                className={iconButton}
                aria-label={`Ocultar widget ${title}`}
                onClick={onHide}
              >
                <EyeOff size={14} />
              </button>
            </Tooltip>
          </span>
        }
      >
        <div className={widgetBody}>{children}</div>
      </Panel>
    </div>
  )
}

/* ── Estados padronizados (contrato de operabilidade) ───────────── */

interface WidgetContentProps {
  loading: boolean
  error: boolean
  empty: boolean
  onRetry: () => void
  children: ReactNode
}

/** Loading → Skeleton; erro → mensagem + "Tentar novamente"; vazio → EmptyState. */
export function WidgetContent({ loading, error, empty, onRetry, children }: WidgetContentProps) {
  if (loading) {
    return (
      <div className={stateBox}>
        <Skeleton variant="rect" width="100%" height={160} />
      </div>
    )
  }
  if (error) {
    return (
      <div className={stateBox} role="alert">
        <span className={errorText}>Não foi possível carregar os dados.</span>
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Tentar novamente
        </Button>
      </div>
    )
  }
  if (empty) {
    return (
      <EmptyState
        title="Sem dados no período"
        description="Nenhum evento registrado no intervalo selecionado."
      />
    )
  }
  return <>{children}</>
}
