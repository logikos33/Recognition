/**
 * Mock data para 3 tenants com identidades visuais distintas.
 * Sprint 1: usado para demonstrar white-label sem backend.
 * Sprint 6: substituído por chamada à API real.
 */
import type { TenantThemeOverrides } from './types'

export const TENANT_MOCKS: Record<string, TenantThemeOverrides> = {
  // Tenant padrão — sem overrides, usa Recognition puro
  logikos: {
    brand: {
      productName: 'Recognition',
    },
    colors: {},
  },

  // RVB Isolantes — verde industrial
  rvb: {
    brand: {
      productName: 'RVB Monitor',
    },
    colors: {
      primary: '#16a34a', // allow: tenant brand override
      primaryHover: '#15803d', // allow: tenant brand override
      accent: '#ea580c', // allow: tenant brand override
    },
  },

  // CATH — azul corporativo
  cath: {
    brand: {
      productName: 'CATH Vision',
    },
    colors: {
      primary: '#2563eb', // allow: tenant brand override
      primaryHover: '#1d4ed8', // allow: tenant brand override
      accent: '#f59e0b', // allow: tenant brand override
    },
  },
}

/** Retorna overrides de um tenant pelo ID. Fallback para logikos. */
export function getMockTenantOverrides(tenantId: string): TenantThemeOverrides {
  return TENANT_MOCKS[tenantId] ?? TENANT_MOCKS.logikos
}
