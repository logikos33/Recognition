import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const pageWrapper = style({
  padding: 24,
  maxWidth: 1200,
  margin: '0 auto',
})

export const pageHeader = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: 24,
})

export const pageTitle = style({
  fontSize: 22,
  fontWeight: 700,
  color: vars.color.textPrimary,
  margin: 0,
})

export const refreshBtn = style({
  padding: `6px 14px`,
  borderRadius: 8,
  border: `1px solid ${vars.color.borderDefault}`,
  background: vars.color.bgCard,
  cursor: 'pointer',
  fontSize: 13,
  color: vars.color.textSecondary,
  transition: `background ${vars.animation.duration} ${vars.animation.easing}`,
  ':hover': { background: vars.color.bgHover },
})

export const errorBanner = style({
  padding: '12px 16px',
  background: vars.color.dangerMuted,
  border: `1px solid ${vars.color.danger}`,
  borderRadius: 8,
  marginBottom: 20,
  color: vars.color.danger,
  fontSize: 13,
})

export const section = style({
  marginBottom: 36,
})

export const sectionTitle = style({
  fontSize: 16,
  fontWeight: 600,
  color: vars.color.textSecondary,
  marginBottom: 14,
})

export const emptyText = style({
  color: vars.color.textMuted,
  padding: '20px 0',
  fontSize: 14,
})

export const grid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
  gap: 16,
})

export const availableGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
  gap: 12,
})

export const cameraCard = style({
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: 12,
  padding: 16,
  background: vars.color.bgCard,
})

export const cameraCardHeader = style({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  marginBottom: 10,
})

export const cameraName = style({
  fontWeight: 600,
  fontSize: 14,
  color: vars.color.textPrimary,
})

export const badgeRow = style({
  display: 'flex',
  gap: 6,
})

export const badgeSetup = style({
  fontSize: 11,
  padding: '2px 8px',
  borderRadius: 20,
  background: vars.color.warningMuted,
  color: vars.color.warning,
  fontWeight: 600,
})

export const badgeActive = style({
  fontSize: 11,
  padding: '2px 8px',
  borderRadius: 20,
  background: vars.color.successMuted,
  color: vars.color.success,
  fontWeight: 600,
})

export const metaText = style({
  fontSize: 13,
  color: vars.color.textMuted,
  marginBottom: 10,
})

export const editStack = style({
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  marginBottom: 10,
})

export const editInput = style({
  padding: '7px 10px',
  borderRadius: 6,
  border: `1px solid ${vars.color.borderDefault}`,
  fontSize: 13,
  background: vars.color.bgSurface,
  color: vars.color.textPrimary,
  ':focus': { borderColor: vars.color.primary },
  outline: 'none',
})

export const editActions = style({
  display: 'flex',
  gap: 8,
})

export const saveBtn = style({
  flex: 1,
  padding: '7px 0',
  borderRadius: 6,
  border: 'none',
  background: vars.color.primary,
  color: vars.color.bgBase,
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 600,
  ':hover': { background: vars.color.primaryLight },
  selectors: { '&:disabled': { opacity: 0.5, cursor: 'not-allowed' } },
})

export const cancelBtn = style({
  padding: '7px 14px',
  borderRadius: 6,
  border: `1px solid ${vars.color.borderDefault}`,
  background: vars.color.bgCard,
  cursor: 'pointer',
  fontSize: 13,
  color: vars.color.textSecondary,
})

export const cardActions = style({
  display: 'flex',
  gap: 8,
})

export const editConfigBtn = style({
  flex: 1,
  padding: '6px 0',
  borderRadius: 6,
  border: `1px solid ${vars.color.borderDefault}`,
  background: vars.color.bgCard,
  cursor: 'pointer',
  fontSize: 12,
  color: vars.color.textSecondary,
  ':hover': { background: vars.color.bgHover },
})

export const removeBtn = style({
  padding: '6px 12px',
  borderRadius: 6,
  border: `1px solid ${vars.color.danger}`,
  background: vars.color.dangerMuted,
  cursor: 'pointer',
  fontSize: 12,
  color: vars.color.danger,
})

export const availableCard = style({
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: 10,
  padding: '14px 16px',
  background: vars.color.bgSurface,
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
})

export const availableName = style({
  fontWeight: 600,
  fontSize: 13,
  color: vars.color.textSecondary,
})

export const addBtn = style({
  padding: '6px 14px',
  borderRadius: 6,
  border: `1px solid ${vars.color.primary}`,
  background: vars.color.primaryAlpha,
  cursor: 'pointer',
  fontSize: 12,
  color: vars.color.primary,
  fontWeight: 600,
  ':hover': { background: vars.color.primaryAlpha },
})

export const loadingText = style({
  padding: 24,
  color: vars.color.textMuted,
})
