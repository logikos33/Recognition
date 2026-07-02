/**
 * BrandingAssetUpload — upload de logo/favicon do editor White-Label (WS1).
 * Estados: vazio → botão upload; enviando → spinner; preenchido → preview + remover.
 */
import { useRef } from 'react'
import { Loader2, Upload, X } from 'lucide-react'
import { vars } from '../../../styles/theme.css'

interface BrandingAssetUploadProps {
  label: string
  url?: string
  isUploading: boolean
  accept?: string
  previewHeight?: number
  onSelect: (file: File) => void
  onClear: () => void
}

export function BrandingAssetUpload({
  label,
  url,
  isUploading,
  accept = 'image/png,image/jpeg,image/gif,image/webp,image/svg+xml',
  previewHeight = 36,
  onSelect,
  onClear,
}: BrandingAssetUploadProps) {
  const fileRef = useRef<HTMLInputElement>(null)

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) onSelect(file)
    if (fileRef.current) fileRef.current.value = ''
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 12, color: vars.color.textSecondary, fontWeight: 500 }}>
        {label}
      </label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {url ? (
          <>
            <img
              src={url}
              alt={`${label} preview`}
              style={{
                height: previewHeight,
                maxWidth: 120,
                objectFit: 'contain',
                border: `1px solid ${vars.color.borderDefault}`,
                borderRadius: 6,
                padding: 4,
                background: vars.color.bgSurface,
              }}
            />
            <button
              onClick={onClear}
              disabled={isUploading}
              style={{
                background: vars.color.dangerMuted,
                border: `1px solid ${vars.color.danger}`,
                borderRadius: 6,
                color: vars.color.danger,
                padding: '6px 10px',
                cursor: isUploading ? 'not-allowed' : 'pointer',
                fontSize: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <X size={12} /> Remover
            </button>
          </>
        ) : isUploading ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: vars.color.textMuted, fontSize: 12 }}>
            <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />
            Enviando...
          </div>
        ) : (
          <button
            onClick={() => fileRef.current?.click()}
            style={{
              background: vars.color.bgSurface,
              border: `1px dashed ${vars.color.borderDefault}`,
              borderRadius: 6,
              color: vars.color.textSecondary,
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
          accept={accept}
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
      </div>
    </div>
  )
}
