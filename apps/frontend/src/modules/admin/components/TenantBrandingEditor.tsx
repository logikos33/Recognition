/**
 * TenantBrandingEditor — editor White-Label do tenant (WS1).
 * Seções: Marca (nome, cores, logo, favicon) e Containers & Superfícies.
 * 100% tokenizado — este editor é o primeiro exemplo do padrão.
 */
import { RotateCcw } from 'lucide-react'
import { vars } from '../../../styles/theme.css'
import type { TenantThemeOverrides } from '../../../theme/tenant-theme/types'
import {
  RECOGNITION_DEFAULT_PRIMARY,
  RECOGNITION_DEFAULT_ACCENT,
} from '../../../theme/tenant-theme/defaults'
import { Button } from '../../../components/ui/Button/Button'
import { ColorPicker } from './ColorPicker'
import { BrandingAssetUpload } from './BrandingAssetUpload'
import { SurfacesEditorSection } from './SurfacesEditorSection'

interface TenantBrandingEditorProps {
  value: TenantThemeOverrides
  onChange: (next: TenantThemeOverrides) => void
  /** Upload do logo via API (parent atualiza value.brand.logoUrl). */
  onLogoUpload?: (file: File) => void
  isUploadingLogo?: boolean
  /** Upload do favicon via API (parent atualiza value.brand.faviconUrl). */
  onFaviconUpload?: (file: File) => void
  isUploadingFavicon?: boolean
}

export function TenantBrandingEditor({
  value,
  onChange,
  onLogoUpload,
  isUploadingLogo = false,
  onFaviconUpload,
  isUploadingFavicon = false,
}: TenantBrandingEditorProps) {
  const primary = value.colors?.primary ?? RECOGNITION_DEFAULT_PRIMARY
  const accent = value.colors?.accent ?? RECOGNITION_DEFAULT_ACCENT
  const productName = value.brand.productName ?? 'Recognition'
  const brandColorsCustom = Boolean(value.colors?.primary || value.colors?.accent)

  function readAsDataUrl(file: File, apply: (dataUrl: string) => void) {
    const reader = new FileReader()
    reader.onload = (ev) => apply(ev.target?.result as string)
    reader.readAsDataURL(file)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Product name */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 12, color: vars.color.textSecondary, fontWeight: 500 }}>
          Nome do produto
        </label>
        <input
          type="text"
          value={productName}
          onChange={(e) => onChange({ ...value, brand: { ...value.brand, productName: e.target.value } })}
          placeholder="Recognition"
          style={{
            background: vars.color.bgSurface,
            border: `1px solid ${vars.color.borderDefault}`,
            borderRadius: 6,
            color: vars.color.textPrimary,
            fontSize: 14,
            padding: '8px 12px',
            outline: 'none',
          }}
        />
      </div>

      {/* Brand colors */}
      <ColorPicker
        label="Cor primária"
        value={primary}
        onChange={(hex) => onChange({ ...value, colors: { ...value.colors, primary: hex } })}
      />
      <ColorPicker
        label="Cor de acento"
        value={accent}
        onChange={(hex) => onChange({ ...value, colors: { ...value.colors, accent: hex } })}
      />
      <div>
        <Button
          variant="ghost"
          size="sm"
          disabled={!brandColorsCustom}
          onClick={() => onChange({ ...value, colors: {} })}
        >
          <RotateCcw size={12} /> Restaurar cores da marca
        </Button>
      </div>

      {/* Logo upload */}
      <BrandingAssetUpload
        label="Logo (PNG / SVG / JPEG — máx 2 MB)"
        url={value.brand.logoUrl}
        isUploading={isUploadingLogo}
        onSelect={(file) => {
          if (onLogoUpload) {
            onLogoUpload(file)
          } else {
            // Fallback dev/sandbox: data URL inline
            readAsDataUrl(file, (dataUrl) =>
              onChange({ ...value, brand: { ...value.brand, logoUrl: dataUrl } }),
            )
          }
        }}
        onClear={() => onChange({ ...value, brand: { ...value.brand, logoUrl: undefined } })}
      />

      {/* Favicon upload (WS1) */}
      <BrandingAssetUpload
        label="Favicon (PNG / SVG — máx 2 MB)"
        url={value.brand.faviconUrl}
        isUploading={isUploadingFavicon}
        accept="image/png,image/svg+xml,image/webp"
        previewHeight={20}
        onSelect={(file) => {
          if (onFaviconUpload) {
            onFaviconUpload(file)
          } else {
            readAsDataUrl(file, (dataUrl) =>
              onChange({ ...value, brand: { ...value.brand, faviconUrl: dataUrl } }),
            )
          }
        }}
        onClear={() => onChange({ ...value, brand: { ...value.brand, faviconUrl: undefined } })}
      />

      {/* Containers & Superfícies (WS1) */}
      <SurfacesEditorSection
        value={value.surfaces}
        onChange={(surfaces) => onChange({ ...value, surfaces })}
      />
    </div>
  )
}
