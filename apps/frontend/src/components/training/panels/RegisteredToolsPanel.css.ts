/**
 * Estilos do RegisteredToolsPanel (task-063) — tokens WS1 + :hover.
 * Card usa bgCard para elevação sobre a sidebar (bgSurface).
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const card = style({
  margin: '0 8px',
  padding: '10px 12px',
  background: vars.color.bgCard,
  borderRadius: '6px',
  border: `1px solid ${vars.color.borderDefault}`,
  transition: `background ${vars.animation.duration}, border-color ${vars.animation.duration}`,
  ':hover': {
    background: vars.color.bgHover,
    borderColor: vars.color.borderStrong,
  },
})

export const actionBtn = style({
  display: 'flex',
  alignItems: 'center',
  gap: '4px',
  padding: '4px 8px',
  background: 'transparent',
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: '4px',
  color: vars.color.primary,
  fontSize: '11px',
  cursor: 'pointer',
  transition: `background ${vars.animation.duration}, border-color ${vars.animation.duration}`,
  ':hover': {
    background: vars.color.bgHover,
    borderColor: vars.color.primary,
  },
})

export const actionBtnDanger = style([actionBtn, {
  color: vars.color.danger,
  ':hover': {
    background: vars.color.dangerMuted,
    borderColor: vars.color.danger,
  },
}])
