import { Info } from 'lucide-react'
import { Tooltip } from '../Tooltip/Tooltip'
import { tooltipTitle, tooltipBody } from '../Tooltip/Tooltip.css'
import { infoButton } from './InfoTooltip.css'

interface InfoTooltipProps {
  /** Título opcional em destaque acima do texto. */
  title?: string
  /** Texto explicativo (pt-BR, linguagem leiga). */
  text: string
  side?: 'top' | 'right' | 'bottom' | 'left'
}

/**
 * InfoTooltip — ícone "i" com ajuda contextual (WS2 Onboarding cognitivo).
 *
 * Aparece somente em hover/focus (nunca fixo). Acessível por teclado:
 * o Radix Trigger abre o conteúdo ao receber foco.
 *
 * Uso padrão, ao lado do label do campo:
 *   <label>Épocas <InfoTooltip text="Quantas vezes o modelo revê o dataset..." /></label>
 */
export function InfoTooltip({ title, text, side = 'top' }: InfoTooltipProps) {
  return (
    <Tooltip
      side={side}
      content={
        <span>
          {title && <span className={tooltipTitle}>{title}</span>}
          <span className={tooltipBody}>{text}</span>
        </span>
      }
    >
      <button
        type="button"
        className={infoButton}
        aria-label={`Mais informações: ${title ?? text}`}
        tabIndex={0}
      >
        <Info size={13} aria-hidden="true" />
      </button>
    </Tooltip>
  )
}
