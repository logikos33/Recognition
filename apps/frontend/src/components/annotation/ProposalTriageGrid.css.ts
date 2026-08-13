/**
 * ProposalTriageGrid styles — grade de triagem em massa de propostas de
 * IA (propagação/pré-anotação). Muitos tiles por tela, teclado-first.
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const root = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
})

// ── barra de filtros ─────────────────────────────────────────────────────

export const filterBar = style({
  position: 'sticky',
  top: 0,
  zIndex: 10,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
  padding: `${vars.space.sm} 0`,
  background: vars.color.bgBase,
})

export const filterRow = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  flexWrap: 'wrap',
})

export const filterLabel = style({
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.textMuted,
  flexShrink: 0,
})

export const chip = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '4px 12px',
  borderRadius: vars.radius.full,
  fontSize: '12px',
  fontWeight: 600,
  cursor: 'pointer',
  border: `1px solid ${vars.color.borderDefault}`,
  background: 'transparent',
  color: vars.color.textSecondary,
  selectors: {
    '&:hover': { background: vars.color.bgHover },
  },
})

export const chipActive = style({
  background: vars.color.primaryDark,
  color: vars.color.textOnPrimary,
  borderColor: vars.color.primaryDark,
})

export const chipCount = style({
  fontSize: '11px',
  fontFamily: vars.font.mono,
  opacity: 0.75,
})

export const jobChip = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '4px 10px',
  borderRadius: vars.radius.full,
  fontSize: '12px',
  fontWeight: 600,
  background: vars.color.primaryAlpha,
  color: vars.color.primary,
  border: `1px solid ${vars.color.primary}`,
})

export const jobChipClose = style({
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  color: 'inherit',
  display: 'inline-flex',
  padding: 0,
})

export const sortButton = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '4px',
  padding: '4px 10px',
  borderRadius: vars.radius.md,
  fontSize: '12px',
  fontWeight: 600,
  cursor: 'pointer',
  border: `1px solid ${vars.color.borderDefault}`,
  background: 'transparent',
  color: vars.color.textSecondary,
  selectors: {
    '&:hover': { background: vars.color.bgHover },
  },
})

export const sortButtonActive = style({
  borderColor: vars.color.primary,
  color: vars.color.primary,
})

export const confidenceInput = style({
  width: '64px',
  padding: '4px 6px',
  fontSize: '12px',
  fontFamily: vars.font.mono,
  borderRadius: vars.radius.sm,
  border: `1px solid ${vars.color.borderDefault}`,
  background: vars.color.bgCard,
  color: vars.color.textPrimary,
})

export const resultLine = style({
  fontSize: '13px',
  fontFamily: vars.font.mono,
  color: vars.color.textSecondary,
})

// ── barra de ações em lote ───────────────────────────────────────────────

export const bulkBar = style({
  display: 'flex',
  alignItems: 'center',
  flexWrap: 'wrap',
  gap: vars.space.sm,
  padding: vars.space.sm,
  borderRadius: vars.radius.md,
  border: `1px solid ${vars.color.borderDefault}`,
  background: vars.color.bgCard,
})

export const bulkGroup = style({
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
})

export const confirmBar = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: vars.space.sm,
  borderRadius: vars.radius.md,
  border: `1px solid ${vars.color.danger}`,
  background: vars.color.dangerMuted,
})

export const confirmText = style({
  fontSize: '13px',
  fontWeight: 600,
  color: vars.color.textPrimary,
})

// ── grade ─────────────────────────────────────────────────────────────────

export const grid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
  gap: '10px',
})

export const tile = style({
  position: 'relative',
  borderRadius: vars.radius.md,
  overflow: 'hidden',
  border: `1px solid ${vars.color.borderDefault}`,
  background: vars.color.bgCard,
  cursor: 'pointer',
  selectors: {
    '&:hover': { borderColor: vars.color.borderStrong },
  },
})

export const tileSelected = style({
  borderColor: vars.color.primary,
  boxShadow: `0 0 0 2px ${vars.color.primaryAlpha}`,
})

export const tileFocused = style({
  boxShadow: `0 0 0 2px ${vars.color.primary}`,
})

export const tileCorrectMode = style({
  boxShadow: `0 0 0 2px ${vars.color.warning}`,
})

export const tileImageWrap = style({
  position: 'relative',
  width: '100%',
  overflow: 'hidden',
  background: vars.color.bgBase,
})

export const tileImage = style({
  width: '100%',
  height: '100%',
  objectFit: 'cover',
  display: 'block',
})

export const tileImagePlaceholder = style({
  width: '100%',
  height: '100%',
  minHeight: '120px',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '4px',
  fontSize: '10px',
  color: vars.color.textMuted,
  background: vars.color.bgBase,
})

export const checkbox = style({
  position: 'absolute',
  top: '6px',
  left: '6px',
  zIndex: 4,
  width: '18px',
  height: '18px',
  cursor: 'pointer',
  accentColor: vars.color.primary,
  opacity: 0,
  selectors: {
    [`${tile}:hover &`]: { opacity: 1 },
    '&:checked': { opacity: 1 },
  },
})

export const checkboxVisible = style({
  opacity: 1,
})

export const correctedBadge = style({
  position: 'absolute',
  top: '6px',
  right: '6px',
  zIndex: 4,
  padding: '1px 7px',
  borderRadius: vars.radius.full,
  fontSize: '10px',
  fontWeight: 700,
  background: vars.color.successMuted,
  color: vars.color.success,
  border: `1px solid ${vars.color.success}`,
})

// ── overlay de caixa (proposta) ──────────────────────────────────────────

export const boxLayer = style({
  position: 'absolute',
  inset: 0,
})

export const box = style({
  position: 'absolute',
  border: `2px dashed ${vars.color.warning}`,
  boxSizing: 'border-box',
  pointerEvents: 'none',
})

export const boxCorrected = style({
  borderStyle: 'solid',
  borderColor: vars.color.success,
})

export const boxEditable = style({
  pointerEvents: 'auto',
  cursor: 'move',
})

export const handle = style({
  position: 'absolute',
  width: '9px',
  height: '9px',
  background: vars.color.textOnPrimary,
  border: `1px solid ${vars.color.borderStrong}`,
  borderRadius: '2px',
  boxSizing: 'border-box',
  pointerEvents: 'auto',
})

export const caption = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '6px',
  padding: '5px 7px',
  fontSize: '11px',
  color: vars.color.textSecondary,
  lineHeight: 1.4,
})

export const captionClass = style({
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  fontWeight: 600,
})

export const captionConfidence = style({
  fontFamily: vars.font.mono,
  flexShrink: 0,
  color: vars.color.textMuted,
})

export const emptyState = style({
  padding: vars.space.xl,
  textAlign: 'center',
  color: vars.color.textMuted,
  fontSize: '14px',
})

export const pagination = style({
  display: 'flex',
  gap: '8px',
  alignItems: 'center',
  justifyContent: 'center',
  marginTop: vars.space.sm,
  paddingBottom: vars.space.md,
})

export const hint = style({
  fontSize: '11px',
  color: vars.color.textMuted,
})
