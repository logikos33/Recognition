import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, RotateCcw, Save, Eye } from 'lucide-react'
import { api } from '../../../services/api'
import { resolveTheme } from '../../../theme/tenant-theme/resolver'
import { TENANT_MOCKS } from '../../../theme/tenant-theme/mockData'
import type { TenantThemeOverrides } from '../../../theme/tenant-theme/types'
import { TenantBrandingEditor } from '../components/TenantBrandingEditor'
import { BrandingPreview } from '../components/BrandingPreview'
import { useToast } from '../../../components/ui/Toast/useToast'

const DEFAULT_OVERRIDES: TenantThemeOverrides = { brand: {} }

interface BrandingDetailResponse {
  status: string
  data: {
    tenant_id: string
    name: string
    slug: string
    branding: Partial<TenantThemeOverrides>
  }
}

interface SaveResponse {
  status: string
  data: { branding: Partial<TenantThemeOverrides>; tenant_id: string }
}

interface UploadResponse {
  status: string
  data: { url: string; key: string }
}

export function AdminBrandingEditorPage() {
  // id pode ser UUID (vindo da lista real) ou slug (URLs legadas de desenvolvimento)
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const toast = useToast()

  const [tenantName, setTenantName] = useState<string>(id)
  const [overrides, setOverrides] = useState<TenantThemeOverrides>(DEFAULT_OVERRIDES)
  const [isPreviewing, setIsPreviewing] = useState(false)
  const [saving, setSaving] = useState(false)

  // Carrega branding da API ao abrir
  useEffect(() => {
    if (!id) return
    api
      .get<BrandingDetailResponse>(`/v1/admin/branding/tenant/${id}`)
      .then(res => {
        if (res.status === 'success') {
          setTenantName(res.data.name)
          const b = res.data.branding
          if (b && typeof b.brand === 'object') {
            setOverrides(b as TenantThemeOverrides)
          }
        }
      })
      .catch(() => {
        // Fallback para mock de dev se a API não tiver o tenant (slug legado)
        const mock = TENANT_MOCKS[id]
        if (mock) {
          setTenantName(id)
          setOverrides(mock)
        }
      })
  }, [id])

  async function handleSave() {
    setSaving(true)
    try {
      let brandingToSave = overrides

      // Se o logo ainda é um data URL (edição local), sobe para R2 primeiro
      if (overrides.brand?.logoUrl?.startsWith('data:')) {
        try {
          const blob = await fetch(overrides.brand.logoUrl).then(r => r.blob())
          const fd = new FormData()
          fd.append('file', blob, 'logo')
          const uploadRes = await api.post<UploadResponse>('/v1/admin/branding/logo', fd)
          if (uploadRes.status === 'success') {
            brandingToSave = {
              ...brandingToSave,
              brand: { ...brandingToSave.brand, logoUrl: uploadRes.data.url },
            }
            setOverrides(brandingToSave)
          }
        } catch {
          toast.error('Erro ao fazer upload do logo — branding salvo sem imagem')
          brandingToSave = {
            ...brandingToSave,
            brand: { ...brandingToSave.brand, logoUrl: undefined },
          }
        }
      }

      const res = await api.put<SaveResponse>('/v1/admin/branding', {
        tenant_id: id,
        branding: brandingToSave,
      })
      if (res.status === 'success') {
        toast.success('Branding salvo com sucesso')
      }
    } catch {
      toast.error('Erro ao salvar branding')
    } finally {
      setSaving(false)
    }
  }

  async function handleReset() {
    try {
      await api.put<SaveResponse>('/v1/admin/branding', {
        tenant_id: id,
        branding: {},
      })
      setOverrides(DEFAULT_OVERRIDES)
      toast.info('Branding resetado para o padrão')
      removePreview()
    } catch {
      toast.error('Erro ao resetar branding')
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

  const primary = overrides.colors?.primary ?? '#06b6d4'
  const accent = overrides.colors?.accent ?? '#ea580c'
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
        Personalize a identidade visual deste tenant. O preview reflete as mudanças em tempo real.
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
          <TenantBrandingEditor value={overrides} onChange={setOverrides} />

          {/* Actions */}
          <div style={{ marginTop: 28, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{
                background: '#06b6d4',
                border: 'none',
                borderRadius: 6,
                color: '#fff',
                padding: '8px 18px',
                cursor: saving ? 'not-allowed' : 'pointer',
                fontSize: 13,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                opacity: saving ? 0.7 : 1,
              }}
            >
              <Save size={13} /> {saving ? 'Salvando...' : 'Salvar'}
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
