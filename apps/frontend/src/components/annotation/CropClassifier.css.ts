/**
 * CropClassifier styles — mesma linguagem visual do AnnotationStudio
 * (dark-first, tokens do tema, nunca hex hardcoded).
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const root = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.md,
})

// ── barra de sessão ──────────────────────────────────────────────────────────

export const sessionBar = style({
  display: 'flex',
  flexWrap: 'wrap',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: vars.space.sm,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
})

export const sessionStat = style({
  fontSize: '12px',
  color: vars.color.textSecondary,
  fontFamily: vars.font.mono,
  whiteSpace: 'nowrap',
})

export const sessionStatStrong = style({
  color: vars.color.textPrimary,
  fontWeight: 700,
})

export const countBadges = style({
  display: 'flex',
  flexWrap: 'wrap',
  gap: '6px',
})

export const pendingBanner = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: `${vars.space.xs} ${vars.space.sm}`,
  background: vars.color.warningMuted,
  border: `1px solid ${vars.color.warning}`,
  borderRadius: vars.radius.md,
  fontSize: '12px',
  color: vars.color.warning,
})

/** Causa real da falha de sincronização, ao lado do contador de pendentes —
 * o banner precisa dizer POR QUE, não só que há pendência. */
export const pendingReason = style({
  opacity: 0.85,
  fontStyle: 'italic',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  maxWidth: '40ch',
})

export const retryButton = style({
  marginLeft: 'auto',
  padding: '3px 10px',
  fontSize: '11px',
  fontWeight: 700,
  color: vars.color.warning,
  background: 'transparent',
  border: `1px solid ${vars.color.warning}`,
  borderRadius: vars.radius.sm,
  cursor: 'pointer',
})

// ── área principal ───────────────────────────────────────────────────────────

export const main = style({
  display: 'flex',
  gap: vars.space.md,
  minHeight: '480px',
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
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.lg,
})

export const cropTile = style({
  position: 'relative',
  width: '100%',
  maxWidth: '640px',
  aspectRatio: '4 / 3',
  overflow: 'hidden',
  background: vars.color.bgCard,
})

export const cropImg = style({
  position: 'absolute',
  maxWidth: 'none',
  pointerEvents: 'none',
})

/** Recorte de frame inteiro (bbox [0,0,1,1] — sem detector de pessoa
 * dedicado ainda, ver nota no topo de CropClassifier.tsx): renderiza a
 * imagem com object-fit:contain (mesmo tratamento de stageImage do
 * AnnotationStudio) em vez do truque de cropStyle, que estica pra
 * preencher o tile e distorceria a proporção de um frame inteiro. */
export const cropImgContain = style({
  display: 'block',
  maxWidth: '100%',
  maxHeight: '600px',
  objectFit: 'contain',
  pointerEvents: 'none',
})

export const imageBroken = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: vars.space.xxl,
  color: vars.color.textMuted,
  fontSize: '13px',
})

// ── painel de tipos (radio por tipo) ─────────────────────────────────────────

export const panel = style({
  width: '340px',
  flexShrink: 0,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.md,
  overflowY: 'auto',
})

export const typeGroup = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  padding: vars.space.sm,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
})

/** Tipo em foco pelo deep-link da matriz de cobertura (class_id da lacuna
 * clicada) — só um destaque visual, não filtra nem trava os outros tipos. */
export const typeGroupEmphasized = style({
  borderColor: vars.color.primary,
  boxShadow: `0 0 0 1px ${vars.color.primary}`,
})

export const typeLabel = style({
  fontSize: '12px',
  fontWeight: 700,
  color: vars.color.textPrimary,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
})

export const stateRow = style({
  display: 'flex',
  flexWrap: 'wrap',
  gap: '6px',
})

export const stateButton = style({
  position: 'relative',
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '6px 10px',
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.textSecondary,
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  cursor: 'pointer',
  selectors: {
    '&:hover': { color: vars.color.textPrimary, background: vars.color.bgHover },
  },
})

export const stateButtonActivePresente = style({
  color: vars.color.success,
  borderColor: vars.color.success,
  background: vars.color.successMuted,
})

export const stateButtonActiveAusente = style({
  color: vars.color.danger,
  borderColor: vars.color.danger,
  background: vars.color.dangerMuted,
})

export const stateButtonActiveNeutral = style({
  color: vars.color.primary,
  borderColor: vars.color.primary,
  background: vars.color.primaryAlpha,
})

export const keyBadge = style({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  minWidth: '16px',
  height: '16px',
  fontSize: '10px',
  fontWeight: 700,
  fontFamily: vars.font.mono,
  color: 'inherit',
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: '3px',
})

// % de confiança da proposta de IA — mesma cor de "proposta" do estúdio
// (borda tracejada warning) e da galeria (selo ⚠ Proposta).
export const confBadge = style({
  fontSize: '10px',
  fontWeight: 700,
  fontFamily: vars.font.mono,
  padding: '0 4px',
  borderRadius: '3px',
  color: vars.color.warning,
  border: `1px solid ${vars.color.warning}`,
})

export const suggestedDot = style({
  position: 'absolute',
  top: '-4px',
  right: '-4px',
  width: '8px',
  height: '8px',
  borderRadius: '50%',
  background: vars.color.accent,
})

// ── ações ─────────────────────────────────────────────────────────────────

export const actions = style({
  display: 'flex',
  flexWrap: 'wrap',
  gap: '8px',
})

export const legend = style({
  fontSize: '11px',
  lineHeight: 1.7,
  color: vars.color.textDim,
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

export const missingList = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
  fontSize: '12px',
  color: vars.color.textSecondary,
})
