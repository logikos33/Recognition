import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const container = style({
  padding: 24,
  maxWidth: 1100,
  margin: '0 auto',
})

export const header = style({
  marginBottom: 24,
})

export const moduleLabel = style({
  fontSize: 11,
  color: vars.color.textMuted,
  textTransform: 'uppercase',
  letterSpacing: 1,
})

export const moduleTitle = style({
  fontSize: 22,
  fontWeight: 700,
  color: vars.color.textPrimary,
  margin: '4px 0 0',
})

export const moduleDesc = style({
  fontSize: 13,
  color: vars.color.textMuted,
  margin: '4px 0 0',
})

export const statsGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
  gap: 12,
  marginBottom: 24,
})

export const statCard = style({
  background: vars.color.bgSurface,
  borderRadius: 10,
  padding: '16px 20px',
  display: 'flex',
  alignItems: 'center',
  gap: 12,
})

export const statIconWrap = style({
  fontSize: 24,
  width: 40,
  height: 40,
  borderRadius: 8,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
})

export const statLabel = style({
  fontSize: 11,
  color: vars.color.textMuted,
})

export const statValue = style({
  fontSize: 20,
  fontWeight: 700,
  color: vars.color.textPrimary,
})

export const classesPanel = style({
  background: vars.color.bgSurface,
  borderRadius: 12,
  padding: 24,
  marginBottom: 24,
})

export const classesPanelTitle = style({
  fontSize: 14,
  fontWeight: 600,
  color: vars.color.textPrimary,
  marginBottom: 16,
})

export const classesGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
  gap: 8,
})

export const classChip = style({
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: '8px 12px',
  borderRadius: 8,
})

export const classDot = style({
  width: 10,
  height: 10,
  borderRadius: vars.radius.full,
  flexShrink: 0,
})

export const className = style({
  fontSize: 12,
  color: vars.color.textPrimary,
  fontWeight: 500,
})

export const quickLinksGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
  gap: 12,
})

export const quickLinkBtn = style({
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: 10,
  padding: '16px 20px',
  cursor: 'pointer',
  textAlign: 'left',
  transition: `border-color ${vars.animation.duration} ${vars.animation.easing}`,
  ':hover': {
    borderColor: vars.color.borderStrong,
  },
})

export const quickLinkIcon = style({
  fontSize: 22,
  marginBottom: 6,
})

export const quickLinkLabel = style({
  fontSize: 13,
  fontWeight: 600,
  color: vars.color.textPrimary,
})
