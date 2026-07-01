import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const page = style({ padding: vars.space.xl })

export const pageHeader = style({
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  marginBottom: vars.space.lg,
})

export const pageTitle = style({
  color: vars.color.textPrimary, fontSize: '22px', fontWeight: 700, margin: 0,
})

export const pageSubtitle = style({
  color: vars.color.textMuted, fontSize: '13px', marginTop: '4px',
})

export const filtersCard = style({
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.lg,
  padding: vars.space.lg,
  marginBottom: vars.space.lg,
})

export const filtersGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
  gap: vars.space.md,
  marginBottom: vars.space.md,
})

export const filterLabel = style({
  display: 'block',
  color: vars.color.textMuted,
  fontSize: '11px',
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  marginBottom: '6px',
})

export const filterInput = style({
  width: '100%',
  padding: '8px 10px',
  borderRadius: vars.radius.sm,
  border: `1px solid ${vars.color.borderDefault}`,
  background: vars.color.bgSurface,
  color: vars.color.textPrimary,
  fontSize: '13px',
  fontFamily: vars.font.sans,
  boxSizing: 'border-box',
})

export const filterSelect = style({
  width: '100%',
  padding: '8px 10px',
  borderRadius: vars.radius.sm,
  border: `1px solid ${vars.color.borderDefault}`,
  background: vars.color.bgSurface,
  color: vars.color.textPrimary,
  fontSize: '13px',
  fontFamily: vars.font.sans,
  cursor: 'pointer',
})

export const sliderRow = style({
  display: 'flex', alignItems: 'center', gap: vars.space.sm,
})

export const slider = style({
  flex: 1,
  accentColor: vars.color.primary,
})

export const sliderValue = style({
  color: vars.color.textSecondary,
  fontSize: '13px',
  minWidth: '36px',
  textAlign: 'right',
})

export const filtersActions = style({
  display: 'flex', gap: vars.space.sm, justifyContent: 'flex-end',
})

// Timeline

export const timelineCard = style({
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.lg,
  padding: vars.space.lg,
  marginBottom: vars.space.lg,
})

export const timelineTitle = style({
  color: vars.color.textSecondary,
  fontSize: '12px',
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  marginBottom: vars.space.md,
})

export const timelineBars = style({
  display: 'flex',
  alignItems: 'flex-end',
  gap: '3px',
  height: '60px',
})

export const timelineBar = style({
  flex: 1,
  background: vars.color.primary,
  borderRadius: '2px 2px 0 0',
  minHeight: '4px',
  opacity: 0.75,
  transition: 'opacity 0.15s',
  ':hover': { opacity: 1 },
})

export const timelineEmpty = style({
  color: vars.color.textMuted,
  fontSize: '13px',
  textAlign: 'center',
  padding: '20px 0',
})

// Results grid

export const resultsHeader = style({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: vars.space.md,
})

export const resultsCount = style({
  color: vars.color.textMuted, fontSize: '13px',
})

export const grid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
  gap: vars.space.md,
})

export const evidenceCard = style({
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.lg,
  overflow: 'hidden',
  cursor: 'pointer',
  transition: 'border-color 0.15s',
  ':hover': {
    borderColor: vars.color.primary,
  },
})

export const thumbnailBox = style({
  width: '100%',
  aspectRatio: '16/9',
  background: vars.color.bgSurface,
  position: 'relative',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  overflow: 'hidden',
})

export const thumbnail = style({
  width: '100%',
  height: '100%',
  objectFit: 'cover',
  display: 'block',
})

export const thumbnailPlaceholder = style({
  color: vars.color.textMuted,
  fontSize: '28px',
})

export const cardBody = style({
  padding: '12px',
})

export const cardCamera = style({
  color: vars.color.textPrimary,
  fontSize: '13px',
  fontWeight: 600,
  marginBottom: '4px',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
})

export const cardDate = style({
  color: vars.color.textMuted,
  fontSize: '11px',
  marginBottom: '6px',
})

export const cardTags = style({
  display: 'flex', flexWrap: 'wrap', gap: '4px',
})

export const tagViolation = style({
  background: `${vars.color.danger}22`,
  color: vars.color.danger,
  fontSize: '11px',
  fontWeight: 600,
  padding: '2px 7px',
  borderRadius: '999px',
})

export const tagConf = style({
  background: `${vars.color.textMuted}22`,
  color: vars.color.textSecondary,
  fontSize: '11px',
  padding: '2px 7px',
  borderRadius: '999px',
})

// Pagination

export const pagination = style({
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  marginTop: vars.space.lg,
})

export const paginationText = style({ color: vars.color.textMuted, fontSize: '13px' })

export const paginationControls = style({
  display: 'flex', gap: vars.space.sm, alignItems: 'center',
})

export const pageNum = style({ color: vars.color.textSecondary, fontSize: '13px' })

export const emptyBox = style({
  padding: '48px', textAlign: 'center', color: vars.color.textMuted,
  background: vars.color.bgCard, borderRadius: vars.radius.lg,
  border: `1px solid ${vars.color.borderDefault}`,
})
