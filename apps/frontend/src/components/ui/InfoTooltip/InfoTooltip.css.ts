import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

/**
 * Botão do ícone "i" — invisível como botão, só o glifo.
 * Cursor 'help' comunica ajuda contextual; foco por teclado abre o tooltip
 * (comportamento nativo do Radix Trigger).
 */
export const infoButton = style({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  verticalAlign: 'middle',
  background: 'none',
  border: 'none',
  padding: 0,
  marginLeft: vars.space.xs,
  cursor: 'help',
  color: vars.color.textMuted,
  lineHeight: 1,
  selectors: {
    '&:hover': { color: vars.color.textSecondary },
    '&:focus-visible': {
      color: vars.color.textSecondary,
      outline: `1px solid ${vars.color.borderDefault}`,
      outlineOffset: 2,
      borderRadius: vars.radius.sm,
    },
  },
})
