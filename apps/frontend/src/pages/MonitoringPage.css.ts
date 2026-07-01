/**
 * MonitoringPage.css.ts — estilos do VMS ao vivo (deliverable h).
 */
import { style, keyframes } from '@vanilla-extract/css'
import { vars } from '../styles/theme.css'

// ---------------------------------------------------------------------------
// Page shell
// ---------------------------------------------------------------------------
export const page = style({
  display: 'flex',
  flexDirection: 'column',
  flex: 1,
  minHeight: 0,
  background: vars.color.bgBase,
  overflow: 'hidden',
})

// ---------------------------------------------------------------------------
// Toolbar
// ---------------------------------------------------------------------------
export const toolbar = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: vars.color.bgSurface,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  flexShrink: 0,
  flexWrap: 'wrap',
})

export const moduleTabList = style({
  display: 'flex',
  alignItems: 'center',
  gap: '2px',
})

export const moduleTab = style({
  padding: '5px 12px',
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.textMuted,
  background: 'transparent',
  border: `1px solid transparent`,
  borderRadius: vars.radius.sm,
  cursor: 'pointer',
  transition: `all ${vars.animation.duration} ${vars.animation.easing}`,
  ':hover': {
    color: vars.color.textPrimary,
    background: vars.color.bgHover,
  },
})

export const moduleTabActive = style([moduleTab, {
  color: vars.color.textPrimary,
  background: vars.color.bgElevated,
  borderColor: vars.color.borderDefault,
}])

export const spacer = style({ flex: 1 })

const livePulse = keyframes({
  '0%, 100%': { opacity: 1 },
  '50%': { opacity: 0.4 },
})

export const statusBadge = style({
  display: 'flex',
  alignItems: 'center',
  gap: '5px',
  fontSize: '11px',
  fontWeight: 600,
  color: vars.color.textMuted,
})

export const statusDotOnline = style({
  width: '6px',
  height: '6px',
  borderRadius: '50%',
  background: vars.color.success,
  animation: `${livePulse} 2s ease-in-out infinite`,
  flexShrink: 0,
})

export const statusDotOffline = style({
  width: '6px',
  height: '6px',
  borderRadius: '50%',
  background: vars.color.textDim,
  flexShrink: 0,
})

export const overlayToggle = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '5px',
  padding: '5px 12px',
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.textSecondary,
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.sm,
  cursor: 'pointer',
  transition: `all ${vars.animation.duration}`,
  ':hover': {
    color: vars.color.textPrimary,
    borderColor: vars.color.borderStrong,
  },
})

export const overlayToggleActive = style([overlayToggle, {
  color: vars.color.primary,
  borderColor: vars.color.primary,
  background: vars.color.primaryAlpha,
  ':hover': {
    color: vars.color.primaryLight,
    borderColor: vars.color.primaryLight,
  },
}])

// ---------------------------------------------------------------------------
// Camera grid
// ---------------------------------------------------------------------------
export const gridContainer = style({
  flex: 1,
  overflowY: 'auto',
  padding: vars.space.md,
})

export const cameraGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
  gap: vars.space.md,
})

const alertPulse = keyframes({
  '0%, 100%': { borderColor: 'rgba(239,68,68,0.7)' }, // allow: canvas semantic danger
  '50%': { borderColor: 'rgba(239,68,68,0.2)' },       // allow: canvas semantic danger
})

export const cameraCard = style({
  position: 'relative',
  background: '#0a0a0a', // allow: VMS dark camera cell bg — no semantic token
  borderRadius: vars.radius.md,
  overflow: 'hidden',
  border: `1px solid rgba(255,255,255,0.06)`, // allow: VMS dark surface border
  cursor: 'pointer',
  transition: `border-color ${vars.animation.duration} ${vars.animation.easing}, box-shadow ${vars.animation.duration}`,
  ':hover': {
    borderColor: vars.color.borderStrong,
    boxShadow: vars.shadow.md,
  },
  ':focus-visible': {
    outline: `2px solid ${vars.color.primary}`,
    outlineOffset: '2px',
  },
})

export const cameraCardAlert = style([cameraCard, {
  animation: `${alertPulse} 1.5s ease-in-out infinite`,
  borderWidth: '2px',
}])

export const cardAspect = style({
  position: 'relative',
  width: '100%',
  paddingTop: '56.25%', // 16:9 ratio
})

export const cardInner = style({
  position: 'absolute',
  inset: 0,
})

export const cardPlaceholder = style({
  position: 'absolute',
  inset: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: 'rgba(255,255,255,0.12)', // allow: VMS dark placeholder text
  fontSize: '11px',
  fontFamily: vars.font.mono,
  background: '#0a0a0a', // allow: VMS dark camera cell bg
})

export const cardHeader = style({
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '6px 8px',
  background: 'linear-gradient(180deg, rgba(0,0,0,0.8) 0%, transparent 100%)', // allow: VMS overlay gradient
  zIndex: 3,
  pointerEvents: 'none',
})

export const cardName = style({
  fontSize: '11px',
  fontWeight: 700,
  color: 'rgba(255,255,255,0.9)', // allow: VMS overlay text on dark bg
  fontFamily: vars.font.mono,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  maxWidth: '72%',
})

export const cardAlertLabel = style({
  fontSize: '9px',
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: '#ef4444',  // allow: canvas semantic danger
  pointerEvents: 'none',
})

export const cardFooter = style({
  position: 'absolute',
  bottom: 0,
  left: 0,
  right: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '6px 8px',
  background: 'linear-gradient(0deg, rgba(0,0,0,0.8) 0%, transparent 100%)', // allow: VMS overlay gradient
  zIndex: 3,
  pointerEvents: 'none',
})

export const cardLocation = style({
  fontSize: '10px',
  color: 'rgba(255,255,255,0.4)', // allow: VMS secondary text on dark bg
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const cardModuleBadge = style({
  fontSize: '9px',
  fontWeight: 700,
  letterSpacing: '0.07em',
  textTransform: 'uppercase',
  color: 'rgba(255,255,255,0.5)',       // allow: VMS overlay text
  background: 'rgba(255,255,255,0.08)', // allow: VMS overlay bg tint
  borderRadius: '3px',
  padding: '2px 5px',
  flexShrink: 0,
})

// ---------------------------------------------------------------------------
// Drawer content
// ---------------------------------------------------------------------------
export const drawerFeed = style({
  position: 'relative',
  background: '#000', // allow: video player bg — always black
  aspectRatio: '16 / 9',
  flexShrink: 0,
  width: '100%',
  overflow: 'hidden',
})

export const drawerTabList = style({
  display: 'flex',
  padding: `${vars.space.sm} ${vars.space.md} 0`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  flexShrink: 0,
})

export const drawerTab = style({
  padding: '7px 14px',
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.textMuted,
  background: 'transparent',
  border: 'none',
  borderBottom: '2px solid transparent',
  cursor: 'pointer',
  transition: `color ${vars.animation.duration}, border-color ${vars.animation.duration}`,
  ':hover': {
    color: vars.color.textPrimary,
  },
})

export const drawerTabActive = style([drawerTab, {
  color: vars.color.primary,
  borderBottomColor: vars.color.primary,
}])

export const drawerScrollBody = style({
  flex: 1,
  overflowY: 'auto',
  minHeight: 0,
})

export const drawerInfoGrid = style({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: vars.space.md,
  padding: vars.space.lg,
})

export const drawerInfoItem = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
})

export const drawerInfoLabel = style({
  fontSize: '10px',
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  color: vars.color.textMuted,
})

export const drawerInfoValue = style({
  fontSize: '13px',
  fontWeight: 600,
  color: vars.color.textPrimary,
})

// ---------------------------------------------------------------------------
// Live logs
// ---------------------------------------------------------------------------
export const logsList = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  padding: vars.space.md,
  fontFamily: vars.font.mono,
})

export const logEntry = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '3px',
  padding: '6px 10px',
  background: vars.color.bgCard,
  borderRadius: vars.radius.sm,
  borderLeft: `2px solid ${vars.color.borderDefault}`,
})

export const logEntryAlert = style([logEntry, {
  borderLeftColor: vars.color.danger,
  background: vars.color.dangerMuted,
}])

export const logTimestamp = style({
  fontSize: '10px',
  color: vars.color.textDim,
})

export const logDetectionRow = style({
  fontSize: '11px',
  color: vars.color.textSecondary,
})

export const emptyState = style({
  textAlign: 'center',
  padding: `${vars.space.xxl} ${vars.space.lg}`,
  color: vars.color.textMuted,
  fontSize: '13px',
})
