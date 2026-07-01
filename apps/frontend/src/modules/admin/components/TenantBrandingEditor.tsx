import { useRef } from 'react'
import { Loader2, Upload, X } from 'lucide-react'
import type { TenantThemeOverrides } from '../../../theme/tenant-theme/types'
import { ColorPicker } from './ColorPicker'

interface TenantBrandingEditorProps {
  value: TenantThemeOverrides
  onChange: (next: TenantThemeOverrides) => void
  /**
   * Called when user selects a logo file.
   * If provided, the file is passed to the parent for API upload rather than
   * being read as a data URL locally. After upload the parent updates `value.brand.logoUrl`.
   */
  onLogoUpload?: (file: File) => void
  isUploadingLogo?: boolean
}

const DEFAULT_PRIMARY = '#06b6d4'
const DEFAULT_ACCENT  = '#ea580c'

export function TenantBrandingEditor({
  value,
  onChange,
  onLogoUpload,
  isUploadingLogo = false,
}: TenantBrandingEditorProps) {
  const fileRef = useRef<HTMLInputElement>(null)

  const primary     = value.colors?.primary ?? DEFAULT_PRIMARY
  const accent      = value.colors?.accent  ?? DEFAULT_ACCENT
  const productName = value.brand.productName ?? 'Recognition'
  const logoUrl     = value.brand.logoUrl

  function setPrimary(hex: string) {
    onChange({ ...value, colors: { ...value.colors, primary: hex } })
  }

  function setAccent(hex: string) {
    onChange({ ...value, colors: { ...value.colors, accent: hex } })
  }

  function setProductName(name: string) {
    onChange({ ...value, brand: { ...value.brand, productName: name } })
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    if (onLogoUpload) {
      // Delegate to parent for API upload
      onLogoUpload(file)
    } else {
      // Fallback: inline data URL (dev/sandbox mode)
      const reader = new FileReader()
      reader.onload = (ev) => {
        const dataUrl = ev.target?.result as string
        onChange({ ...value, brand: { ...value.brand, logoUrl: dataUrl } })
      }
      reader.readAsDataURL(file)
    }

    // Reset input so the same file can be re-selected
    if (fileRef.current) fileRef.current.value = ''
  }

  function clearLogo() {
    onChange({ ...value, brand: { ...value.brand, logoUrl: undefined } })
    if (fileRef.current) fileRef.current.value = ''
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Product name */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 12, color: '#8ba3bc', fontWeight: 500 }}>
          Nome do produto
        </label>
        <input
          type="text"
          value={productName}
          onChange={(e) => setProductName(e.target.value)}
          placeholder="Recognition"
          style={{
            background: '#111318',
            border: '1px solid #1e2730',
            borderRadius: 6,
            color: '#f0f4f8',
            fontSize: 14,
            padding: '8px 12px',
            outline: 'none',
          }}
        />
      </div>

      {/* Colors */}
      <ColorPicker label="Cor primária" value={primary} onChange={setPrimary} />
      <ColorPicker label="Cor de acento" value={accent} onChange={setAccent} />

      {/* Logo upload */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 12, color: '#8ba3bc', fontWeight: 500 }}>
          Logo (PNG / SVG / JPEG — máx 2 MB)
        </label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {logoUrl ? (
            <>
              <img
                src={logoUrl}
                alt="logo preview"
                style={{
                  height: 36,
                  maxWidth: 120,
                  objectFit: 'contain',
                  border: '1px solid #1e2730',
                  borderRadius: 6,
                  padding: 4,
                  background: '#111318',
                }}
              />
              <button
                onClick={clearLogo}
                disabled={isUploadingLogo}
                style={{
                  background: 'rgba(239,68,68,0.1)',
                  border: '1px solid rgba(239,68,68,0.3)',
                  borderRadius: 6,
                  color: '#ef4444',
                  padding: '6px 10px',
                  cursor: isUploadingLogo ? 'not-allowed' : 'pointer',
                  fontSize: 12,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                <X size={12} /> Remover
              </button>
            </>
          ) : isUploadingLogo ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                color: '#668096',
                fontSize: 12,
              }}
            >
              <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />
              Enviando...
            </div>
          ) : (
            <button
              onClick={() => fileRef.current?.click()}
              style={{
                background: '#111318',
                border: '1px dashed #1e2730',
                borderRadius: 6,
                color: '#8ba3bc',
                padding: '10px 16px',
                cursor: 'pointer',
                fontSize: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <Upload size={13} /> Fazer upload
            </button>
          )}
          <input
            ref={fileRef}
            type="file"
            accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />
        </div>
      </div>
    </div>
  )
}
