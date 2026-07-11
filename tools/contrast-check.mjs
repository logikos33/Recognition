#!/usr/bin/env node
/**
 * WCAG 2.1 contrast ratio checker for recognition-light token pairs.
 * Formula: https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
 */

function linearize(c8bit) {
  const c = c8bit / 255
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
}

function luminance(hex) {
  const clean = hex.replace('#', '')
  const r = linearize(parseInt(clean.slice(0, 2), 16))
  const g = linearize(parseInt(clean.slice(2, 4), 16))
  const b = linearize(parseInt(clean.slice(4, 6), 16))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(hex1, hex2) {
  const L1 = luminance(hex1)
  const L2 = luminance(hex2)
  const lighter = Math.max(L1, L2)
  const darker  = Math.min(L1, L2)
  return (lighter + 0.05) / (darker + 0.05)
}

function grade(ratio, isLargeText = false) {
  const aaThresh  = isLargeText ? 3.0 : 4.5
  const aaaThresh = isLargeText ? 4.5 : 7.0
  if (ratio >= aaaThresh) return 'AAA'
  if (ratio >= aaThresh)  return 'AA'
  return `FAIL (need ${isLargeText ? '3.0' : '4.5'})`
}

// ── Token values — recognition-light ──────────────────────────────────────────
const BG = {
  bgBase:     '#F8FAFC',
  bgSurface:  '#FFFFFF',
  bgCard:     '#FFFFFF',
  bgHover:    '#F1F5F9',
  bgElevated: '#FFFFFF',
}

const TEXT = {
  textPrimary:   '#0F172A',
  textSecondary: '#334155',
  textMuted:     '#64748B',
  textDim:       '#94A3B8',
  textOnPrimary: '#FFFFFF',
}

const BRAND = {
  primary:      '#0369A1',
  primaryLight: '#0284C7',
  primaryDark:  '#075985',
  accent:       '#B45309',
  accentLight:  '#0EA5E9',
  accentDark:   '#92400E',
}

const SEMANTIC = {
  success:     '#15803D',
  warning:     '#A16207',
  danger:      '#B91C1C',
}

const SEMANTIC_BG = {
  successMuted: '#F0FDF4',
  warningMuted: '#FFFBEB',
  dangerMuted:  '#FEF2F2',
}

const BORDERS = {
  borderSubtle:  '#F1F5F9',
  borderDefault: '#E2E8F0',
  borderStrong:  '#CBD5E1',
}

// ── Pairs to check ────────────────────────────────────────────────────────────
const pairs = []

// Text × backgrounds (normal text → need 4.5 AA)
for (const [tName, tHex] of Object.entries(TEXT)) {
  for (const [bgName, bgHex] of Object.entries(BG)) {
    if (tName === 'textOnPrimary') continue // handled separately
    pairs.push({ fg: tName, bg: bgName, fgHex: tHex, bgHex, isLarge: false })
  }
}

// textOnPrimary × primary variants
pairs.push({ fg: 'textOnPrimary', bg: 'primary',      fgHex: TEXT.textOnPrimary, bgHex: BRAND.primary,      isLarge: false })
pairs.push({ fg: 'textOnPrimary', bg: 'primaryDark',  fgHex: TEXT.textOnPrimary, bgHex: BRAND.primaryDark,  isLarge: false })
pairs.push({ fg: 'textOnPrimary', bg: 'primaryLight', fgHex: TEXT.textOnPrimary, bgHex: BRAND.primaryLight, isLarge: false })

// Brand as foreground text on white
for (const [bName, bHex] of Object.entries(BRAND)) {
  pairs.push({ fg: bName, bg: 'bgSurface', fgHex: bHex, bgHex: BG.bgSurface, isLarge: false })
}

// Semantic foreground × their muted bg
pairs.push({ fg: 'success', bg: 'successMuted', fgHex: SEMANTIC.success, bgHex: SEMANTIC_BG.successMuted, isLarge: false })
pairs.push({ fg: 'warning', bg: 'warningMuted', fgHex: SEMANTIC.warning, bgHex: SEMANTIC_BG.warningMuted, isLarge: false })
pairs.push({ fg: 'danger',  bg: 'dangerMuted',  fgHex: SEMANTIC.danger,  bgHex: SEMANTIC_BG.dangerMuted,  isLarge: false })

// Semantic on white
for (const [sName, sHex] of Object.entries(SEMANTIC)) {
  pairs.push({ fg: sName, bg: 'bgSurface', fgHex: sHex, bgHex: BG.bgSurface, isLarge: false })
}

// Borders on bgSurface (informational — no AA requirement for non-text)
for (const [bName, bHex] of Object.entries(BORDERS)) {
  pairs.push({ fg: bName, bg: 'bgSurface', fgHex: bHex, bgHex: BG.bgSurface, isLarge: true, note: 'border/non-text' })
}

// ── Output ────────────────────────────────────────────────────────────────────
const rows = pairs.map(({ fg, bg, fgHex, bgHex, isLarge, note }) => {
  const ratio = contrast(fgHex, bgHex)
  const g = grade(ratio, isLarge)
  return { fg, fgHex, bg, bgHex, ratio: ratio.toFixed(2), grade: g, note: note ?? '' }
})

// Sort: FAILs first, then by ratio asc
rows.sort((a, b) => {
  const aFail = a.grade.startsWith('FAIL')
  const bFail = b.grade.startsWith('FAIL')
  if (aFail !== bFail) return aFail ? -1 : 1
  return parseFloat(a.ratio) - parseFloat(b.ratio)
})

console.log('\n═══════════════════════════════════════════════════════════════════════════════')
console.log(' WCAG Contrast Report — recognition-light (Ocean Blue)')
console.log('═══════════════════════════════════════════════════════════════════════════════')
console.log(` ${'FG token'.padEnd(18)} ${'FG hex'.padEnd(9)} ${'BG token'.padEnd(16)} ${'BG hex'.padEnd(9)} ${'Ratio'.padEnd(7)} Grade`)
console.log('─'.repeat(82))

for (const r of rows) {
  const flag = r.grade.startsWith('FAIL') ? '⚠️ ' : r.grade === 'AAA' ? '✓  ' : '✓  '
  const note = r.note ? `  [${r.note}]` : ''
  console.log(` ${flag}${r.fg.padEnd(16)} ${r.fgHex.padEnd(9)} ${r.bg.padEnd(16)} ${r.bgHex.padEnd(9)} ${r.ratio.padEnd(7)} ${r.grade}${note}`)
}

const fails = rows.filter(r => r.grade.startsWith('FAIL') && !r.note)
console.log('\n─'.repeat(82))
console.log(` FAILS (non-border): ${fails.length}`)
if (fails.length === 0) console.log(' All text pairs PASS WCAG AA ✓')
console.log('═══════════════════════════════════════════════════════════════════════════════\n')
