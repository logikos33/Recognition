/**
 * AdminBrandingEditorPage — edição White-Label de um tenant (WS1).
 * Carrega/salva o formato FLAT (PUT /v1/admin/tenants/<id>/branding),
 * incluindo Containers & Superfícies, favicon e preview ao vivo.
 */
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Eye, RotateCcw, Save } from 'lucide-react'
import { vars } from '../../../styles/theme.css'
import { adminService } from '../services/adminService'
import { resolveTheme } from '../../../theme/tenant-theme/resolver'
import type { TenantThemeOverrides } from '../../../theme/tenant-theme/types'
import type { TenantBranding } from '../types/admin'
import { TenantBrandingEditor } from '../components/TenantBrandingEditor'
import { BrandingPreview } from '../components/BrandingPreview'
import { Button } from '../../../components/ui/Button/Button'
import { Panel } from '../../../components/ui/Panel/Panel'
import { useToast } from '../../../components/ui/Toast/useToast'
import {
  RECOGNITION_DEFAULT_PRIMARY,
  RECOGNITION_DEFAULT_ACCENT,
} from '../../../theme/tenant-theme/defaults'

const DEFAULT_BRANDING: TenantBranding = {
  product_name: 'Recognition',
  color_primary: RECOGNITION_DEFAULT_PRIMARY,
  color_secondary: RECOGNITION_DEFAULT_ACCENT,
  logo_url: null,
  favicon_url: null,
}

/** Convert API TenantBranding (flat) → TenantThemeOverrides (resolver format). */
function brandingToOverrides(b: TenantBranding): TenantThemeOverrides {
  return {
    brand: {
      productName: b.product_name ?? 'Recognition',
      logoUrl: b.logo_url ?? undefined,
      faviconUrl: b.favicon_url ?? undefined,
    },
    colors: {
      primary: b.color_primary ?? undefined,
      accent: b.color_secondary ?? undefined,
    },
    surfaces: {
      bgBase: b.color_bg_base ?? undefined,
      bgSurface: b.color_bg_surface ?? undefined,
      bgElevated: b.color_bg_elevated ?? undefined,
      bgCard: b.color_bg_card ?? undefined,
      textPrimary: b.color_text_primary ?? undefined,
      textSecondary: b.color_text_secondary ?? undefined,
      border: b.color_border ?? undefined,
    },
  }
}

/** Convert TenantThemeOverrides → API TenantBranding (flat snake_case). */
function overridesToBranding(o: TenantThemeOverrides): Partial<TenantBranding> {
  return {
    product_name: o.brand.productName ?? 'Recognition',
    color_primary: o.colors?.primary ?? RECOGNITION_DEFAULT_PRIMARY,
    color_secondary: o.colors?.accent ?? RECOGNITION_DEFAULT_ACCENT,
    logo_url: o.brand.logoUrl ?? null,
    favicon_url: o.brand.faviconUrl ?? null,
    color_bg_base: o.surfaces?.bgBase ?? null,
    color_bg_surface: o.surfaces?.bgSurface ?? null,
    color_bg_elevated: o.surfaces?.bgElevated ?? null,
    color_bg_card: o.surfaces?.bgCard ?? null,
    color_text_primary: o.surfaces?.textPrimary ?? null,
    color_text_secondary: o.surfaces?.textSecondary ?? null,
    color_border: o.surfaces?.border ?? null,
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
  const [isUploadingFavicon, setIsUploadingFavicon] = useState(false)
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
      const { logo_url } = await adminService.uploadBrandingLogo(id, file, 'logo')
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

  async function handleFaviconUpload(file: File) {
    if (!id) return
    setIsUploadingFavicon(true)
    try {
      const { favicon_url } = await adminService.uploadBrandingLogo(id, file, 'favicon')
      setOverrides((prev) => ({
        ...prev,
        brand: { ...prev.brand, faviconUrl: favicon_url },
      }))
      toast.success('Favicon enviado com sucesso')
    } catch {
      toast.error('Erro no upload do favicon')
    } finally {
      setIsUploadingFavicon(false)
    }
  }

  function applyPreview() {
    const { cssVars } = resolveTheme(overrides)
    const style = document.getElementById('recognition-tenant-theme')
    if (style) {
      const varLines = Object.entries(cssVars)
        .map(([k, v]) => `${k}: ${v};`)
        .join(' ')
      style.textContent = `:root { ${varLines} }`
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
      <div style={{ padding: 32, color: vars.color.textMuted, fontSize: 13 }}>
        Carregando branding...
      </div>
    )
  }

  const primary = overrides.colors?.primary ?? RECOGNITION_DEFAULT_PRIMARY
  const accent = overrides.colors?.accent ?? RECOGNITION_DEFAULT_ACCENT
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
            color: vars.color.textMuted,
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
        <span style={{ color: vars.color.textDim }}>/</span>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: vars.color.textPrimary }}>
          {tenantName}
        </h2>
        {isPreviewing && (
          <span
            style={{
              background: vars.color.primaryAlpha,
              color: vars.color.primary,
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
      <p style={{ color: vars.color.textMuted, fontSize: 13, margin: '0 0 28px' }}>
        Personalize a identidade visual deste tenant — marca, cores e containers.
        Salva no banco de dados; aplicado no próximo boot do frontend.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 32, alignItems: 'start' }}>
        {/* Editor */}
        <Panel variant="surface" title="Configurações de Marca">
          <TenantBrandingEditor
            value={overrides}
            onChange={setOverrides}
            onLogoUpload={handleLogoUpload}
            isUploadingLogo={isUploading}
            onFaviconUpload={handleFaviconUpload}
            isUploadingFavicon={isUploadingFavicon}
          />

          {/* Actions */}
          <div style={{ marginTop: 28, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Button variant="primary" onClick={handleSave} loading={isSaving}>
              <Save size={13} /> {isSaving ? 'Salvando...' : 'Salvar'}
            </Button>
            {isPreviewing ? (
              <Button variant="secondary" onClick={removePreview}>
                <Eye size={13} /> Sair do preview
              </Button>
            ) : (
              <Button variant="secondary" onClick={applyPreview}>
                <Eye size={13} /> Visualizar como tenant
              </Button>
            )}
            <Button variant="ghost" onClick={handleReset}>
              <RotateCcw size={13} /> Resetar padrão
            </Button>
          </div>
        </Panel>

        {/* Preview */}
        <div style={{ position: 'sticky', top: 20 }}>
          <Panel variant="surface" padding="md">
            <BrandingPreview
              primary={primary}
              accent={accent}
              productName={productName}
              logoUrl={overrides.brand.logoUrl}
              surfaces={overrides.surfaces}
            />
          </Panel>
        </div>
      </div>
    </div>
  )
}
