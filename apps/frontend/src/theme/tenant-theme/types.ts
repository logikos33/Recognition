/**
 * TenantThemeOverrides — overrides de identidade visual por tenant.
 * Sprint 1: estrutura preparada; ativação real via API no Sprint 6.
 * WS1 (Jul 2026): grupo `surfaces` — containers/superfícies configuráveis.
 */
export interface TenantSurfaceOverrides {
  /** Fundo base do app (hex) */
  bgBase?: string
  /** Superfícies: sidebar, topbar, painéis (hex) */
  bgSurface?: string
  /** Superfícies elevadas: modais, dropdowns (hex) */
  bgElevated?: string
  /** Cards e células de tabela (hex) */
  bgCard?: string
  /** Texto primário (hex) */
  textPrimary?: string
  /** Texto secundário (hex) — textMuted é derivado automaticamente */
  textSecondary?: string
  /** Borda padrão (hex) — subtle/strong são derivadas automaticamente */
  border?: string
}

export interface TenantThemeOverrides {
  brand: {
    /** Override do nome "Recognition" exibido no header/login */
    productName?: string
    /** URL ou data URL do logo principal */
    logoUrl?: string
    /** URL ou data URL do logo monocromático (sidebar colapsada) */
    logoMonoUrl?: string
    /** URL do favicon do tenant */
    faviconUrl?: string
  }
  colors?: {
    /** Cor primária da marca do tenant (hex) */
    primary?: string
    /** Hover da cor primária (hex) — gerado automaticamente se omitido */
    primaryHover?: string
    /** Cor de acento secundária (hex) */
    accent?: string
  }
  /** Containers & superfícies (WS1) — aplicados via CSS vars planas */
  surfaces?: TenantSurfaceOverrides
}

export interface ResolvedTenantTheme {
  overrides: TenantThemeOverrides
  cssVars: Record<string, string>
}
