/**
 * SearchFindingsPanel styles — painel de resultados ANCORADO (drawer fixo,
 * nunca modal/overlay de tela cheia — mesma regra de SearchContentPanel).
 * Mesmos tokens (white-label).
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const panel = style({
  position: 'fixed',
  top: '32px',
  right: vars.space.md,
  bottom: '16px',
  zIndex: 55,
  display: 'flex',
  flexDirection: 'column',
  width: '560px',
  maxWidth: 'calc(100vw - 32px)',
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderStrong}`,
  borderRadius: vars.radius.lg,
  boxShadow: vars.shadow.lg,
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
  fontSize: '14px',
  fontWeight: 700,
  color: vars.color.textPrimary,
})

export const closeButton = style({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '24px',
  height: '24px',
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
  gap: vars.space.md,
})

// 🔴 Aviso PERMANENTE — "amostra, não contagem" — nunca dispensável.
export const disclaimer = style({
  margin: 0,
  padding: vars.space.sm,
  fontSize: '12px',
  lineHeight: 1.5,
  color: vars.color.warning,
  background: vars.color.warningMuted,
  border: `1px solid ${vars.color.warning}`,
  borderRadius: vars.radius.md,
})

export const disclaimerStrong = style({
  color: vars.color.danger,
  fontWeight: 800,
})

export const emptyText = style({
  fontSize: '13px',
  color: vars.color.textMuted,
})

export const group = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '8px',
  paddingBottom: vars.space.md,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  selectors: {
    '&:last-child': { borderBottom: 'none', paddingBottom: 0 },
  },
})

export const groupTitle = style({
  fontSize: '13px',
  fontWeight: 700,
  color: vars.color.textPrimary,
})

export const classRow = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  flexWrap: 'wrap',
})

export const classSelect = style({
  flex: 1,
  minWidth: '160px',
  padding: '6px 8px',
  fontSize: '12px',
  color: vars.color.textPrimary,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
})

export const createRow = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  padding: vars.space.sm,
  background: vars.color.bgCard,
  border: `1px dashed ${vars.color.borderStrong}`,
  borderRadius: vars.radius.md,
})

export const createInput = style({
  flex: 1,
  padding: '6px 8px',
  fontSize: '12px',
  color: vars.color.textPrimary,
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
})

export const grid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(112px, 1fr))',
  gap: '8px',
})

export const tile = style({
  position: 'relative',
  width: '100%',
  aspectRatio: '1 / 1',
  overflow: 'hidden',
  borderRadius: vars.radius.md,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
})

export const tileImg = style({
  position: 'absolute',
  maxWidth: 'none',
  pointerEvents: 'none',
})

export const confidenceBadge = style({
  position: 'absolute',
  top: '4px',
  right: '4px',
  zIndex: 2,
  padding: '1px 5px',
  borderRadius: vars.radius.full,
  fontSize: '10px',
  fontWeight: 700,
  fontFamily: vars.font.mono,
  color: vars.color.textOnPrimary,
  background: 'rgba(0,0,0,0.6)',
  pointerEvents: 'none',
})

export const promotedBadge = style({
  position: 'absolute',
  inset: 0,
  zIndex: 3,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '4px',
  fontSize: '11px',
  fontWeight: 700,
  color: vars.color.success,
  background: 'rgba(0,0,0,0.55)',
  pointerEvents: 'none',
})

export const promoteButton = style({
  position: 'absolute',
  left: '4px',
  right: '4px',
  bottom: '4px',
  zIndex: 2,
  padding: '3px 0',
  fontSize: '10px',
  fontWeight: 700,
  color: vars.color.textOnPrimary,
  background: vars.color.primary,
  border: 'none',
  borderRadius: vars.radius.sm,
  cursor: 'pointer',
  selectors: {
    '&:disabled': { opacity: 0.4, cursor: 'not-allowed' },
  },
})
