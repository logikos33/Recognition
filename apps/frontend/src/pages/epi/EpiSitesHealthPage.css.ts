import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const container = style({
  display: 'flex',
  flexDirection: 'column',
  padding: vars.space.lg,
  gap: vars.space.lg,
  flex: 1,
  overflowY: 'auto',
  overflowX: 'hidden',
})

export const pageHeader = style({
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  flexShrink: 0,
})

export const pageTitle = style({
  fontSize: '18px',
  fontWeight: 700,
  color: vars.color.textPrimary,
  margin: 0,
  lineHeight: 1.3,
})

export const pageSubtitle = style({
  fontSize: '13px',
  color: vars.color.textMuted,
  marginTop: '2px',
})

/* ── Overview cards row ────────────────────────────────────────── */

export const overviewRow = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(152px, 1fr))',
  gap: vars.space.sm,
  flexShrink: 0,
})

export const overviewCard = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.xs,
  padding: vars.space.md,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.lg,
})

export const overviewCardLabel = style({
  fontSize: '10px',
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: vars.color.textMuted,
})

export const overviewCardValue = style({
  fontFamily: vars.font.mono,
  fontSize: '28px',
  fontWeight: 700,
  lineHeight: 1,
  color: vars.color.textPrimary,
})

export const overviewCardValueSuccess = style({
  fontFamily: vars.font.mono,
  fontSize: '28px',
  fontWeight: 700,
  lineHeight: 1,
  color: vars.color.success,
})

export const overviewCardValueWarning = style({
  fontFamily: vars.font.mono,
  fontSize: '28px',
  fontWeight: 700,
  lineHeight: 1,
  color: vars.color.warning,
})

export const overviewCardValueDanger = style({
  fontFamily: vars.font.mono,
  fontSize: '28px',
  fontWeight: 700,
  lineHeight: 1,
  color: vars.color.danger,
})

export const overviewCardSub = style({
  fontSize: '11px',
  color: vars.color.textDim,
})

/* ── Split layout ──────────────────────────────────────────────── */

export const mainContent = style({
  display: 'flex',
  gap: vars.space.md,
  flex: 1,
  minHeight: '320px',
  overflow: 'hidden',
})

export const tableSection = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.lg,
  overflow: 'hidden',
  minWidth: 0,
})

export const tableSectionHeader = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  flexShrink: 0,
})

export const tableSectionTitle = style({
  fontSize: '12px',
  fontWeight: 700,
  color: vars.color.textSecondary,
  letterSpacing: '0.05em',
  textTransform: 'uppercase',
})

export const tableWrapper = style({
  overflowY: 'auto',
  flex: 1,
})

export const table = style({
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '13px',
})

export const th = style({
  textAlign: 'left',
  padding: `${vars.space.xs} ${vars.space.md}`,
  fontSize: '10px',
  fontWeight: 700,
  color: vars.color.textDim,
  letterSpacing: '0.07em',
  textTransform: 'uppercase',
  borderBottom: `1px solid ${vars.color.borderDefault}`,
  background: vars.color.bgSurface,
  position: 'sticky',
  top: 0,
  zIndex: 1,
})

export const td = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  color: vars.color.textSecondary,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  verticalAlign: 'middle',
})

export const tableRow = style({
  cursor: 'pointer',
  outline: 'none',
  ':hover': { background: vars.color.bgHover },
  ':focus-visible': {
    background: vars.color.primaryAlpha,
    outline: `2px solid ${vars.color.primary}`,
    outlineOffset: '-2px',
  },
})

export const tableRowSelected = style({
  background: vars.color.primaryAlpha,
})

export const siteName = style({
  fontWeight: 600,
  color: vars.color.textPrimary,
})

export const siteIdText = style({
  fontSize: '11px',
  color: vars.color.textDim,
  fontFamily: vars.font.mono,
  marginTop: '1px',
})

export const fpsValue = style({
  fontFamily: vars.font.mono,
  fontSize: '13px',
  fontWeight: 600,
  color: vars.color.textPrimary,
})

export const camerasCell = style({
  fontFamily: vars.font.mono,
  fontSize: '13px',
})

/* ── Detail panel ──────────────────────────────────────────────── */

export const detailPanel = style({
  width: '360px',
  flexShrink: 0,
  display: 'flex',
  flexDirection: 'column',
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.lg,
  overflow: 'hidden',
})

export const detailHeader = style({
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  padding: vars.space.md,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  flexShrink: 0,
  gap: vars.space.sm,
})

export const detailTitle = style({
  fontSize: '15px',
  fontWeight: 700,
  color: vars.color.textPrimary,
  margin: 0,
  flex: 1,
  minWidth: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const detailCloseBtn = style({
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  color: vars.color.textMuted,
  padding: '4px',
  borderRadius: vars.radius.sm,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
  ':hover': { color: vars.color.textPrimary, background: vars.color.bgHover },
})

export const detailBody = style({
  flex: 1,
  overflowY: 'auto',
  padding: vars.space.md,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.md,
})

export const summaryGrid = style({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: vars.space.sm,
})

export const summaryMetric = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
  padding: vars.space.sm,
  background: vars.color.bgSurface,
  borderRadius: vars.radius.md,
})

export const summaryMetricLabel = style({
  fontSize: '10px',
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: vars.color.textMuted,
})

export const summaryMetricValue = style({
  fontFamily: vars.font.mono,
  fontSize: '20px',
  fontWeight: 700,
  color: vars.color.textPrimary,
  lineHeight: 1,
})

export const summaryMetricValueSm = style({
  fontFamily: vars.font.mono,
  fontSize: '13px',
  fontWeight: 600,
  color: vars.color.textPrimary,
})

export const chartSectionTitle = style({
  fontSize: '11px',
  fontWeight: 700,
  letterSpacing: '0.05em',
  textTransform: 'uppercase',
  color: vars.color.textMuted,
  marginBottom: vars.space.xs,
})

/* ── Loading / error / empty states ───────────────────────────── */

export const centeredState = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: vars.space.md,
  padding: vars.space.xl,
  color: vars.color.textDim,
  fontSize: '14px',
  textAlign: 'center',
})

export const errorText = style({
  color: vars.color.danger,
})

export const errorBanner = style({
  fontSize: '13px',
  color: vars.color.danger,
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: vars.color.dangerMuted,
  borderRadius: vars.radius.md,
  border: `1px solid ${vars.color.danger}`,
  flexShrink: 0,
})

export const retryBtn = style({
  padding: `${vars.space.xs} ${vars.space.md}`,
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  color: vars.color.textSecondary,
  cursor: 'pointer',
  fontSize: '13px',
  ':hover': {
    background: vars.color.bgHover,
    borderColor: vars.color.borderStrong,
  },
})
