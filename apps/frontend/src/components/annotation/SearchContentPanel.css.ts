/**
 * SearchContentPanel styles — painel ANCORADO (drawer fixo no canto
 * superior direito, nunca modal, nunca overlay de tela cheia — mesma regra
 * de SimilarSearchPanel.css.ts). Mesmos tokens (white-label).
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const panel = style({
  position: 'fixed',
  top: '64px',
  right: vars.space.md,
  bottom: '16px',
  zIndex: 55,
  display: 'flex',
  flexDirection: 'column',
  width: '380px',
  maxWidth: 'calc(100vw - 32px)',
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderStrong}`,
  borderRadius: vars.radius.lg,
  boxShadow: vars.shadow.lg,
  fontSize: '12px',
  color: vars.color.textSecondary,
  overflow: 'hidden',
})

export const header = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: vars.space.sm,
  padding: vars.space.md,
  borderBottom: `1px solid ${vars.color.borderDefault}`,
  flexShrink: 0,
})

export const title = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  fontSize: '13px',
  fontWeight: 700,
  color: vars.color.textPrimary,
})

export const closeButton = style({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '22px',
  height: '22px',
  color: vars.color.textMuted,
  background: 'transparent',
  border: 'none',
  borderRadius: vars.radius.md,
  cursor: 'pointer',
  selectors: {
    '&:hover': { color: vars.color.textPrimary, background: vars.color.bgHover },
  },
})

export const body = style({
  flex: 1,
  overflowY: 'auto',
  padding: vars.space.md,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
})

export const infoLine = style({
  margin: 0,
  fontSize: '12px',
  color: vars.color.textSecondary,
  lineHeight: 1.5,
})

export const sectionLabel = style({
  fontSize: '11px',
  fontWeight: 700,
  color: vars.color.textMuted,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  marginTop: vars.space.xs,
})

export const termsGroup = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
  padding: vars.space.sm,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.md,
})

export const termRow = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  padding: '4px 2px',
  fontSize: '12px',
  color: vars.color.textSecondary,
  cursor: 'pointer',
})

export const termLabel = style({
  color: vars.color.textPrimary,
  fontWeight: 600,
})

export const termQuery = style({
  fontFamily: vars.font.mono,
  fontSize: '10px',
  color: vars.color.textDim,
})

export const freeTermRow = style({
  display: 'flex',
  gap: '6px',
})

export const freeTermInput = style({
  flex: 1,
  padding: '7px 10px',
  fontSize: '12px',
  color: vars.color.textPrimary,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  selectors: {
    '&::placeholder': { color: vars.color.textDim },
  },
})

export const chipsRow = style({
  display: 'flex',
  flexWrap: 'wrap',
  gap: '6px',
})

export const chip = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '5px',
  padding: '3px 8px',
  borderRadius: vars.radius.full,
  fontSize: '11px',
  fontWeight: 600,
  color: vars.color.primaryLight,
  background: vars.color.primaryAlpha,
  border: `1px solid ${vars.color.primary}`,
})

export const chipRemove = style({
  display: 'inline-flex',
  cursor: 'pointer',
  color: 'inherit',
  background: 'transparent',
  border: 'none',
  padding: 0,
  lineHeight: 0,
})

export const costBox = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
  padding: vars.space.sm,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.md,
})

export const costValue = style({
  fontSize: '15px',
  fontWeight: 700,
  color: vars.color.textPrimary,
  fontFamily: vars.font.mono,
})

export const warningBox = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.xs,
  padding: vars.space.sm,
  color: vars.color.warning,
  background: vars.color.warningMuted,
  border: `1px solid ${vars.color.warning}`,
  borderRadius: vars.radius.md,
  fontSize: '11px',
  lineHeight: 1.5,
})

export const errorBox = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.xs,
  padding: vars.space.sm,
  color: vars.color.danger,
  background: vars.color.dangerMuted,
  border: `1px solid ${vars.color.danger}`,
  borderRadius: vars.radius.md,
  fontSize: '12px',
})

export const retryButton = style({
  alignSelf: 'flex-start',
  padding: '4px 10px',
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.danger,
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.danger}`,
  borderRadius: vars.radius.md,
  cursor: 'pointer',
})

export const footer = style({
  flexShrink: 0,
  padding: vars.space.md,
  borderTop: `1px solid ${vars.color.borderDefault}`,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.xs,
})

export const cta = style({
  width: '100%',
  padding: '9px 12px',
  fontSize: '13px',
  fontWeight: 700,
  color: vars.color.textOnPrimary,
  background: vars.color.primary,
  border: 'none',
  borderRadius: vars.radius.md,
  cursor: 'pointer',
  selectors: {
    '&:disabled': {
      opacity: 0.45,
      cursor: 'not-allowed',
    },
  },
})

export const reasonText = style({
  margin: 0,
  fontSize: '11px',
  color: vars.color.textMuted,
  lineHeight: 1.4,
  textAlign: 'center',
})
