import { style } from '@vanilla-extract/css'
import { recipe } from '@vanilla-extract/recipes'
import { vars } from '../../styles/theme.css'

export const overlay = style({
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.65)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
  padding: vars.space.md,
})

export const modal = style({
  background: vars.color.bgCard,
  borderRadius: vars.radius.xl,
  border: `1px solid ${vars.color.borderDefault}`,
  width: '100%',
  maxWidth: '520px',
  maxHeight: '90vh',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
})

export const modalHeader = style({
  padding: `${vars.space.md} ${vars.space.lg}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  flexShrink: 0,
})

export const modalTitle = style({
  fontWeight: 700,
  fontSize: '16px',
  color: vars.color.textPrimary,
})

export const modalSubtitle = style({
  color: vars.color.textMuted,
  fontSize: '12px',
  marginTop: '2px',
})

export const closeBtn = style({
  background: 'none',
  border: 'none',
  color: vars.color.textMuted,
  cursor: 'pointer',
  fontSize: '22px',
  lineHeight: 1,
  padding: '0 4px',
  ':hover': { color: vars.color.textPrimary },
})

export const progressBar = style({
  display: 'flex',
  padding: `${vars.space.md} ${vars.space.lg} 0`,
  gap: '6px',
  flexShrink: 0,
})

export const progressSegment = recipe({
  base: {
    flex: 1,
    height: '3px',
    borderRadius: '2px',
    transition: `background ${vars.animation.duration}`,
  },
  variants: {
    active: {
      true: { background: vars.color.primary },
      false: { background: vars.color.borderDefault },
    },
  },
})

export const content = style({
  padding: vars.space.lg,
  overflowY: 'auto',
  flex: 1,
})

export const footer = style({
  padding: `${vars.space.md} ${vars.space.lg}`,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  background: vars.color.bgSurface,
  display: 'flex',
  justifyContent: 'space-between',
  flexShrink: 0,
})

// ─── Step styles ────────────────────────────────────────

export const stepStack = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.md,
})

export const hint = style({
  padding: '10px 14px',
  background: 'rgba(59, 130, 246, 0.12)',
  borderRadius: vars.radius.md,
  fontSize: '12px',
  color: '#93c5fd',
})

export const grid2 = style({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: vars.space.md,
})

export const manufacturerGrid = style({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: '10px',
})

export const manufacturerBtn = recipe({
  base: {
    padding: '12px 14px',
    borderRadius: vars.radius.md,
    cursor: 'pointer',
    textAlign: 'left',
    fontWeight: 600,
    fontSize: '14px',
    color: vars.color.textPrimary,
    transition: `border-color ${vars.animation.duration}, background ${vars.animation.duration}`,
    fontFamily: vars.font.sans,
  },
  variants: {
    selected: {
      true: {
        border: `2px solid ${vars.color.primary}`,
        background: 'rgba(139, 92, 246, 0.12)',
      },
      false: {
        border: `2px solid ${vars.color.borderDefault}`,
        background: vars.color.bgSurface,
        ':hover': { borderColor: vars.color.borderStrong },
      },
    },
  },
})

export const helpText = style({
  color: vars.color.textDim,
  fontSize: '11px',
  marginTop: '4px',
})

export const urlPreview = style({
  padding: vars.space.md,
  background: vars.color.bgSurface,
  borderRadius: vars.radius.md,
})

export const urlPreviewLabel = style({
  color: vars.color.textMuted,
  fontSize: '11px',
  fontWeight: 700,
  marginBottom: '6px',
  letterSpacing: '0.04em',
})

export const urlPreviewCode = style({
  color: vars.color.accent,
  fontSize: '11px',
  wordBreak: 'break-all',
  fontFamily: vars.font.mono,
})

export const testCenterBox = style({
  textAlign: 'center',
  padding: '24px 0',
})

export const testCenterText = style({
  color: vars.color.textSecondary,
  marginBottom: vars.space.lg,
  fontSize: '14px',
})

export const resultBanner = recipe({
  base: {
    padding: '12px 16px',
    borderRadius: vars.radius.md,
    border: '1px solid',
  },
  variants: {
    success: {
      true: {
        background: vars.color.successMuted,
        borderColor: 'rgba(16, 185, 129, 0.3)',
      },
      false: {
        background: vars.color.dangerMuted,
        borderColor: 'rgba(239, 68, 68, 0.3)',
      },
    },
  },
})

export const resultTitle = recipe({
  base: { fontWeight: 700, fontSize: '14px' },
  variants: {
    success: {
      true: { color: '#86efac' },
      false: { color: '#fca5a5' },
    },
  },
})

export const resultErrorMsg = style({
  color: '#fca5a5',
  fontSize: '12px',
  marginTop: '4px',
})

export const resultSuggestion = style({
  color: vars.color.textSecondary,
  fontSize: '12px',
  marginTop: '6px',
})

export const diagnosticBox = style({
  background: vars.color.bgSurface,
  borderRadius: vars.radius.md,
  padding: '10px 14px',
})

export const diagnosticTitle = style({
  color: vars.color.textMuted,
  fontSize: '11px',
  fontWeight: 700,
  marginBottom: '8px',
  letterSpacing: '0.04em',
})

export const diagnosticRow = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  fontSize: '12px',
})

export const diagnosticLabel = recipe({
  base: { flex: 1 },
  variants: {
    isError: {
      true: { color: '#fca5a5' },
      false: { color: vars.color.textSecondary },
    },
  },
})

export const diagnosticDetail = style({
  color: vars.color.textDim,
  fontSize: '11px',
})

export const failureActions = style({
  display: 'flex',
  gap: vars.space.sm,
})

export const errorText = style({
  color: vars.color.danger,
  fontSize: '11px',
  marginTop: '6px',
})

export const diagnosticGap = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
})
