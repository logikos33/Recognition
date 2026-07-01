import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Palette, ChevronRight } from 'lucide-react'
import { api } from '../../../services/api'
import type { TenantThemeOverrides } from '../../../theme/tenant-theme/types'

interface TenantBrandingRow {
  id: string
  name: string
  slug: string
  is_active: boolean
  branding: Partial<TenantThemeOverrides>
}

interface ListResponse {
  status: string
  data: { tenants: TenantBrandingRow[] }
}

export function AdminBrandingTenantsPage() {
  const navigate = useNavigate()
  const [tenants, setTenants] = useState<TenantBrandingRow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .get<ListResponse>('/v1/admin/branding/tenants')
      .then(res => {
        if (res.status === 'success') setTenants(res.data.tenants)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={{ padding: 32, maxWidth: 720 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <Palette size={20} style={{ color: '#06b6d4' }} />
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f0f4f8' }}>
          Identidade Visual por Tenant
        </h2>
      </div>
      <p style={{ color: '#668096', fontSize: 13, margin: '0 0 28px' }}>
        Configure cores, logo e nome do produto por tenant. As alterações são persistidas na
        plataforma.
      </p>

      {loading && (
        <p style={{ color: '#668096', fontSize: 13 }}>Carregando tenants...</p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {tenants.map(t => {
          const primary = t.branding?.colors?.primary ?? '#06b6d4'
          const accent = t.branding?.colors?.accent ?? '#ea580c'
          const productName = t.branding?.brand?.productName ?? 'Recognition'
          const hasCustom = Boolean(t.branding && Object.keys(t.branding).length > 0)

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
                <div
                  style={{
                    width: 24,
                    height: 24,
                    borderRadius: 4,
                    background: primary,
                    border: '1px solid rgba(255,255,255,0.08)',
                  }}
                />
                <div
                  style={{
                    width: 24,
                    height: 24,
                    borderRadius: 4,
                    background: accent,
                    border: '1px solid rgba(255,255,255,0.08)',
                  }}
                />
              </div>

              {/* Info */}
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: '#f0f4f8' }}>{t.name}</div>
                <div style={{ fontSize: 12, color: '#668096', marginTop: 2 }}>
                  {productName}
                  {hasCustom && (
                    <span style={{ marginLeft: 8, color: '#06b6d4', fontSize: 11 }}>
                      • Customizado
                    </span>
                  )}
                </div>
              </div>

              {/* Logo preview */}
              {t.branding?.brand?.logoUrl && (
                <img
                  src={t.branding.brand.logoUrl}
                  alt="logo"
                  style={{
                    height: 28,
                    maxWidth: 80,
                    objectFit: 'contain',
                    opacity: 0.8,
                  }}
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
          style={{
            background: 'transparent',
            border: '1px solid #1e2730',
            borderRadius: 6,
            color: '#8ba3bc',
            padding: '8px 16px',
            cursor: 'pointer',
            fontSize: 13,
          }}
        >
          Ver tema padrão
        </button>
        <button
          onClick={() => navigate('/admin/branding/sandbox')}
          style={{
            background: 'transparent',
            border: '1px solid #1e2730',
            borderRadius: 6,
            color: '#8ba3bc',
            padding: '8px 16px',
            cursor: 'pointer',
            fontSize: 13,
          }}
        >
          Abrir Sandbox
        </button>
      </div>
    </div>
  )
}
