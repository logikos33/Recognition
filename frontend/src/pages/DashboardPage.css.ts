import { style } from '@vanilla-extract/css'
import { vars } from '../styles/theme.css'

export const page = style({ padding: vars.space.xl })

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

export const statsGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
  gap: '14px',
})

export const statCard = style({
  padding: vars.space.lg,
  background: vars.color.bgCard,
  borderRadius: vars.radius.lg,
  border: `1px solid ${vars.color.borderDefault}`,
})

export const statLabel = style({
  color: vars.color.textSecondary,
  fontSize: '12px',
  marginBottom: '6px',
})

export const statValue = style({
  fontSize: '32px',
  fontWeight: 800,
})

export const statSub = style({
  color: vars.color.textMuted,
  fontSize: '12px',
  marginTop: '4px',
})

export const section = style({
  marginTop: vars.space.lg,
  padding: vars.space.lg,
  background: vars.color.bgCard,
  borderRadius: vars.radius.lg,
  border: `1px solid ${vars.color.borderDefault}`,
})

export const sectionTitle = style({
  color: vars.color.textPrimary,
  marginBottom: vars.space.md,
  fontSize: '15px',
  fontWeight: 600,
  margin: '0 0 12px',
})

export const chartRow = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
})

export const chartLabel = style({
  color: vars.color.textSecondary,
  fontSize: '13px',
  minWidth: '120px',
})

export const chartBarBg = style({
  flex: 1,
  height: '8px',
  background: vars.color.bgElevated,
  borderRadius: vars.radius.full,
  overflow: 'hidden',
})

export const chartBarFill = style({
  height: '100%',
  background: vars.color.purple500,
  borderRadius: vars.radius.full,
})

export const chartCount = style({
  color: vars.color.textMuted,
  fontSize: '12px',
  minWidth: '40px',
  textAlign: 'right',
})

export const statusRow = style({
  display: 'flex',
  justifyContent: 'space-between',
  color: vars.color.textSecondary,
  fontSize: '13px',
})
