import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, RotateCcw, Save, Eye } from 'lucide-react'
import { TENANT_MOCKS } from '../../../theme/tenant-theme/mockData'
import { resolveTheme } from '../../../theme/tenant-theme/resolver'
import type { TenantThemeOverrides } from '../../../theme/tenant-theme/types'
import { TenantBrandingEditor } from '../components/TenantBrandingEditor'
import { BrandingPreview } from '../components/BrandingPreview'
import { useToast } from '../../../components/ui/Toast/useToast'

const TENANT_LABELS: Record<string, string> = {
  logikos: 'Logikos',
  rvb: 'RVB Isolantes',
  cath: 'CATH',
}

function storageKey(id: string) { return `recognition-branding-${id}` }

function loadOverrides(tenantId: string): TenantThemeOverrides {
  try {
    const raw = localStorage.getItem(storageKey(tenantId))
    return raw ? JSON.parse(raw) : (TENANT_MOCKS[tenantId] ?? TENANT_MOCKS.logikos)
  } catch {
    return TENANT_MOCKS[tenantId] ?? TENANT_MOCKS.logikos
  }
}

export function AdminBrandingEditorPage() {
  const { id = 'logikos' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const toast = useToast()

  const [overrides, setOverrides] = useState<TenantThemeOverrides>(() => loadOverrides(id))
  const [isPreviewing, setIsPreviewing] = useState(false)

  useEffect(() => {
    setOverrides(loadOverrides(id))
  }, [id])

  function handleSave() {
    localStorage.setItem(storageKey(id), JSON.stringify(overrides))
    toast.success('Branding salvo com sucesso')
  }

  function handleReset() {
    const defaults = TENANT_MOCKS[id] ?? TENANT_MOCKS.logikos
    setOverrides(defaults)
    localStorage.removeItem(storageKey(id))
    toast.info('Branding resetado para o padrão')
    removePreview()
  }

  function applyPreview() {
    const { cssVars } = resolveTheme(overrides)
    const style = document.getElementById('recognition-tenant-theme')
    if (style) {
      const vars = Object.entries(cssVars).map(([k, v]) => `${k}: ${v};`).join(' ')
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
  const tenantLabel = TENANT_LABELS[id] ?? id

  return (
    <div style={{ padding: 32, maxWidth: 1100 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
        <button
          onClick={() => navigate('/admin/branding/tenants')}
          style={{ background: 'transparent', border: 'none', color: '#668096', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, padding: 0 }}
        >
          <ArrowLeft size={14} /> Tenants
        </button>
        <span style={{ color: '#334155' }}>/</span>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f0f4f8' }}>{tenantLabel}</h2>
        {isPreviewing && (
          <span style={{ background: 'rgba(6,182,212,0.12)', color: '#06b6d4', fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4 }}>
            Visualizando
          </span>
        )}
      </div>
      <p style={{ color: '#668096', fontSize: 13, margin: '0 0 28px' }}>
        Personalize a identidade visual deste tenant. O preview reflete as mudanças em tempo real.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 32, alignItems: 'start' }}>
        {/* Editor */}
        <div style={{ background: '#111318', border: '1px solid #1e2730', borderRadius: 10, padding: 24 }}>
          <h3 style={{ margin: '0 0 20px', fontSize: 15, fontWeight: 600, color: '#f0f4f8' }}>Configurações de Marca</h3>
          <TenantBrandingEditor value={overrides} onChange={setOverrides} />

          {/* Actions */}
          <div style={{ marginTop: 28, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button
              onClick={handleSave}
              style={{ background: '#06b6d4', border: 'none', borderRadius: 6, color: '#fff', padding: '8px 18px', cursor: 'pointer', fontSize: 13, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <Save size={13} /> Salvar
            </button>
            {isPreviewing ? (
              <button
                onClick={removePreview}
                style={{ background: 'rgba(6,182,212,0.1)', border: '1px solid rgba(6,182,212,0.3)', borderRadius: 6, color: '#06b6d4', padding: '8px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <Eye size={13} /> Sair do preview
              </button>
            ) : (
              <button
                onClick={applyPreview}
                style={{ background: 'transparent', border: '1px solid #2a3545', borderRadius: 6, color: '#8ba3bc', padding: '8px 16px', cursor: 'pointer', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <Eye size={13} /> Visualizar como tenant
              </button>
            )}
            <button
              onClick={handleReset}
              style={{ background: 'transparent', border: '1px solid #1e2730', borderRadius: 6, color: '#668096', padding: '8px 16px', cursor: 'pointer', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <RotateCcw size={13} /> Resetar padrão
            </button>
          </div>
        </div>

        {/* Preview */}
        <div style={{ background: '#111318', border: '1px solid #1e2730', borderRadius: 10, padding: 20, position: 'sticky', top: 20 }}>
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
