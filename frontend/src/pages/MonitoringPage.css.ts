import { style } from '@vanilla-extract/css'
import { recipe } from '@vanilla-extract/recipes'
import { vars } from '../styles/theme.css'

export const page = style({ padding: vars.space.lg })

export const pageHeader = style({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: vars.space.md,
})

export const pageTitle = style({
  color: vars.color.textPrimary,
  fontSize: '22px',
  fontWeight: 700,
  margin: 0,
})

export const wsStatus = recipe({
  base: { fontSize: '12px', fontWeight: 600 },
  variants: {
    connected: {
      true: { color: vars.color.success },
      false: { color: vars.color.danger },
    },
  },
})

export const layout = style({
  display: 'grid',
  gridTemplateColumns: '200px 1fr',
  gap: vars.space.md,
})

export const sidebarLabel = style({
  color: vars.color.textMuted,
  fontSize: '11px',
  fontWeight: 700,
  letterSpacing: '0.06em',
  marginBottom: vars.space.sm,
})

export const emptyText = style({
  color: vars.color.textDim,
  fontSize: '13px',
})

export const cameraBtn = recipe({
  base: {
    width: '100%',
    padding: '10px 12px',
    marginBottom: '6px',
    borderRadius: vars.radius.md,
    border: 'none',
    cursor: 'pointer',
    textAlign: 'left',
    fontSize: '13px',
    fontFamily: vars.font.sans,
    fontWeight: 500,
    transition: `background ${vars.animation.duration}`,
  },
  variants: {
    active: {
      true: { background: vars.color.primaryDark, color: '#fff' },
      false: { background: vars.color.bgCard, color: vars.color.textSecondary,
        ':hover': { background: vars.color.bgHover } },
    },
  },
})

export const detectionCount = style({
  marginLeft: '6px',
  fontSize: '11px',
  color: vars.color.warning,
})

export const alertsLabel = style({
  color: vars.color.danger,
  fontSize: '11px',
  fontWeight: 700,
  letterSpacing: '0.06em',
  marginBottom: vars.space.sm,
  marginTop: vars.space.md,
})

export const alertItem = style({
  padding: '8px 10px',
  background: vars.color.bgCard,
  borderRadius: vars.radius.sm,
  border: `1px solid rgba(220, 38, 38, 0.3)`,
  marginBottom: '6px',
})

export const alertText = style({
  color: '#fca5a5',
  fontSize: '11px',
  margin: 0,
})

export const playerWrapper = style({
  position: 'relative',
  display: 'inline-block',
})

export const noStream = style({
  width: '640px',
  height: '360px',
  background: vars.color.bgCard,
  borderRadius: vars.radius.lg,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: vars.color.textDim,
  fontSize: '14px',
})
