/**
 * AnnotationPage styles — dark theme using design tokens.
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../styles/theme.css'

export const page = style({
  padding: vars.space.xl,
})

export const pageTitle = style({
  color: vars.color.textPrimary,
  fontSize: '22px',
  fontWeight: 700,
  marginBottom: vars.space.md,
  marginTop: 0,
})

export const emptyState = style({
  padding: '40px',
  textAlign: 'center',
  color: vars.color.textMuted,
  background: vars.color.bgCard,
  borderRadius: vars.radius.lg,
  border: `1px solid ${vars.color.borderDefault}`,
})

export const emptyText = style({
  margin: 0,
})

export const emptyTextSub = style({
  fontSize: '13px',
  margin: '8px 0 0',
})

export const grid = style({
  display: 'grid',
  gap: '12px',
})

export const videoCard = style({
  padding: vars.space.md,
  background: vars.color.bgCard,
  borderRadius: vars.radius.lg,
  border: `1px solid ${vars.color.borderDefault}`,
  cursor: 'pointer',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  transition: `background ${vars.animation.duration} ${vars.animation.easing}`,
  ':hover': {
    background: vars.color.bgHover,
  },
})

export const videoName = style({
  color: vars.color.textPrimary,
  fontWeight: 600,
})

export const videoFrameCount = style({
  color: vars.color.textMuted,
  fontSize: '13px',
  marginLeft: '12px',
})
