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
      primary: '#16a34a',
      primaryHover: '#15803d',
      accent: '#ea580c',
    },
  },

  // CATH — azul corporativo
  cath: {
    brand: {
      productName: 'CATH Vision',
    },
    colors: {
      primary: '#2563eb',
      primaryHover: '#1d4ed8',
      accent: '#f59e0b',
    },
  },
}

/** Retorna overrides de um tenant pelo ID. Fallback para logikos. */
export function getMockTenantOverrides(tenantId: string): TenantThemeOverrides {
  return TENANT_MOCKS[tenantId] ?? TENANT_MOCKS.logikos
}
