/**
 * AnnotationStudio styles — estúdio de anotação em tela cheia, dark-first,
 * usando os tokens do tema (white-label: nunca hex hardcoded).
 */
import { keyframes, style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

const spin = keyframes({
  from: { transform: 'rotate(0deg)' },
  to: { transform: 'rotate(360deg)' },
})

export const spinIcon = style({
  animation: `${spin} 1s linear infinite`,
})

export const root = style({
  position: 'fixed',
  // top respeita o espaço ocupado pelos banners globais (impersonation /
  // contexto de tenant assumido) — ver GlobalBanners.tsx. Sem isso, esta
  // tela fixed em zIndex 200 nasce por baixo dos banners (zIndex 2000/2001)
  // e a topBar fica inacessível.
  top: 'var(--global-banner-offset, 0px)',
  right: 0,
  bottom: 0,
  left: 0,
  zIndex: 200,
  display: 'flex',
  flexDirection: 'column',
  background: vars.color.bgBase,
  color: vars.color.textPrimary,
  userSelect: 'none',
})

// ── Barra superior ───────────────────────────────────────────────────────────

export const topBar = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: vars.color.bgSurface,
  borderBottom: `1px solid ${vars.color.borderDefault}`,
  flexShrink: 0,
})

export const topBarTitle = style({
  fontSize: '13px',
  fontWeight: 600,
  color: vars.color.textPrimary,
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
})

export const topBarMeta = style({
  fontSize: '12px',
  fontFamily: vars.font.mono,
  color: vars.color.textMuted,
  whiteSpace: 'nowrap',
})

export const progressText = style({
  fontSize: '13px',
  fontFamily: vars.font.mono,
  fontWeight: 600,
  color: vars.color.textSecondary,
  whiteSpace: 'nowrap',
})

export const saveBadge = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  fontSize: '12px',
  fontWeight: 600,
  padding: '3px 10px',
  borderRadius: vars.radius.full,
  whiteSpace: 'nowrap',
})

export const saveBadgeSaving = style({
  color: vars.color.textSecondary,
  background: vars.color.bgCard,
})

export const saveBadgeSaved = style({
  color: vars.color.success,
  background: vars.color.successMuted,
})

export const iconButton = style({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '6px',
  padding: '6px 10px',
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.textSecondary,
  background: 'transparent',
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  cursor: 'pointer',
  selectors: {
    '&:hover': {
      color: vars.color.textPrimary,
      background: vars.color.bgHover,
    },
  },
})

export const iconButtonActive = style({
  color: vars.color.primary,
  borderColor: vars.color.primary,
  background: vars.color.primaryAlpha,
})

export const iconButtonDisabled = style({
  opacity: 0.4,
  cursor: 'not-allowed',
  selectors: {
    '&:hover': {
      color: vars.color.textSecondary,
      background: 'transparent',
    },
  },
})

// ── Banner de erro de salvamento — impossível de ignorar ─────────────────────

export const errorBanner = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: vars.space.md,
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: vars.color.danger,
  color: vars.color.textOnPrimary,
  fontSize: '14px',
  fontWeight: 700,
  flexShrink: 0,
})

export const errorBannerButton = style({
  padding: '6px 14px',
  fontSize: '13px',
  fontWeight: 700,
  color: vars.color.danger,
  background: vars.color.textOnPrimary,
  border: 'none',
  borderRadius: vars.radius.md,
  cursor: 'pointer',
})

// ── Área principal ───────────────────────────────────────────────────────────

export const main = style({
  display: 'flex',
  flex: 1,
  minHeight: 0,
})

export const stage = style({
  position: 'relative',
  flex: 1,
  minWidth: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  overflow: 'hidden',
  background: vars.color.bgBase,
})

export const imageWrap = style({
  position: 'relative',
  display: 'inline-block',
  maxWidth: '100%',
  maxHeight: '100%',
})

export const stageImage = style({
  display: 'block',
  maxWidth: '100%',
  maxHeight: 'calc(100vh - 96px)',
  objectFit: 'contain',
  pointerEvents: 'none',
})

export const imageBroken = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: vars.space.md,
  padding: vars.space.xxl,
  color: vars.color.textMuted,
  fontSize: '14px',
})

// Overlay de caixas cobre exatamente a imagem (o wrap encolhe pro tamanho dela)
export const boxLayer = style({
  position: 'absolute',
  inset: 0,
})

export const box = style({
  position: 'absolute',
  border: '2px solid',
  cursor: 'move',
  boxSizing: 'border-box',
})

export const boxLabel = style({
  position: 'absolute',
  top: 0,
  left: 0,
  transform: 'translateY(-100%)',
  fontSize: '10px',
  fontWeight: 700,
  lineHeight: 1.4,
  padding: '0 4px',
  whiteSpace: 'nowrap',
  color: vars.color.textOnPrimary,
  pointerEvents: 'none',
})

export const handle = style({
  position: 'absolute',
  width: '10px',
  height: '10px',
  background: vars.color.textOnPrimary,
  border: `1px solid ${vars.color.borderStrong}`,
  borderRadius: '2px',
  boxSizing: 'border-box',
})

// ── Sidebar ──────────────────────────────────────────────────────────────────

export const sidebar = style({
  width: '272px',
  flexShrink: 0,
  display: 'flex',
  flexDirection: 'column',
  minHeight: 0,
  background: vars.color.bgSurface,
  borderLeft: `1px solid ${vars.color.borderDefault}`,
})

export const sidebarSection = style({
  padding: vars.space.md,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
})

export const sidebarTitle = style({
  fontSize: '11px',
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  color: vars.color.textMuted,
  margin: `0 0 ${vars.space.sm}`,
})

export const paletteRow = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  width: '100%',
  padding: '5px 8px',
  fontSize: '13px',
  color: vars.color.textSecondary,
  background: 'transparent',
  border: '1px solid transparent',
  borderRadius: vars.radius.md,
  cursor: 'pointer',
  textAlign: 'left',
  selectors: {
    '&:hover': { background: vars.color.bgHover },
  },
})

export const paletteRowActive = style({
  color: vars.color.textPrimary,
  borderColor: vars.color.primary,
  background: vars.color.primaryAlpha,
})

export const keyBadge = style({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  minWidth: '18px',
  height: '18px',
  fontSize: '11px',
  fontWeight: 700,
  fontFamily: vars.font.mono,
  color: vars.color.textSecondary,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: '4px',
  flexShrink: 0,
})

export const colorSwatch = style({
  width: '12px',
  height: '12px',
  borderRadius: '3px',
  flexShrink: 0,
})

export const paletteName = style({
  flex: 1,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const paletteCount = style({
  fontSize: '11px',
  fontFamily: vars.font.mono,
  color: vars.color.textDim,
})

// ── Fila lateral de miniaturas ───────────────────────────────────────────────

export const queue = style({
  flex: 1,
  minHeight: 0,
  overflowY: 'auto',
  padding: vars.space.sm,
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
})

export const queueItem = style({
  position: 'relative',
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: '4px',
  borderRadius: vars.radius.md,
  border: '1px solid transparent',
  cursor: 'pointer',
  background: 'transparent',
  textAlign: 'left',
  selectors: {
    '&:hover': { background: vars.color.bgHover },
  },
})

export const queueItemCurrent = style({
  borderColor: vars.color.primary,
  background: vars.color.primaryAlpha,
})

export const queueThumb = style({
  width: '64px',
  height: '40px',
  objectFit: 'cover',
  borderRadius: '4px',
  background: vars.color.bgCard,
  flexShrink: 0,
})

export const queueMeta = style({
  minWidth: 0,
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
  fontSize: '11px',
  color: vars.color.textMuted,
  fontFamily: vars.font.mono,
})

export const queueDone = style({
  color: vars.color.success,
})

// ── Legenda de atalhos ───────────────────────────────────────────────────────

export const legend = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  fontSize: '11px',
  lineHeight: 1.7,
  color: vars.color.textDim,
  flexShrink: 0,
})

export const kbd = style({
  display: 'inline-block',
  padding: '0 4px',
  fontSize: '10px',
  fontFamily: vars.font.mono,
  fontWeight: 700,
  color: vars.color.textSecondary,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: '3px',
  margin: '0 2px',
})

// ── Overlays (ajuda / diretrizes / brilho / nova classe) ─────────────────────

export const overlayBackdrop = style({
  position: 'absolute',
  inset: 0,
  zIndex: 20,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: vars.color.overlay,
})

export const overlayPanel = style({
  width: 'min(560px, calc(100vw - 48px))',
  maxHeight: 'calc(100vh - 96px)',
  overflowY: 'auto',
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderStrong}`,
  borderRadius: vars.radius.lg,
  boxShadow: vars.shadow.lg,
  padding: vars.space.lg,
})

export const overlayTitle = style({
  margin: `0 0 ${vars.space.md}`,
  fontSize: '15px',
  fontWeight: 700,
  color: vars.color.textPrimary,
})

export const overlayFooter = style({
  marginTop: vars.space.md,
  paddingTop: vars.space.sm,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  fontSize: '11px',
  fontFamily: vars.font.mono,
  color: vars.color.textDim,
})

export const shortcutTable = style({
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '13px',
  color: vars.color.textSecondary,
})

export const shortcutCell = style({
  padding: '4px 8px',
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
})

export const guidelineSection = style({
  marginBottom: vars.space.md,
})

export const guidelineTitle = style({
  fontSize: '13px',
  fontWeight: 700,
  color: vars.color.textPrimary,
  margin: `0 0 ${vars.space.xs}`,
})

export const guidelineList = style({
  margin: 0,
  paddingLeft: '18px',
  fontSize: '13px',
  lineHeight: 1.6,
  color: vars.color.textSecondary,
})

// ── Painel flutuante de brilho/contraste ─────────────────────────────────────

export const floatPanel = style({
  position: 'absolute',
  top: vars.space.md,
  left: vars.space.md,
  zIndex: 15,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
  padding: vars.space.md,
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderStrong}`,
  borderRadius: vars.radius.lg,
  boxShadow: vars.shadow.md,
  fontSize: '12px',
  color: vars.color.textSecondary,
  width: '220px',
})

export const sliderRow = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
})

export const textInput = style({
  width: '100%',
  padding: '7px 10px',
  fontSize: '13px',
  color: vars.color.textPrimary,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  selectors: {
    '&:focus': {
      outline: 'none',
      borderColor: vars.color.primary,
    },
  },
})
