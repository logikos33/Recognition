import { useMemo } from 'react'
import { vars } from '../../../styles/theme.css'
import { RECOGNITION_DEFAULT_SURFACES } from '../../../theme/tenant-theme/defaults'

interface ColorPickerProps {
  label: string
  value: string
  onChange: (hex: string) => void
  bgBase?: string
}

function getRelativeLuminance(hex: string): number {
  const clean = hex.replace('#', '')
  const r = parseInt(clean.slice(0, 2), 16) / 255
  const g = parseInt(clean.slice(2, 4), 16) / 255
  const b = parseInt(clean.slice(4, 6), 16) / 255
  const toLinear = (c: number) => c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
  return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b)
}

function contrastRatio(hex1: string, hex2: string): number {
  const l1 = getRelativeLuminance(hex1)
  const l2 = getRelativeLuminance(hex2)
  const [lighter, darker] = l1 > l2 ? [l1, l2] : [l2, l1]
  return (lighter + 0.05) / (darker + 0.05)
}

export function ColorPicker({
  label,
  value,
  onChange,
  bgBase = RECOGNITION_DEFAULT_SURFACES.bgBase,
}: ColorPickerProps) {
  const ratio = useMemo(() => {
    if (!value || value.length < 7) return null
    try { return contrastRatio(value, bgBase) } catch { return null }
  }, [value, bgBase])

  const aaPass = ratio !== null && ratio >= 4.5

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 12, color: vars.color.textSecondary, fontWeight: 500 }}>{label}</label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <input
          type="color"
          value={value}
          onChange={e => onChange(e.target.value)}
          style={{
            width: 36, height: 36,
            border: `1px solid ${vars.color.borderDefault}`,
            borderRadius: 6,
            cursor: 'pointer',
            background: 'none',
            padding: 2,
          }}
        />
        <input
          type="text"
          value={value}
          onChange={e => {
            const v = e.target.value
            if (/^#[0-9a-fA-F]{0,6}$/.test(v)) onChange(v)
          }}
          maxLength={7}
          style={{
            background: vars.color.bgSurface,
            border: `1px solid ${vars.color.borderDefault}`,
            borderRadius: 6,
            color: vars.color.textPrimary,
            fontSize: 13,
            padding: '6px 10px',
            width: 90,
            fontFamily: vars.font.mono,
          }}
        />
        {ratio !== null && (
          <span style={{
            fontSize: 11, fontWeight: 600,
            padding: '2px 7px', borderRadius: 4,
            background: aaPass ? vars.color.successMuted : vars.color.dangerMuted,
            color: aaPass ? vars.color.success : vars.color.danger,
          }}>
            {ratio.toFixed(2)}:1 {aaPass ? 'AA ✓' : 'AA ✗'}
          </span>
        )}
      </div>
    </div>
  )
}
