import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const card = style({
  background: vars.color.bgCard,
  borderRadius: vars.radius.lg,
  border: `1px solid ${vars.color.borderDefault}`,
  overflow: 'hidden',
})

export const cardHeader = style({
  padding: `14px ${vars.space.md} ${vars.space.sm}`,
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
})

export const cameraName = style({
  color: vars.color.textPrimary,
  fontWeight: 600,
  fontSize: '15px',
})

export const cameraLocation = style({
  color: vars.color.textMuted,
  fontSize: '12px',
  marginTop: '2px',
})

export const cardInfo = style({
  padding: `0 ${vars.space.md} ${vars.space.sm}`,
})

export const rtspUrl = style({
  color: vars.color.textDim,
  fontSize: '11px',
  fontFamily: vars.font.mono,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const metaText = style({
  color: vars.color.textDim,
  fontSize: '11px',
  marginTop: '2px',
})

export const errorBanner = style({
  margin: `0 ${vars.space.md} ${vars.space.sm}`,
  padding: `6px 10px`,
  background: vars.color.dangerMuted,
  borderRadius: vars.radius.sm,
  color: '#fca5a5',
  fontSize: '11px',
})

export const testBannerOk = style({
  margin: `0 ${vars.space.md} ${vars.space.sm}`,
  padding: `6px 10px`,
  borderRadius: vars.radius.sm,
  fontSize: '11px',
  background: vars.color.successMuted,
  color: '#86efac',
})

export const testBannerError = style({
  margin: `0 ${vars.space.md} ${vars.space.sm}`,
  padding: `6px 10px`,
  borderRadius: vars.radius.sm,
  fontSize: '11px',
  background: vars.color.dangerMuted,
  color: '#fca5a5',
})

export const testBannerLoading = style({
  margin: `0 ${vars.space.md} ${vars.space.sm}`,
  padding: `6px 10px`,
  borderRadius: vars.radius.sm,
  fontSize: '11px',
  background: vars.color.bgElevated,
  color: vars.color.textSecondary,
})

export const actions = style({
  padding: `${vars.space.sm} ${vars.space.md} 14px`,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  display: 'flex',
  gap: vars.space.sm,
  alignItems: 'center',
  flexWrap: 'wrap',
})

export const spacer = style({ flex: 1 })

export const deleteConfirm = style({
  padding: `${vars.space.md}`,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  background: vars.color.dangerMuted,
})

export const deleteConfirmText = style({
  color: '#fca5a5',
  fontSize: '12px',
  marginBottom: vars.space.sm,
})

export const deleteConfirmActions = style({
  display: 'flex',
  gap: vars.space.sm,
})
