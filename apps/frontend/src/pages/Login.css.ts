/**
 * Login page styles — tokenizado no recognition-dark (WS1).
 * Antes: palette azul-clara própria (desvio de marca). Limitação documentada:
 * white-label do tenant não aplica pré-login (branding vem do JWT).
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../styles/theme.css'

export const page = style({
  minHeight: '100vh',
  background: vars.color.bgBase,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontFamily: vars.font.sans,
  padding: '20px',
})

export const container = style({
  width: '100%',
  maxWidth: '400px',
})

export const logoWrap = style({
  textAlign: 'center',
  marginBottom: '28px',
})

export const logoIcon = style({
  width: '72px',
  height: '72px',
  borderRadius: '20px',
  margin: '0 auto 14px',
  background: `linear-gradient(135deg, ${vars.color.primary}, ${vars.color.primaryDark})`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '36px',
  boxShadow: vars.shadow.glowCyan,
})

export const logoTitle = style({
  fontSize: '28px',
  fontWeight: 800,
  color: vars.color.textPrimary,
  margin: 0,
})

export const logoSub = style({
  color: vars.color.textSecondary,
  margin: '6px 0 0',
  fontSize: '14px',
})

export const card = style({
  background: vars.color.bgSurface,
  borderRadius: '20px',
  padding: '28px 24px',
  boxShadow: vars.shadow.lg,
  border: `1px solid ${vars.color.borderDefault}`,
})

export const tabs = style({
  display: 'flex',
  background: vars.color.bgBase,
  borderRadius: '10px',
  padding: '4px',
  marginBottom: '24px',
  gap: '4px',
})

export const tabBtn = style({
  flex: 1,
  padding: '9px 0',
  border: 'none',
  borderRadius: '8px',
  fontSize: '14px',
  fontWeight: 600,
  cursor: 'pointer',
  background: 'transparent',
  color: vars.color.textMuted,
  boxShadow: 'none',
  transition: `background ${vars.animation.duration}, color ${vars.animation.duration}, box-shadow ${vars.animation.duration}`,
})

export const tabBtnActive = style({
  background: vars.color.bgElevated,
  color: vars.color.primary,
  boxShadow: vars.shadow.sm,
})

export const formStack = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
})

export const input = style({
  width: '100%',
  padding: '12px 14px',
  borderRadius: '10px',
  border: `1.5px solid ${vars.color.borderDefault}`,
  background: vars.color.bgCard,
  fontSize: '15px',
  color: vars.color.textPrimary,
  outline: 'none',
  boxSizing: 'border-box',
  fontFamily: 'inherit',
  '::placeholder': {
    color: vars.color.textMuted,
  },
  ':focus': {
    borderColor: vars.color.primary,
    boxShadow: vars.shadow.glow,
  },
})

export const errorBox = style({
  padding: '10px 14px',
  borderRadius: '8px',
  background: vars.color.dangerMuted,
  border: `1px solid ${vars.color.danger}`,
  color: vars.color.danger,
  fontSize: '13px',
})

export const submitBtn = style({
  padding: '13px',
  borderRadius: '10px',
  border: 'none',
  background: `linear-gradient(135deg, ${vars.color.primary}, ${vars.color.primaryDark})`,
  color: vars.color.textOnPrimary,
  fontSize: '15px',
  fontWeight: 700,
  cursor: 'pointer',
  boxShadow: vars.shadow.glowCyan,
})

export const submitBtnLoading = style({
  background: vars.color.primaryDark,
  cursor: 'not-allowed',
  opacity: 0.7,
})

export const credHint = style({
  marginTop: '16px',
  padding: '10px 12px',
  borderRadius: '8px',
  background: vars.color.bgCard,
  border: `1px dashed ${vars.color.borderStrong}`,
})

export const credHintLabel = style({
  margin: 0,
  fontSize: '12px',
  color: vars.color.textSecondary,
  fontWeight: 600,
})

export const credHintValue = style({
  margin: '2px 0 0',
  fontSize: '12px',
  color: vars.color.textMuted,
  fontFamily: vars.font.mono,
})

export const footer = style({
  textAlign: 'center',
  color: vars.color.textMuted,
  fontSize: '12px',
  marginTop: '20px',
})

export const footerBrand = style({
  color: vars.color.primary,
  fontWeight: 600,
})
