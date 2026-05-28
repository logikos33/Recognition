/**
 * TenantThemeOverrides — overrides de identidade visual por tenant.
 * Sprint 1: estrutura preparada; ativação real via API no Sprint 6.
 */
export interface TenantThemeOverrides {
  brand: {
    /** Override do nome "Recognition" exibido no header/login */
    productName?: string
    /** URL ou data URL do logo principal */
    logoUrl?: string
    /** URL ou data URL do logo monocromático (sidebar colapsada) */
    logoMonoUrl?: string
  }
  colors?: {
    /** Cor primária da marca do tenant (hex) */
    primary?: string
    /** Hover da cor primária (hex) — gerado automaticamente se omitido */
    primaryHover?: string
    /** Cor de acento secundária (hex) */
    accent?: string
  }
}

export interface ResolvedTenantTheme {
  overrides: TenantThemeOverrides
  cssVars: Record<string, string>
}
