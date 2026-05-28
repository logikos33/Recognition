import { useMemo } from 'react'

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

export function ColorPicker({ label, value, onChange, bgBase = '#0a0c10' }: ColorPickerProps) {
  const ratio = useMemo(() => {
    if (!value || value.length < 7) return null
    try { return contrastRatio(value, bgBase) } catch { return null }
  }, [value, bgBase])

  const aaPass = ratio !== null && ratio >= 4.5

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 12, color: '#8ba3bc', fontWeight: 500 }}>{label}</label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <input
          type="color"
          value={value}
          onChange={e => onChange(e.target.value)}
          style={{
            width: 36, height: 36,
            border: '1px solid #1e2730',
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
            background: '#111318',
            border: '1px solid #1e2730',
            borderRadius: 6,
            color: '#f0f4f8',
            fontSize: 13,
            padding: '6px 10px',
            width: 90,
            fontFamily: 'monospace',
          }}
        />
        {ratio !== null && (
          <span style={{
            fontSize: 11, fontWeight: 600,
            padding: '2px 7px', borderRadius: 4,
            background: aaPass ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)',
            color: aaPass ? '#10b981' : '#ef4444',
          }}>
            {ratio.toFixed(2)}:1 {aaPass ? 'AA ✓' : 'AA ✗'}
          </span>
        )}
      </div>
    </div>
  )
}
