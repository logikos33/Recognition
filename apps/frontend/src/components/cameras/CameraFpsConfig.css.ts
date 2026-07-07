/**
 * Estilos do CameraFpsConfig (task-063) — tokens WS1, com estados :hover
 * que estilos inline não suportam.
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const container = style({
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: '8px',
  padding: '12px 14px',
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
})

export const title = style({
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  fontWeight: 600,
  fontSize: '13px',
  color: vars.color.textPrimary,
})

export const sectionLabel = style({
  fontSize: '11px',
  color: vars.color.textMuted,
  marginBottom: '5px',
})

export const optionBtn = style({
  padding: '4px 10px',
  borderRadius: '5px',
  border: `1px solid ${vars.color.borderDefault}`,
  background: 'transparent',
  color: vars.color.textSecondary,
  fontSize: '12px',
  fontWeight: 400,
  cursor: 'pointer',
  transition: `background ${vars.animation.duration}, border-color ${vars.animation.duration}, color ${vars.animation.duration}`,
  selectors: {
    '&:hover:not(:disabled)': {
      background: vars.color.bgHover,
      borderColor: vars.color.borderStrong,
      color: vars.color.textPrimary,
    },
    '&:disabled': {
      cursor: 'not-allowed',
      opacity: 0.55,
    },
  },
})

export const optionBtnActive = style([optionBtn, {
  border: `1px solid ${vars.color.primary}`,
  background: vars.color.primaryAlpha,
  color: vars.color.primaryLight,
  fontWeight: 600,
  selectors: {
    '&:hover:not(:disabled)': {
      background: vars.color.primaryAlpha,
      borderColor: vars.color.primaryLight,
      color: vars.color.primaryLight,
    },
  },
}])

export const healthBox = style({
  background: vars.color.bgSurface,
  borderRadius: '6px',
  padding: '8px 10px',
  fontSize: '11px',
  color: vars.color.textSecondary,
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
})

export const refreshBtn = style({
  display: 'flex',
  alignItems: 'center',
  gap: '4px',
  background: 'transparent',
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: '5px',
  color: vars.color.textSecondary,
  fontSize: '10px',
  padding: '2px 8px',
  cursor: 'pointer',
  transition: `background ${vars.animation.duration}, border-color ${vars.animation.duration}`,
  selectors: {
    '&:hover:not(:disabled)': {
      background: vars.color.bgHover,
      borderColor: vars.color.borderStrong,
      color: vars.color.textPrimary,
    },
    '&:disabled': {
      cursor: 'wait',
    },
  },
})
