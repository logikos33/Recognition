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

export const pageMeta = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
  marginTop: '4px',
})

export const pageCount = style({
  fontSize: '13px',
  color: vars.color.textMuted,
})

export const headerActions = style({
  display: 'flex',
  gap: vars.space.sm,
})

export const emptyState = style({
  padding: '60px 40px',
  textAlign: 'center',
  background: vars.color.bgCard,
  borderRadius: vars.radius.lg,
  border: `1px solid ${vars.color.borderDefault}`,
})

export const emptyTitle = style({
  color: vars.color.textPrimary,
  margin: '0 0 8px',
  fontSize: '18px',
  fontWeight: 600,
})

export const emptyText = style({
  color: vars.color.textMuted,
  margin: '0 0 24px',
  fontSize: '14px',
})

export const grid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
  gap: vars.space.md,
})
