import { style } from '@vanilla-extract/css'
import { vars } from '../styles/theme.css'

export const pageWrapper = style({
  padding: `${vars.space.lg} ${vars.space.xl}`,
  maxWidth: 1400,
  margin: '0 auto',
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.lg,
})

export const pageHeader = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
})

export const pageTitle = style({
  fontSize: '22px',
  fontWeight: 700,
  color: vars.color.textPrimary,
  margin: 0,
})

export const headerCounts = style({
  fontSize: '13px',
  color: vars.color.textSecondary,
})

export const headerNote = style({
  fontSize: '12px',
  color: vars.color.textMuted,
})

export const errorBanner = style({
  padding: '10px 14px',
  background: vars.color.dangerMuted,
  border: `1px solid ${vars.color.danger}`,
  borderRadius: vars.radius.md,
  color: vars.color.danger,
  fontSize: '13px',
})

/* ── Totalizador de consequência ── */

export const totalizer = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  padding: vars.space.md,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.lg,
})

export const totalizerHeadline = style({
  fontSize: '14px',
  fontWeight: 700,
  color: vars.color.textPrimary,
})

export const totalizerRow = style({
  display: 'flex',
  gap: vars.space.sm,
  fontSize: '13px',
  color: vars.color.textSecondary,
})

export const totalizerLabel = style({
  minWidth: '180px',
  color: vars.color.textMuted,
})

export const totalizerWarn = style({
  color: vars.color.warning,
  fontWeight: 600,
})

/* ── Barra de lote ── */

export const batchBar = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: vars.color.primaryAlpha,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
})

export const batchCount = style({
  fontSize: '13px',
  fontWeight: 600,
  color: vars.color.textPrimary,
  marginRight: 'auto',
})

/* ── Tabela ── */

export const tableWrapper = style({
  overflowX: 'auto',
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.lg,
})

export const table = style({
  width: '100%',
  borderCollapse: 'collapse',
  fontFamily: vars.font.sans,
  fontSize: '13px',
})

export const thead = style({
  background: vars.color.bgSurface,
  borderBottom: `1px solid ${vars.color.borderDefault}`,
})

export const th = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  textAlign: 'left',
  fontWeight: 600,
  fontSize: '11px',
  letterSpacing: '0.05em',
  textTransform: 'uppercase',
  color: vars.color.textMuted,
  whiteSpace: 'nowrap',
})

export const tr = style({
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  transition: `background ${vars.animation.duration} ${vars.animation.easing}`,
  ':hover': { background: vars.color.bgHover },
})

export const trSelected = style({
  background: vars.color.primaryAlpha,
})

export const td = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  verticalAlign: 'middle',
  color: vars.color.textSecondary,
})

export const channelCell = style({
  fontWeight: 700,
  color: vars.color.textPrimary,
})

export const nameCell = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
})

export const nameText = style({
  fontWeight: 600,
  color: vars.color.textPrimary,
})

export const renameBtn = style({
  padding: '2px 8px',
  borderRadius: vars.radius.sm,
  border: `1px solid ${vars.color.borderDefault}`,
  background: vars.color.bgCard,
  cursor: 'pointer',
  fontSize: '11px',
  color: vars.color.textSecondary,
  ':hover': { background: vars.color.bgHover },
})

export const editRow = style({
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
})

export const editInput = style({
  padding: '5px 8px',
  borderRadius: vars.radius.sm,
  border: `1px solid ${vars.color.borderDefault}`,
  fontSize: '13px',
  background: vars.color.bgSurface,
  color: vars.color.textPrimary,
  outline: 'none',
  ':focus': { borderColor: vars.color.primary },
})

export const saveBtn = style({
  padding: '5px 10px',
  borderRadius: vars.radius.sm,
  border: 'none',
  background: vars.color.primary,
  color: vars.color.textOnPrimary,
  cursor: 'pointer',
  fontSize: '12px',
  fontWeight: 600,
  selectors: { '&:disabled': { opacity: 0.6, cursor: 'not-allowed' } },
})

export const cancelBtn = style({
  padding: '5px 10px',
  borderRadius: vars.radius.sm,
  border: `1px solid ${vars.color.borderDefault}`,
  background: vars.color.bgCard,
  cursor: 'pointer',
  fontSize: '12px',
  color: vars.color.textSecondary,
})

export const positionCell = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  flexWrap: 'wrap',
})

export const confirmPositionBtn = style({
  padding: '2px 8px',
  borderRadius: vars.radius.sm,
  border: `1px solid ${vars.color.borderDefault}`,
  background: 'transparent',
  cursor: 'pointer',
  fontSize: '11px',
  color: vars.color.textMuted,
  ':hover': { background: vars.color.bgHover, color: vars.color.textSecondary },
})

export const codecText = style({
  fontFamily: vars.font.mono,
  fontSize: '12px',
})

export const actionBtn = style({
  padding: '5px 10px',
  borderRadius: vars.radius.sm,
  border: `1px solid ${vars.color.borderDefault}`,
  background: vars.color.bgCard,
  cursor: 'pointer',
  fontSize: '12px',
  color: vars.color.textSecondary,
  ':hover': { background: vars.color.bgHover },
})

/* ── Preview ── */

export const previewPanel = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
  padding: vars.space.md,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.lg,
})

export const previewHeader = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
})

export const previewTitle = style({
  fontSize: '14px',
  fontWeight: 700,
  color: vars.color.textPrimary,
})

export const previewNotice = style({
  fontSize: '12px',
  color: vars.color.warning,
  background: vars.color.warningMuted,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  padding: vars.space.sm,
  lineHeight: 1.5,
})

export const previewVideoWrap = style({
  borderRadius: vars.radius.md,
  overflow: 'hidden',
  background: '#000', // allow: área de vídeo (sempre preta)
})

export const previewPlaceholder = style({
  width: 480,
  height: 270,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: 'rgba(255,255,255,0.5)', // allow: texto sobre placeholder preto de vídeo
  fontSize: '13px',
})

export const previewActions = style({
  display: 'flex',
  gap: vars.space.sm,
})

export const emptyText = style({
  padding: '48px 0',
  textAlign: 'center',
  color: vars.color.textMuted,
  fontSize: '14px',
})

export const loadingText = style({
  padding: '48px 0',
  textAlign: 'center',
  color: vars.color.textMuted,
  fontSize: '14px',
})
