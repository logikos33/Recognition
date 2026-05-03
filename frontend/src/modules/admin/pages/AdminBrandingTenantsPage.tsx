import { useNavigate } from 'react-router-dom'
import { Palette, ChevronRight } from 'lucide-react'
import { TENANT_MOCKS } from '../../../theme/tenant-theme/mockData'
import type { TenantThemeOverrides } from '../../../theme/tenant-theme/types'

const TENANT_LABELS: Record<string, string> = {
  logikos: 'Logikos',
  rvb: 'RVB Isolantes',
  cath: 'CATH',
}

function loadSavedOverrides(tenantId: string): TenantThemeOverrides {
  try {
    const raw = localStorage.getItem(`recognition-branding-${tenantId}`)
    return raw ? JSON.parse(raw) : TENANT_MOCKS[tenantId] ?? TENANT_MOCKS.logikos
  } catch {
    return TENANT_MOCKS[tenantId] ?? TENANT_MOCKS.logikos
  }
}

export function AdminBrandingTenantsPage() {
  const navigate = useNavigate()

  const tenants = Object.keys(TENANT_MOCKS).map(id => ({
    id,
    label: TENANT_LABELS[id] ?? id,
    overrides: loadSavedOverrides(id),
  }))

  return (
    <div style={{ padding: 32, maxWidth: 720 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <Palette size={20} style={{ color: '#06b6d4' }} />
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f0f4f8' }}>Identidade Visual por Tenant</h2>
      </div>
      <p style={{ color: '#668096', fontSize: 13, margin: '0 0 28px' }}>
        Configure cores, logo e nome do produto por tenant. As alterações são salvas localmente.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {tenants.map(t => {
          const primary = t.overrides.colors?.primary ?? '#06b6d4'
          const accent = t.overrides.colors?.accent ?? '#ea580c'
          const name = t.overrides.brand.productName ?? 'Recognition'
          const hasCustom = Boolean(localStorage.getItem(`recognition-branding-${t.id}`))

          return (
            <div
              key={t.id}
              onClick={() => navigate(`/admin/branding/tenants/${t.id}`)}
              style={{
                background: '#111318',
                border: '1px solid #1e2730',
                borderRadius: 10,
                padding: '14px 18px',
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                cursor: 'pointer',
                transition: 'border-color 0.15s',
              }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = '#2a3545')}
              onMouseLeave={e => (e.currentTarget.style.borderColor = '#1e2730')}
            >
              {/* Color swatches */}
              <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                <div style={{ width: 24, height: 24, borderRadius: 4, background: primary, border: '1px solid rgba(255,255,255,0.08)' }} />
                <div style={{ width: 24, height: 24, borderRadius: 4, background: accent, border: '1px solid rgba(255,255,255,0.08)' }} />
              </div>

              {/* Info */}
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: '#f0f4f8' }}>{t.label}</div>
                <div style={{ fontSize: 12, color: '#668096', marginTop: 2 }}>
                  {name}
                  {hasCustom && <span style={{ marginLeft: 8, color: '#06b6d4', fontSize: 11 }}>• Customizado</span>}
                </div>
              </div>

              {/* Logo preview */}
              {t.overrides.brand.logoUrl && (
                <img
                  src={t.overrides.brand.logoUrl}
                  alt="logo"
                  style={{ height: 28, maxWidth: 80, objectFit: 'contain', opacity: 0.8 }}
                />
              )}

              <ChevronRight size={16} style={{ color: '#334155', flexShrink: 0 }} />
            </div>
          )
        })}
      </div>

      <div style={{ marginTop: 24, display: 'flex', gap: 10 }}>
        <button
          onClick={() => navigate('/admin/branding/default')}
          style={{ background: 'transparent', border: '1px solid #1e2730', borderRadius: 6, color: '#8ba3bc', padding: '8px 16px', cursor: 'pointer', fontSize: 13 }}
        >
          Ver tema padrão
        </button>
        <button
          onClick={() => navigate('/admin/branding/sandbox')}
          style={{ background: 'transparent', border: '1px solid #1e2730', borderRadius: 6, color: '#8ba3bc', padding: '8px 16px', cursor: 'pointer', fontSize: 13 }}
        >
          Abrir Sandbox
        </button>
      </div>
    </div>
  )
}
