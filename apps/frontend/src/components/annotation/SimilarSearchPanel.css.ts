/**
 * SimilarSearchPanel styles — painel de configuração ancorado abaixo da
 * topBar (mesmo padrão visual do floatPanel de brilho/contraste do
 * Estúdio: card elevado com borda, NUNCA modal, NUNCA overlay de tela
 * cheia). Mesmos tokens de AnnotationStudio.css.ts (white-label).
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const panel = style({
  position: 'absolute',
  top: '52px',
  right: vars.space.md,
  zIndex: 25,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
  width: '320px',
  maxWidth: 'calc(100vw - 32px)',
  padding: vars.space.md,
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderStrong}`,
  borderRadius: vars.radius.lg,
  boxShadow: vars.shadow.md,
  fontSize: '12px',
  color: vars.color.textSecondary,
})

export const header = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: vars.space.sm,
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

export const infoLine = style({
  margin: 0,
  fontSize: '12px',
  color: vars.color.textSecondary,
  lineHeight: 1.5,
})

export const muted = style({
  margin: 0,
  fontSize: '12px',
  color: vars.color.textMuted,
})

export const quantityGroup = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
  padding: vars.space.sm,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.md,
})

export const quantityRow = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  fontSize: '12px',
  color: vars.color.textSecondary,
  cursor: 'pointer',
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
  color: vars.color.warning,
  lineHeight: 1.4,
})
