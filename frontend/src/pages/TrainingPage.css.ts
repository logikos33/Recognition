/**
 * TrainingPage styles — dark theme using design tokens.
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../styles/theme.css'

export const page = style({
  padding: vars.space.xl,
})

export const pageHeader = style({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: vars.space.lg,
})

export const pageTitle = style({
  color: vars.color.textPrimary,
  fontSize: '22px',
  fontWeight: 700,
  margin: 0,
})

export const sectionTitle = style({
  color: vars.color.textSecondary,
  fontSize: '14px',
  fontWeight: 600,
  marginBottom: '12px',
})

export const emptyText = style({
  color: vars.color.textMuted,
})

export const grid = style({
  display: 'grid',
  gap: '10px',
  marginBottom: vars.space.xxl,
})

export const gridModels = style({
  display: 'grid',
  gap: '10px',
})

export const jobCard = style({
  padding: vars.space.md,
  background: vars.color.bgCard,
  borderRadius: vars.radius.lg,
  border: `1px solid ${vars.color.borderDefault}`,
})

export const modelCard = style({
  padding: vars.space.md,
  background: vars.color.bgCard,
  borderRadius: vars.radius.lg,
  border: `1px solid ${vars.color.borderDefault}`,
})

export const modelCardActive = style({
  border: `2px solid ${vars.color.success}`,
})

export const cardRow = style({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
})

export const jobName = style({
  color: vars.color.textPrimary,
  fontWeight: 600,
})

export const jobPreset = style({
  color: vars.color.textMuted,
  fontSize: '13px',
  marginLeft: '8px',
})

export const modelName = style({
  color: vars.color.textPrimary,
  fontWeight: 600,
})

export const progressWrap = style({
  marginTop: '10px',
})

export const progressTrack = style({
  height: '6px',
  background: vars.color.borderDefault,
  borderRadius: vars.radius.sm,
  overflow: 'hidden',
})

export const progressFill = style({
  height: '100%',
  background: vars.color.purple500,
  borderRadius: vars.radius.sm,
  transition: `width ${vars.animation.duration} ${vars.animation.easing}`,
})

export const progressLabel = style({
  color: vars.color.textMuted,
  fontSize: '12px',
  marginTop: '4px',
  display: 'block',
})

export const modelMeta = style({
  color: vars.color.textMuted,
  fontSize: '13px',
  marginTop: '6px',
})
