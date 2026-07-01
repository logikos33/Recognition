import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Eye, RotateCcw, Save } from 'lucide-react'
import { adminService } from '../services/adminService'
import { resolveTheme } from '../../../theme/tenant-theme/resolver'
import type { TenantThemeOverrides } from '../../../theme/tenant-theme/types'
import type { TenantBranding } from '../types/admin'
import { TenantBrandingEditor } from '../components/TenantBrandingEditor'
import { BrandingPreview } from '../components/BrandingPreview'
import { useToast } from '../../../components/ui/Toast/useToast'

const DEFAULT_BRANDING: TenantBranding = {
  product_name: 'Recognition',
  color_primary: '#06b6d4',
  color_secondary: '#ea580c',
  logo_url: null,
  favicon_url: null,
}

/** Convert API TenantBranding → TenantThemeOverrides (resolver format). */
function brandingToOverrides(b: TenantBranding): TenantThemeOverrides {
  return {
    brand: {
      productName: b.product_name ?? 'Recognition',
      logoUrl: b.logo_url ?? undefined,
    },
    colors: {
      primary: b.color_primary ?? undefined,
      accent:  b.color_secondary ?? undefined,
    },
  }
}

/** Convert TenantThemeOverrides → API TenantBranding. */
function overridesToBranding(o: TenantThemeOverrides): Partial<TenantBranding> {
  return {
    product_name:    o.brand.productName  ?? 'Recognition',
    color_primary:   o.colors?.primary    ?? '#06b6d4',
    color_secondary: o.colors?.accent     ?? '#ea580c',
    logo_url:        o.brand.logoUrl      ?? null,
  }
}

export function AdminBrandingEditorPage() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const toast = useToast()

  const [tenantName, setTenantName] = useState<string>(id)
  const [overrides, setOverrides] = useState<TenantThemeOverrides>(
    brandingToOverrides(DEFAULT_BRANDING),
  )
  const [isPreviewing, setIsPreviewing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [loading, setLoading] = useState(true)

  // Carrega branding da API ao abrir
  useEffect(() => {
    if (!id) return
    setLoading(true)

    Promise.all([
      adminService.getTenant(id).catch(() => null),
      adminService.getTenantBranding(id).catch(() => DEFAULT_BRANDING),
    ]).then(([tenant, b]) => {
      if (tenant) setTenantName(tenant.name)
      setOverrides(brandingToOverrides(b ?? DEFAULT_BRANDING))
    }).finally(() => setLoading(false))
  }, [id])

  async function handleSave() {
    if (!id) return
    setIsSaving(true)
    try {
      await adminService.updateTenantBranding(id, overridesToBranding(overrides))
      toast.success('Branding salvo com sucesso')
    } catch {
      toast.error('Erro ao salvar branding')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleReset() {
    if (!id) return
    try {
      await adminService.updateTenantBranding(id, DEFAULT_BRANDING)
      setOverrides(brandingToOverrides(DEFAULT_BRANDING))
      removePreview()
      toast.info('Branding resetado para o padrão')
    } catch {
      toast.error('Erro ao resetar branding')
    }
  }

  async function handleLogoUpload(file: File) {
    if (!id) return
    setIsUploading(true)
    try {
      const { logo_url } = await adminService.uploadBrandingLogo(id, file)
      setOverrides((prev) => ({
        ...prev,
        brand: { ...prev.brand, logoUrl: logo_url },
      }))
      toast.success('Logo enviado com sucesso')
    } catch {
      toast.error('Erro no upload do logo')
    } finally {
      setIsUploading(false)
    }
  }

  function applyPreview() {
    const { cssVars } = resolveTheme(overrides)
    const style = document.getElementById('recognition-tenant-theme')
    if (style) {
      const vars = Object.entries(cssVars)
        .map(([k, v]) => `${k}: ${v};`)
        .join(' ')
      style.textContent = `:root { ${vars} }`
    }
    setIsPreviewing(true)
    toast.info(`Visualizando como "${overrides.brand.productName ?? 'Recognition'}"`)
  }

  function removePreview() {
    const style = document.getElementById('recognition-tenant-theme')
    if (style) style.textContent = ''
    setIsPreviewing(false)
  }

  if (loading) {
    return (
      <div style={{ padding: 32, color: '#668096', fontSize: 13 }}>
        Carregando branding...
      </div>
    )
  }

  const primary = overrides.colors?.primary ?? '#06b6d4'
  const accent  = overrides.colors?.accent  ?? '#ea580c'
  const productName = overrides.brand.productName ?? 'Recognition'

  return (
    <div style={{ padding: 32, maxWidth: 1100 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
        <button
          onClick={() => navigate('/admin/branding/tenants')}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#668096',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            fontSize: 13,
            padding: 0,
          }}
        >
          <ArrowLeft size={14} /> Tenants
        </button>
        <span style={{ color: '#334155' }}>/</span>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f0f4f8' }}>
          {tenantName}
        </h2>
        {isPreviewing && (
          <span
            style={{
              background: 'rgba(6,182,212,0.12)',
              color: '#06b6d4',
              fontSize: 11,
              fontWeight: 600,
              padding: '2px 8px',
              borderRadius: 4,
            }}
          >
            Visualizando
          </span>
        )}
      </div>
      <p style={{ color: '#668096', fontSize: 13, margin: '0 0 28px' }}>
        Personalize a identidade visual deste tenant. Salva no banco de dados; aplicado em tempo real no próximo boot do frontend.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 32, alignItems: 'start' }}>
        {/* Editor */}
        <div
          style={{
            background: '#111318',
            border: '1px solid #1e2730',
            borderRadius: 10,
            padding: 24,
          }}
        >
          <h3 style={{ margin: '0 0 20px', fontSize: 15, fontWeight: 600, color: '#f0f4f8' }}>
            Configurações de Marca
          </h3>
          <TenantBrandingEditor
            value={overrides}
            onChange={setOverrides}
            onLogoUpload={handleLogoUpload}
            isUploadingLogo={isUploading}
          />

          {/* Actions */}
          <div style={{ marginTop: 28, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button
              onClick={handleSave}
              disabled={isSaving}
              style={{
                background: '#06b6d4',
                border: 'none',
                borderRadius: 6,
                color: '#fff',
                padding: '8px 18px',
                cursor: isSaving ? 'not-allowed' : 'pointer',
                fontSize: 13,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                opacity: isSaving ? 0.7 : 1,
              }}
            >
              <Save size={13} /> {isSaving ? 'Salvando...' : 'Salvar'}
            </button>

            {isPreviewing ? (
              <button
                onClick={removePreview}
                style={{
                  background: 'rgba(6,182,212,0.1)',
                  border: '1px solid rgba(6,182,212,0.3)',
                  borderRadius: 6,
                  color: '#06b6d4',
                  padding: '8px 16px',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <Eye size={13} /> Sair do preview
              </button>
            ) : (
              <button
                onClick={applyPreview}
                style={{
                  background: 'transparent',
                  border: '1px solid #2a3545',
                  borderRadius: 6,
                  color: '#8ba3bc',
                  padding: '8px 16px',
                  cursor: 'pointer',
                  fontSize: 13,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <Eye size={13} /> Visualizar como tenant
              </button>
            )}

            <button
              onClick={handleReset}
              style={{
                background: 'transparent',
                border: '1px solid #1e2730',
                borderRadius: 6,
                color: '#668096',
                padding: '8px 16px',
                cursor: 'pointer',
                fontSize: 13,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <RotateCcw size={13} /> Resetar padrão
            </button>
          </div>
        </div>

        {/* Preview */}
        <div
          style={{
            background: '#111318',
            border: '1px solid #1e2730',
            borderRadius: 10,
            padding: 20,
            position: 'sticky',
            top: 20,
          }}
        >
          <BrandingPreview
            primary={primary}
            accent={accent}
            productName={productName}
            logoUrl={overrides.brand.logoUrl}
          />
        </div>
      </div>
    </div>
  )
}
