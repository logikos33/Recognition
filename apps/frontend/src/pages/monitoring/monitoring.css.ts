/**
 * monitoring.css.ts — estilos da página oculta /monitoring (edge Jetson).
 * Só tokens do tema (vars) — zero cor hardcoded (guard-rail no-offbrand-colors).
 */
import { style, styleVariants } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const page = style({
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  overflow: 'auto',
  padding: `${vars.space.lg} ${vars.space.xl}`,
  gap: vars.space.md,
})

export const headerRow = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: vars.space.md,
  flexWrap: 'wrap',
})

export const pageTitle = style({
  fontSize: 20,
  fontWeight: 700,
  color: vars.color.textPrimary,
  margin: 0,
})

export const pageSubtitle = style({
  fontSize: 13,
  color: vars.color.textMuted,
  margin: 0,
})

export const controls = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  flexWrap: 'wrap',
})

export const select = style({
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderStrong}`,
  borderRadius: vars.radius.md,
  color: vars.color.textPrimary,
  padding: '6px 10px',
  fontSize: 13,
  outline: 'none',
  cursor: 'pointer',
})

export const windowGroup = style({
  display: 'inline-flex',
  border: `1px solid ${vars.color.borderStrong}`,
  borderRadius: vars.radius.full,
  overflow: 'hidden',
})

export const windowBtn = style({
  padding: '6px 12px',
  fontSize: 12,
  fontWeight: 600,
  background: 'transparent',
  border: 'none',
  color: vars.color.textSecondary,
  cursor: 'pointer',
  selectors: {
    '&:hover': { background: vars.color.bgHover },
  },
})

export const windowBtnActive = style({
  background: vars.color.primaryAlpha,
  color: vars.color.textPrimary,
})

// ── Banner de frescor (sempre visível) ──────────────────────────────────────

export const freshnessBar = style({
  position: 'sticky',
  top: 0,
  zIndex: 5,
})

// ── Semáforo ────────────────────────────────────────────────────────────────

export const semaphoreCard = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
  padding: vars.space.lg,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.lg,
  background: vars.color.bgSurface,
})

export const semaphoreHead = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
  flexWrap: 'wrap',
})

const dotBase = style({
  width: 16,
  height: 16,
  borderRadius: vars.radius.full,
  flexShrink: 0,
})

export const semaphoreDot = styleVariants({
  ok: [dotBase, { background: vars.color.success, boxShadow: vars.shadow.sm }],
  warn: [dotBase, { background: vars.color.warning, boxShadow: vars.shadow.sm }],
  crit: [dotBase, { background: vars.color.danger, boxShadow: vars.shadow.glowDanger }],
})

export const semaphoreTitle = style({
  fontSize: 16,
  fontWeight: 700,
  color: vars.color.textPrimary,
})

export const semaphoreReason = style({
  fontSize: 14,
  color: vars.color.textSecondary,
})

export const reasonList = style({
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  margin: 0,
  padding: 0,
  listStyle: 'none',
})

export const reasonItem = style({
  display: 'flex',
  alignItems: 'baseline',
  gap: vars.space.sm,
  fontSize: 13,
  color: vars.color.textSecondary,
  flexWrap: 'wrap',
})

export const runbookText = style({
  fontSize: 12,
  color: vars.color.textMuted,
  fontStyle: 'italic',
})

// ── Grid de cards ───────────────────────────────────────────────────────────

export const cardsGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
  gap: vars.space.md,
  alignItems: 'start',
})

export const chartsGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
  gap: vars.space.md,
})

export const cardFull = style({
  gridColumn: '1 / -1',
})

// ── Blocos internos dos cards ───────────────────────────────────────────────

export const statGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
  gap: vars.space.sm,
})

export const statRow = style({
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
})

export const statLabel = style({
  fontSize: 11,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  color: vars.color.textMuted,
})

export const statValue = style({
  fontSize: 15,
  fontWeight: 700,
  color: vars.color.textPrimary,
  fontVariantNumeric: 'tabular-nums',
})

export const statSub = style({
  fontSize: 11,
  color: vars.color.textMuted,
})

export const sectionLabel = style({
  fontSize: 12,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: vars.color.textMuted,
  marginTop: vars.space.sm,
})

// Barra de medida (RAM/disk/etc.)
export const meterTrack = style({
  position: 'relative',
  height: 6,
  borderRadius: vars.radius.full,
  background: vars.color.bgElevated,
  overflow: 'hidden',
})

export const meterFill = style({
  position: 'absolute',
  insetBlock: 0,
  left: 0,
  borderRadius: vars.radius.full,
})

// Mini-barras por core de CPU
export const coreGrid = style({
  display: 'flex',
  alignItems: 'flex-end',
  gap: 3,
  height: 30,
})

export const coreBar = style({
  position: 'relative',
  width: 8,
  height: '100%',
  borderRadius: 2,
  background: vars.color.bgElevated,
  overflow: 'hidden',
})

export const coreFill = style({
  position: 'absolute',
  insetInline: 0,
  bottom: 0,
  borderRadius: 2,
})

// Chips (temperaturas por zona, classes de detecção)
export const chipRow = style({
  display: 'flex',
  flexWrap: 'wrap',
  gap: 6,
})

export const chip = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  fontSize: 12,
  fontWeight: 600,
  padding: '2px 8px',
  borderRadius: vars.radius.full,
  border: `1px solid ${vars.color.borderSubtle}`,
  color: vars.color.textSecondary,
  fontVariantNumeric: 'tabular-nums',
})

// Eventos
export const eventList = style({
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
  margin: 0,
  padding: 0,
  listStyle: 'none',
  maxHeight: 160,
  overflow: 'auto',
})

export const eventItem = style({
  display: 'flex',
  alignItems: 'baseline',
  gap: vars.space.sm,
  fontSize: 12,
  color: vars.color.textSecondary,
})

export const eventTs = style({
  fontFamily: vars.font.mono,
  fontSize: 11,
  color: vars.color.textMuted,
  flexShrink: 0,
})

// Tabelas simples (serviços, pipeline, inferência)
export const tableWrap = style({
  overflowX: 'auto',
})

export const table = style({
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: 13,
})

export const th = style({
  textAlign: 'left',
  padding: '6px 10px',
  fontSize: 11,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  color: vars.color.textMuted,
  borderBottom: `1px solid ${vars.color.borderDefault}`,
  whiteSpace: 'nowrap',
})

export const td = style({
  padding: '6px 10px',
  color: vars.color.textSecondary,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  fontVariantNumeric: 'tabular-nums',
  whiteSpace: 'nowrap',
})

export const mono = style({
  fontFamily: vars.font.mono,
  fontSize: 12,
})

export const muted = style({
  color: vars.color.textMuted,
  fontSize: 12,
})

// Logtail
export const logPre = style({
  fontFamily: vars.font.mono,
  fontSize: 12,
  lineHeight: 1.5,
  color: vars.color.textSecondary,
  background: vars.color.bgBase,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.md,
  padding: vars.space.md,
  maxHeight: '50vh',
  overflow: 'auto',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-all',
  margin: 0,
})

// Thresholds modal
export const thresholdsGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
  gap: vars.space.md,
})

export const checkboxRow = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  fontSize: 13,
  color: vars.color.textSecondary,
  cursor: 'pointer',
})

// Indicador "ao vivo"
export const liveBadge = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  fontSize: 12,
  fontWeight: 600,
  padding: '4px 10px',
  borderRadius: vars.radius.full,
  border: `1px solid ${vars.color.borderSubtle}`,
  color: vars.color.textSecondary,
  cursor: 'default',
})

export const liveDot = style({
  width: 8,
  height: 8,
  borderRadius: vars.radius.full,
  background: vars.color.success,
})
