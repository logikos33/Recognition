/**
 * Estilos do TrainingModeLayout (task-063) — tokens WS1 + hover nas linhas
 * da tabela resumo (inline styles não suportam :hover).
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const summaryRow = style({
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  transition: `background ${vars.animation.duration}`,
  ':hover': {
    background: vars.color.bgHover,
  },
})
