/**
 * TrainingGallery styles — galeria de imagens de treino com curadoria.
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const filterBar = style({
  position: 'sticky',
  top: 0,
  zIndex: 10,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
  padding: `${vars.space.sm} 0`,
  background: vars.color.bgBase,
  marginBottom: vars.space.md,
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

export const resultLine = style({
  fontSize: '13px',
  fontFamily: vars.font.mono,
  color: vars.color.textSecondary,
})

export const grid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
  gap: '10px',
  marginBottom: vars.space.md,
})

export const card = style({
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

export const cardSelected = style({
  borderColor: vars.color.primary,
  boxShadow: `0 0 0 2px ${vars.color.primaryAlpha}`,
})

export const cardExcluded = style({
  opacity: 0.55,
})

export const cardImage = style({
  width: '100%',
  height: '104px',
  objectFit: 'cover',
  display: 'block',
  background: vars.color.bgBase,
})

export const cardImageBroken = style({
  width: '100%',
  height: '104px',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '4px',
  fontSize: '10px',
  color: vars.color.textMuted,
  background: vars.color.bgBase,
})

export const cardMeta = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
  padding: '5px 7px',
  fontSize: '11px',
  color: vars.color.textMuted,
  lineHeight: 1.4,
})

export const cardMetaRow = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '6px',
  overflow: 'hidden',
})

export const cardCamera = style({
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  color: vars.color.textSecondary,
  fontWeight: 600,
})

export const cardTime = style({
  fontFamily: vars.font.mono,
  flexShrink: 0,
})

export const checkbox = style({
  position: 'absolute',
  top: '6px',
  left: '6px',
  zIndex: 3,
  width: '18px',
  height: '18px',
  cursor: 'pointer',
  accentColor: vars.color.primary,
  opacity: 0,
  selectors: {
    [`${card}:hover &`]: { opacity: 1 },
    '&:checked': { opacity: 1 },
  },
})

export const checkboxVisible = style({
  opacity: 1,
})

// Selos de procedência — estado sempre com cor + palavra, nunca só cor.
// "Proposta" (máquina, ninguém conferiu) tem que ser CLARAMENTE distinta de
// anotação humana a três metros da tela: borda tracejada + warning.
export const seal = style({
  position: 'absolute',
  top: '6px',
  right: '6px',
  zIndex: 2,
  display: 'inline-flex',
  alignItems: 'center',
  gap: '3px',
  padding: '1px 7px',
  borderRadius: vars.radius.full,
  fontSize: '10px',
  fontWeight: 700,
})

export const sealHumana = style({
  background: vars.color.successMuted,
  color: vars.color.success,
  border: `1px solid ${vars.color.success}`,
})

export const sealAprovada = style({
  background: vars.color.successMuted,
  color: vars.color.success,
  border: `1px dashed ${vars.color.success}`,
})

export const sealProposta = style({
  background: vars.color.warningMuted,
  color: vars.color.warning,
  border: `2px dashed ${vars.color.warning}`,
})

export const statusChip = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '3px',
  padding: '0 6px',
  borderRadius: vars.radius.full,
  fontSize: '10px',
  fontWeight: 700,
  whiteSpace: 'nowrap',
})

export const statusChipDuvida = style({
  background: vars.color.warningMuted,
  color: vars.color.warning,
})

export const statusChipExcluida = style({
  background: vars.color.dangerMuted,
  color: vars.color.danger,
})

// ── barra de ação fixa (seleção múltipla) — sobreposta, não empurra nada ─────

export const actionBar = style({
  position: 'fixed',
  bottom: '20px',
  left: '50%',
  transform: 'translateX(-50%)',
  zIndex: 50,
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderStrong}`,
  borderRadius: vars.radius.lg,
  boxShadow: vars.shadow.lg,
})

export const actionBarCount = style({
  fontSize: '13px',
  fontWeight: 700,
  fontFamily: vars.font.mono,
  color: vars.color.textPrimary,
  whiteSpace: 'nowrap',
})

export const selectionLink = style({
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.textSecondary,
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  padding: '2px 6px',
  textDecoration: 'underline',
  selectors: {
    '&:hover': { color: vars.color.textPrimary },
  },
})

export const uploadZone = style({
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  padding: '14px 18px',
  marginBottom: vars.space.md,
  borderRadius: vars.radius.lg,
  border: `1.5px dashed ${vars.color.borderStrong}`,
  background: vars.color.bgCard,
  cursor: 'pointer',
  transition: 'all 0.15s',
})

export const uploadZoneActive = style({
  borderColor: vars.color.primaryLight,
  background: vars.color.primaryAlpha,
})

export const pagination = style({
  display: 'flex',
  gap: '8px',
  alignItems: 'center',
  justifyContent: 'center',
  marginTop: vars.space.sm,
  paddingBottom: '64px', // espaço pra barra de ação fixa não cobrir a última linha
})

export const undoButton = style({
  marginLeft: '10px',
  padding: '3px 10px',
  fontSize: '12px',
  fontWeight: 700,
  color: vars.color.textOnPrimary,
  background: vars.color.primary,
  border: 'none',
  borderRadius: vars.radius.md,
  cursor: 'pointer',
})
