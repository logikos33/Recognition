/**
 * SurfacesEditorSection — seção colapsável "Containers & Superfícies" do
 * editor White-Label (WS1). 7 cores de contêiner com reset por seção.
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight, RotateCcw } from 'lucide-react'
import { vars } from '../../../styles/theme.css'
import { RECOGNITION_DEFAULT_SURFACES } from '../../../theme/tenant-theme/defaults'
import type { TenantSurfaceOverrides } from '../../../theme/tenant-theme/types'
import { Button } from '../../../components/ui/Button/Button'
import { ColorPicker } from './ColorPicker'

interface SurfacesEditorSectionProps {
  value: TenantSurfaceOverrides | undefined
  onChange: (next: TenantSurfaceOverrides | undefined) => void
}

const FIELDS: Array<{ key: keyof TenantSurfaceOverrides; label: string }> = [
  { key: 'bgBase', label: 'Fundo base do app' },
  { key: 'bgSurface', label: 'Superfície / painel' },
  { key: 'bgElevated', label: 'Elevado (modais, dropdowns)' },
  { key: 'bgCard', label: 'Card' },
  { key: 'textPrimary', label: 'Texto primário' },
  { key: 'textSecondary', label: 'Texto secundário' },
  { key: 'border', label: 'Borda' },
]

export function SurfacesEditorSection({ value, onChange }: SurfacesEditorSectionProps) {
  const [open, setOpen] = useState(false)
  const hasCustom = Boolean(value && Object.values(value).some(Boolean))

  function setField(key: keyof TenantSurfaceOverrides, hex: string) {
    onChange({ ...value, [key]: hex })
  }

  return (
    <div style={{ borderTop: `1px solid ${vars.color.borderSubtle}`, paddingTop: 16 }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          background: 'transparent',
          border: 'none',
          padding: 0,
          cursor: 'pointer',
          color: vars.color.textPrimary,
          fontSize: 13,
          fontWeight: 600,
        }}
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        Containers &amp; Superfícies
        {hasCustom && (
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: vars.color.primary,
              background: vars.color.primaryAlpha,
              borderRadius: 4,
              padding: '1px 6px',
            }}
          >
            customizado
          </span>
        )}
      </button>

      {open && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 14 }}>
          <p style={{ margin: 0, fontSize: 12, color: vars.color.textMuted }}>
            Cores de fundo, texto e borda dos contêineres (painéis, cards e modais).
            Deixe no padrão Recognition se não precisar customizar.
          </p>
          {FIELDS.map(({ key, label }) => (
            <ColorPicker
              key={key}
              label={label}
              value={value?.[key] ?? RECOGNITION_DEFAULT_SURFACES[key]}
              onChange={(hex) => setField(key, hex)}
              bgBase={value?.bgBase ?? RECOGNITION_DEFAULT_SURFACES.bgBase}
            />
          ))}
          <div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onChange(undefined)}
              disabled={!hasCustom}
            >
              <RotateCcw size={12} /> Restaurar padrão da seção
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
