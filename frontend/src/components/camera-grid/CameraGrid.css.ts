import { style, keyframes } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const container = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  background: '#000000',
  position: 'relative',
  overflow: 'hidden',
})

export const grid = style({
  flex: 1,
  display: 'grid',
  gap: '2px',
  padding: '2px',
  minHeight: 0,
  gridAutoFlow: 'dense',
})

export const cellBase = style({
  position: 'relative',
  overflow: 'hidden',
  background: '#0a0a0a',
  border: '1px solid rgba(255,255,255,0.05)',
  borderRadius: '2px',
  display: 'flex',
  flexDirection: 'column',
  aspectRatio: '16 / 9',
  transition: `border-color 200ms ease`,
})

export const cellExpanded = style({
  position: 'absolute',
  inset: 0,
  zIndex: 10,
  borderRadius: 0,
  aspectRatio: 'auto',
})

const violationPulse = keyframes({
  '0%, 100%': { borderColor: 'rgba(239, 68, 68, 0.6)' },
  '50%': { borderColor: 'rgba(239, 68, 68, 0.15)' },
})

export const cellAlert = style({
  animation: `${violationPulse} 1.5s ease-in-out infinite`,
  borderWidth: '2px',
})

export const cellDragOver = style({
  borderColor: `${vars.color.borderStrong} !important`,
  borderWidth: '2px',
  boxShadow: `inset 0 0 20px rgba(139, 92, 246, 0.15)`,
})

export const cellDragging = style({
  opacity: 0.4,
})

export const cellHeader = style({
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '4px 8px',
  background: 'linear-gradient(180deg, rgba(0,0,0,0.7) 0%, transparent 100%)',
  zIndex: 2,
  pointerEvents: 'none',
})

export const cellName = style({
  fontSize: '11px',
  fontWeight: 600,
  color: 'rgba(255,255,255,0.9)',
  fontFamily: vars.font.mono,
  textShadow: '0 1px 2px rgba(0,0,0,0.8)',
})

const livePulse = keyframes({
  '0%, 100%': { opacity: 1 },
  '50%': { opacity: 0.5 },
})

export const liveBadge = style({
  display: 'flex',
  alignItems: 'center',
  gap: '3px',
  fontSize: '9px',
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: '#22c55e',
  pointerEvents: 'none',
})

export const liveDot = style({
  width: '5px',
  height: '5px',
  borderRadius: '50%',
  background: '#22c55e',
  animation: `${livePulse} 2s ease-in-out infinite`,
})

export const alertBadge = style([liveBadge, {
  color: '#ef4444',
}])

export const alertDot = style([liveDot, {
  background: '#ef4444',
}])

export const cellFooter = style({
  position: 'absolute',
  bottom: 0,
  left: 0,
  right: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '4px 8px',
  background: 'linear-gradient(0deg, rgba(0,0,0,0.7) 0%, transparent 100%)',
  zIndex: 2,
  pointerEvents: 'none',
})

export const cellLocation = style({
  fontSize: '10px',
  color: 'rgba(255,255,255,0.5)',
})

export const cellTime = style({
  fontSize: '10px',
  color: 'rgba(255,255,255,0.5)',
  fontFamily: vars.font.mono,
})

export const playerWrap = style({
  position: 'absolute',
  inset: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
})

/* Placeholder cell (empty / add camera) */
export const placeholder = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '8px',
  border: '1px dashed rgba(255,255,255,0.1)',
  borderRadius: '2px',
  cursor: 'pointer',
  transition: 'border-color 200ms, background 200ms',
  background: 'transparent',
  color: 'rgba(255,255,255,0.2)',
  ':hover': {
    borderColor: 'rgba(139, 92, 246, 0.4)',
    background: 'rgba(139, 92, 246, 0.05)',
    color: 'rgba(139, 92, 246, 0.6)',
  },
})

export const placeholderIcon = style({
  fontSize: '24px',
})

export const placeholderText = style({
  fontSize: '11px',
  fontWeight: 500,
})

/* Toolbar */
export const toolbar = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: `${vars.space.xs} ${vars.space.md}`,
  background: vars.color.bgSurface,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  flexShrink: 0,
  flexWrap: 'wrap',
})

export const toolbarGroup = style({
  display: 'flex',
  alignItems: 'center',
  gap: '4px',
})

export const toolbarBtn = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '4px',
  padding: '4px 10px',
  fontSize: '12px',
  fontWeight: 500,
  color: vars.color.textSecondary,
  background: 'transparent',
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.sm,
  cursor: 'pointer',
  transition: `background ${vars.animation.duration}, color ${vars.animation.duration}, border-color ${vars.animation.duration}`,
  ':hover': {
    background: vars.color.bgHover,
    color: vars.color.textPrimary,
    borderColor: vars.color.borderDefault,
  },
})

export const toolbarBtnActive = style([toolbarBtn, {
  background: vars.color.primaryDark,
  color: '#fff',
  borderColor: vars.color.primaryDark,
  ':hover': {
    background: vars.color.primary,
    borderColor: vars.color.primary,
    color: '#fff',
  },
}])

export const toolbarSpacer = style({
  flex: 1,
})

export const presetName = style({
  fontSize: '11px',
  color: vars.color.textDim,
  fontFamily: vars.font.mono,
})

/* Context menu */
export const contextMenu = style({
  position: 'fixed',
  zIndex: 100,
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  padding: '4px',
  minWidth: '160px',
  boxShadow: vars.shadow.lg,
})

export const contextMenuItem = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  width: '100%',
  padding: '6px 10px',
  fontSize: '12px',
  color: vars.color.textSecondary,
  background: 'transparent',
  border: 'none',
  borderRadius: vars.radius.sm,
  cursor: 'pointer',
  textAlign: 'left',
  ':hover': {
    background: vars.color.bgHover,
    color: vars.color.textPrimary,
  },
})

export const contextMenuDanger = style([contextMenuItem, {
  color: vars.color.danger,
  ':hover': {
    background: vars.color.dangerMuted,
    color: vars.color.danger,
  },
}])

/* Save preset modal */
export const modalOverlay = style({
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.7)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 200,
})

export const modalBox = style({
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.lg,
  padding: vars.space.lg,
  width: '360px',
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.md,
})

export const modalTitle = style({
  fontSize: '16px',
  fontWeight: 700,
  color: vars.color.textPrimary,
})

export const modalInput = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  color: vars.color.textPrimary,
  fontSize: '14px',
  outline: 'none',
  ':focus': {
    borderColor: vars.color.primary,
  },
})

export const modalActions = style({
  display: 'flex',
  justifyContent: 'flex-end',
  gap: vars.space.sm,
})

export const modalBtnPrimary = style({
  padding: '6px 16px',
  fontSize: '13px',
  fontWeight: 600,
  background: vars.color.primaryDark,
  color: '#fff',
  border: 'none',
  borderRadius: vars.radius.md,
  cursor: 'pointer',
  ':hover': {
    background: vars.color.primary,
  },
  selectors: {
    '&:disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },
})

export const modalBtnSecondary = style({
  padding: '6px 16px',
  fontSize: '13px',
  fontWeight: 600,
  background: 'transparent',
  color: vars.color.textSecondary,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  cursor: 'pointer',
  ':hover': {
    borderColor: vars.color.borderStrong,
    color: vars.color.textPrimary,
  },
})

/* Grid panel (hamburger sidebar inside container) */
export const panelOverlay = style({
  position: 'absolute',
  inset: 0,
  background: 'rgba(0,0,0,0.4)',
  zIndex: 50,
})

export const panel = style({
  position: 'absolute',
  top: 0,
  left: 0,
  bottom: 0,
  width: '280px',
  background: vars.color.bgElevated,
  borderRight: `1px solid ${vars.color.borderDefault}`,
  zIndex: 51,
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  transition: 'transform 200ms ease',
})

export const panelHeader = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: `${vars.space.sm} ${vars.space.md}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  flexShrink: 0,
})

export const panelTitle = style({
  fontSize: '13px',
  fontWeight: 700,
  color: vars.color.textPrimary,
  letterSpacing: '0.02em',
})

export const panelBody = style({
  flex: 1,
  overflowY: 'auto',
  padding: vars.space.sm,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.md,
})

export const panelSection = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
})

export const panelSectionTitle = style({
  fontSize: '10px',
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  color: vars.color.textMuted,
  padding: `2px ${vars.space.sm}`,
})

export const panelSearchInput = style({
  padding: `6px ${vars.space.sm}`,
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.sm,
  color: vars.color.textPrimary,
  fontSize: '12px',
  outline: 'none',
  width: '100%',
  ':focus': {
    borderColor: vars.color.primary,
  },
  '::placeholder': {
    color: vars.color.textDim,
  },
})

export const panelCameraItem = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: `6px ${vars.space.sm}`,
  fontSize: '12px',
  color: vars.color.textSecondary,
  background: 'transparent',
  border: 'none',
  borderRadius: vars.radius.sm,
  cursor: 'pointer',
  textAlign: 'left',
  width: '100%',
  ':hover': {
    background: vars.color.bgHover,
    color: vars.color.textPrimary,
  },
})

export const panelCameraDot = style({
  width: '6px',
  height: '6px',
  borderRadius: '50%',
  flexShrink: 0,
})

export const panelCameraName = style({
  flex: 1,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const panelCameraLocation = style({
  fontSize: '10px',
  color: vars.color.textDim,
  flexShrink: 0,
})

export const panelAddBtn = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: `8px ${vars.space.sm}`,
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.primaryLight,
  background: 'transparent',
  border: `1px dashed ${vars.color.primaryDark}`,
  borderRadius: vars.radius.sm,
  cursor: 'pointer',
  width: '100%',
  ':hover': {
    background: 'rgba(139, 92, 246, 0.1)',
  },
})

export const panelPresetGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(3, 1fr)',
  gap: '4px',
})

export const panelPresetBtn = style({
  padding: '6px',
  fontSize: '11px',
  fontWeight: 600,
  color: vars.color.textSecondary,
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.sm,
  cursor: 'pointer',
  textAlign: 'center',
  ':hover': {
    borderColor: vars.color.primary,
    color: vars.color.textPrimary,
  },
})

export const panelPresetBtnActive = style([panelPresetBtn, {
  background: vars.color.primaryDark,
  color: '#fff',
  borderColor: vars.color.primaryDark,
}])

export const panelCustomPreset = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: `4px ${vars.space.sm}`,
  fontSize: '12px',
  color: vars.color.textSecondary,
  cursor: 'pointer',
  borderRadius: vars.radius.sm,
  ':hover': {
    background: vars.color.bgHover,
  },
})

export const hamburgerBtn = style({
  position: 'absolute',
  top: '6px',
  left: '6px',
  zIndex: 20,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '32px',
  height: '32px',
  background: 'rgba(0,0,0,0.6)',
  border: `1px solid rgba(255,255,255,0.1)`,
  borderRadius: vars.radius.sm,
  color: 'rgba(255,255,255,0.7)',
  cursor: 'pointer',
  backdropFilter: 'blur(4px)',
  transition: 'background 200ms, color 200ms',
  ':hover': {
    background: 'rgba(139, 92, 246, 0.3)',
    color: '#fff',
  },
})

/* Camera selector dropdown */
export const cameraSelectorOverlay = style({
  position: 'fixed',
  inset: 0,
  zIndex: 90,
})

export const cameraSelectorDropdown = style({
  position: 'absolute',
  top: '50%',
  left: '50%',
  transform: 'translate(-50%, -50%)',
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  padding: vars.space.sm,
  minWidth: '200px',
  maxHeight: '300px',
  overflowY: 'auto',
  zIndex: 91,
  boxShadow: vars.shadow.lg,
})

export const cameraSelectorItem = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  width: '100%',
  padding: '6px 10px',
  fontSize: '12px',
  color: vars.color.textSecondary,
  background: 'transparent',
  border: 'none',
  borderRadius: vars.radius.sm,
  cursor: 'pointer',
  textAlign: 'left',
  ':hover': {
    background: vars.color.bgHover,
    color: vars.color.textPrimary,
  },
})

export const cameraSelectorTitle = style({
  fontSize: '11px',
  fontWeight: 700,
  letterSpacing: '0.05em',
  textTransform: 'uppercase',
  color: vars.color.textMuted,
  padding: '4px 10px',
})
