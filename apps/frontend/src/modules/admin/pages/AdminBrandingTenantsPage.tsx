import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, Palette } from 'lucide-react'
import { adminService } from '../services/adminService'
import type { Tenant, TenantBranding } from '../types/admin'

const DEFAULT_BRANDING: TenantBranding = {
  product_name: 'Recognition',
  color_primary: '#06b6d4',
  color_secondary: '#ea580c',
  logo_url: null,
  favicon_url: null,
}

export function AdminBrandingTenantsPage() {
  const navigate = useNavigate()
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [brandingMap, setBrandingMap] = useState<Record<string, TenantBranding>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminService.getTenants()
      .then(async (items) => {
        setTenants(items)
        // Load branding for each tenant in parallel (best-effort)
        const entries = await Promise.allSettled(
          items.map((t) =>
            adminService.getTenantBranding(t.id)
              .then((b) => ({ id: t.id, branding: b }))
              .catch(() => ({ id: t.id, branding: DEFAULT_BRANDING })),
          ),
        )
        const map: Record<string, TenantBranding> = {}
        for (const result of entries) {
          if (result.status === 'fulfilled') {
            map[result.value.id] = result.value.branding
          }
        }
        setBrandingMap(map)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])


  if (loading) {
    return (
      <div style={{ padding: 32, color: '#668096', fontSize: 13 }}>
        Carregando tenants...
      </div>
    )
  }

  return (
    <div style={{ padding: 32, maxWidth: 720 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <Palette size={20} style={{ color: '#06b6d4' }} />
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f0f4f8' }}>
          Identidade Visual por Tenant
        </h2>
      </div>
      <p style={{ color: '#668096', fontSize: 13, margin: '0 0 28px' }}>
        Configure cores, logo e nome do produto por tenant. As alterações são salvas no banco de dados.
      </p>

      {tenants.length === 0 && (
        <p style={{ color: '#668096', fontSize: 13 }}>Nenhum tenant encontrado.</p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {tenants.map((t) => {
          const branding = brandingMap[t.id] ?? DEFAULT_BRANDING
          const primary = branding.color_primary ?? '#06b6d4'
          const secondary = branding.color_secondary ?? '#ea580c'
          const productName = branding.product_name ?? 'Recognition'
          const hasCustom = Boolean(
            brandingMap[t.id] &&
            (branding.product_name !== 'Recognition' ||
              branding.color_primary !== '#06b6d4' ||
              branding.logo_url),
          )

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
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#2a3545')}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#1e2730')}
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
                    background: secondary,
                    border: '1px solid rgba(255,255,255,0.08)',
                  }}
                />
              </div>

              {/* Info */}
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: '#f0f4f8' }}>{t.name}</div>
                <div style={{ fontSize: 12, color: '#668096', marginTop: 2 }}>
                  {productName}
                  {!t.is_active && (
                    <span style={{ marginLeft: 8, color: '#ef4444', fontSize: 11 }}>• Suspenso</span>
                  )}
                  {hasCustom && (
                    <span style={{ marginLeft: 8, color: '#06b6d4', fontSize: 11 }}>• Customizado</span>
                  )}
                </div>
              </div>

              {/* Logo preview */}
              {branding.logo_url && (
                <img
                  src={branding.logo_url}
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
