/**
 * Estilos do OperationCatalogPanel (task-063) — hover via :hover CSS
 * (antes era onMouseEnter com hex hardcoded '#181818').
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const typeCard = style({
  display: 'flex',
  alignItems: 'flex-start',
  gap: '10px',
  padding: '10px 12px',
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: '6px',
  color: 'inherit',
  cursor: 'pointer',
  textAlign: 'left',
  width: '100%',
  transition: `background ${vars.animation.duration}, border-color ${vars.animation.duration}`,
  ':hover': {
    background: vars.color.bgHover,
    borderColor: vars.color.borderStrong,
  },
})
