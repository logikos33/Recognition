import { style } from '@vanilla-extract/css'
import { vars } from '../styles/theme.css'

export const page = style({ padding: vars.space.xl })

export const pageHeader = style({
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  marginBottom: vars.space.lg,
})

export const pageTitle = style({
  color: vars.color.textPrimary, fontSize: '22px', fontWeight: 700, margin: 0,
})

export const filtersRow = style({
  display: 'flex', gap: '10px', marginBottom: vars.space.lg, flexWrap: 'wrap',
})

export const filterInput = style({
  padding: '8px 10px', borderRadius: vars.radius.sm,
  border: `1px solid ${vars.color.borderDefault}`,
  background: vars.color.bgSurface, color: vars.color.textPrimary, fontSize: '13px',
  fontFamily: vars.font.sans,
})

export const emptyBox = style({
  padding: '40px', textAlign: 'center', color: vars.color.textMuted,
  background: vars.color.bgCard, borderRadius: vars.radius.lg,
  border: `1px solid ${vars.color.borderDefault}`,
})

export const tableWrapper = style({
  background: vars.color.bgCard, borderRadius: vars.radius.lg, overflow: 'hidden',
  border: `1px solid ${vars.color.borderDefault}`,
})

export const table = style({ width: '100%', borderCollapse: 'collapse' })

export const thead = style({ background: vars.color.bgSurface })

export const th = style({
  padding: '12px 16px', textAlign: 'left', color: vars.color.textMuted,
  fontSize: '12px', fontWeight: 700, letterSpacing: '0.04em',
})

export const tr = style({ borderTop: `1px solid ${vars.color.borderSubtle}` })

const tdBase = { padding: '12px 16px', fontSize: '13px' }

export const td = style(tdBase)
export const tdDate = style({ ...tdBase, color: vars.color.textSecondary })
export const tdCamera = style({ ...tdBase, color: vars.color.textPrimary })
export const tdViolation = style({ ...tdBase, color: vars.color.danger, fontWeight: 600 })
export const tdConf = style({ ...tdBase, color: vars.color.textSecondary })

export const statusAck = style({ color: vars.color.success, fontWeight: 600 })
export const statusPending = style({ color: vars.color.warning, fontWeight: 600 })

export const pagination = style({
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  marginTop: vars.space.md,
})

export const paginationText = style({ color: vars.color.textMuted, fontSize: '13px' })

export const paginationControls = style({
  display: 'flex', gap: vars.space.sm, alignItems: 'center',
})

export const pageNum = style({ color: vars.color.textSecondary, fontSize: '13px' })
