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

/* Tabs */
export const tabsList = style({
  display: 'flex',
  gap: '2px',
  borderBottom: `1px solid ${vars.color.borderDefault}`,
  marginBottom: vars.space.lg,
})

export const tabsTrigger = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  fontSize: '13px',
  fontWeight: 600,
  color: vars.color.textMuted,
  background: 'transparent',
  border: 'none',
  borderBottom: '2px solid transparent',
  cursor: 'pointer',
  transition: 'color 200ms, border-color 200ms',
  selectors: {
    '&[data-state="active"]': {
      color: vars.color.textPrimary,
      borderBottomColor: vars.color.purple500,
    },
    '&:hover': {
      color: vars.color.textSecondary,
    },
  },
})

export const tabsContent = style({
  outline: 'none',
})

/* Upload zone */
export const uploadZone = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: vars.space.sm,
  padding: vars.space.xl,
  border: `2px dashed ${vars.color.borderDefault}`,
  borderRadius: vars.radius.lg,
  cursor: 'pointer',
  transition: 'border-color 200ms, background 200ms',
  marginBottom: vars.space.lg,
  ':hover': {
    borderColor: vars.color.purple500,
    background: 'rgba(139, 92, 246, 0.03)',
  },
})

export const uploadZoneActive = style({
  borderColor: vars.color.purple500,
  background: 'rgba(139, 92, 246, 0.06)',
})

export const uploadText = style({
  fontSize: '13px',
  color: vars.color.textMuted,
})

export const uploadProgressTrack = style({
  width: '200px',
  height: '6px',
  background: vars.color.borderDefault,
  borderRadius: vars.radius.sm,
  overflow: 'hidden',
})

export const uploadProgressFill = style({
  height: '100%',
  background: vars.color.purple500,
  borderRadius: vars.radius.sm,
  transition: 'width 200ms',
})

/* Training config panel */
export const configPanel = style({
  padding: vars.space.lg,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.lg,
  marginBottom: vars.space.lg,
})

export const configTitle = style({
  fontSize: '15px',
  fontWeight: 700,
  color: vars.color.textPrimary,
  margin: `0 0 ${vars.space.md}`,
})

export const configGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
  gap: vars.space.md,
})

export const configField = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
})

export const configLabel = style({
  fontSize: '11px',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: vars.color.textMuted,
})

export const configSelect = style({
  padding: `6px ${vars.space.sm}`,
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.sm,
  color: vars.color.textPrimary,
  fontSize: '13px',
  outline: 'none',
  ':focus': {
    borderColor: vars.color.purple500,
  },
})

export const configInput = style({
  padding: `6px ${vars.space.sm}`,
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.sm,
  color: vars.color.textPrimary,
  fontSize: '13px',
  outline: 'none',
  width: '100%',
  ':focus': {
    borderColor: vars.color.purple500,
  },
})

/* Storage bar */
export const storageBar = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  marginBottom: vars.space.lg,
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: vars.color.bgCard,
  borderRadius: vars.radius.lg,
  border: `1px solid ${vars.color.borderDefault}`,
})

export const storageTrack = style({
  flex: 1,
  height: '8px',
  background: vars.color.borderDefault,
  borderRadius: vars.radius.sm,
  overflow: 'hidden',
})

export const storageFill = style({
  height: '100%',
  background: vars.color.purple500,
  borderRadius: vars.radius.sm,
  transition: 'width 300ms',
})

export const storageLabel = style({
  fontSize: '12px',
  color: vars.color.textMuted,
  whiteSpace: 'nowrap',
})

export const storagePlus = style({
  background: 'none',
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.sm,
  color: vars.color.purple500,
  cursor: 'pointer',
  padding: '2px 8px',
  fontSize: '13px',
  fontWeight: 700,
  transition: 'border-color 200ms',
  ':hover': {
    borderColor: vars.color.purple500,
  },
})

/* Frame carousel */
export const carouselWrap = style({
  marginTop: vars.space.sm,
  overflowX: 'auto',
  display: 'flex',
  gap: '4px',
  paddingBottom: '4px',
  scrollbarWidth: 'thin',
})

export const carouselThumb = style({
  flexShrink: 0,
  width: '72px',
  height: '48px',
  borderRadius: '4px',
  objectFit: 'cover',
  border: `1px solid ${vars.color.borderDefault}`,
  cursor: 'pointer',
  transition: 'border-color 200ms, opacity 200ms',
  ':hover': {
    borderColor: vars.color.purple500,
    opacity: 0.8,
  },
})

/* Delete btn inline */
export const deleteBtn = style({
  background: 'none',
  border: 'none',
  color: vars.color.textMuted,
  cursor: 'pointer',
  padding: '4px',
  borderRadius: vars.radius.sm,
  transition: 'color 200ms',
  ':hover': {
    color: '#ef4444',
  },
})
