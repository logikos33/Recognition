import { style } from '@vanilla-extract/css'
import { vars } from '../styles/theme.css'

export const page = style({
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  overflow: 'hidden',
})

export const pageHeader = style({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: `${vars.space.md} ${vars.space.xl}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  flexShrink: 0,
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

export const splitView = style({
  display: 'flex',
  flex: 1,
  minHeight: 0,
  overflow: 'hidden',
})

export const cameraList = style({
  width: '320px',
  flexShrink: 0,
  borderRight: `1px solid ${vars.color.borderSubtle}`,
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
})

export const cameraListItem = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: `${vars.space.sm} ${vars.space.md}`,
  cursor: 'pointer',
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  transition: 'background 150ms',
  ':hover': {
    background: vars.color.bgHover,
  },
})

export const cameraListItemActive = style([cameraListItem, {
  background: vars.color.bgHover,
  borderLeft: `3px solid ${vars.color.primary}`,
}])

export const listDot = style({
  width: '8px',
  height: '8px',
  borderRadius: '50%',
  flexShrink: 0,
})

export const listName = style({
  flex: 1,
  fontSize: '13px',
  fontWeight: 600,
  color: vars.color.textPrimary,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const listLocation = style({
  fontSize: '11px',
  color: vars.color.textMuted,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  maxWidth: '120px',
})

export const detailPanel = style({
  flex: 1,
  overflowY: 'auto',
  padding: vars.space.lg,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.lg,
})

export const detailEmpty = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  color: vars.color.textMuted,
  fontSize: '14px',
  gap: vars.space.sm,
})

export const previewWrap = style({
  borderRadius: vars.radius.lg,
  overflow: 'hidden',
  background: '#000',
  aspectRatio: '16 / 9',
  maxHeight: '360px',
})

export const detailFields = style({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: vars.space.md,
})

export const fieldGroup = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
})

export const fieldLabel = style({
  fontSize: '11px',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: vars.color.textMuted,
})

export const fieldValue = style({
  fontSize: '13px',
  color: vars.color.textPrimary,
  padding: `6px ${vars.space.sm}`,
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.sm,
})

export const detailActions = style({
  display: 'flex',
  gap: vars.space.sm,
  flexWrap: 'wrap',
})

export const logList = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
})

export const logItem = style({
  fontSize: '12px',
  color: vars.color.textSecondary,
  padding: `4px ${vars.space.sm}`,
  borderRadius: vars.radius.sm,
  background: vars.color.bgSurface,
})

export const sectionTitle = style({
  fontSize: '13px',
  fontWeight: 700,
  color: vars.color.textPrimary,
  margin: 0,
})

export const rtspTip = style({
  fontSize: '12px',
  color: vars.color.textMuted,
  padding: vars.space.sm,
  background: 'rgba(139, 92, 246, 0.05)',
  border: `1px solid rgba(139, 92, 246, 0.15)`,
  borderRadius: vars.radius.md,
  lineHeight: '1.5',
})

/* Legacy exports for backward compat */
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
