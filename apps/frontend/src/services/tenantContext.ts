/**
 * Assumir contexto de tenant (superadmin).
 *
 * Distinto de impersonation.ts (WS6, "ver como um usuário"): aqui o
 * superadmin troca de TENANT mantendo a própria identidade — usado para
 * navegar/depurar o produto como se estivesse "dentro" de um tenant
 * específico, com os próprios privilégios de superadmin.
 *
 * Mesmo mecanismo de troca/backup/restauração de token do WS6 (ver
 * services/api.ts): o token original fica em backup no localStorage e é
 * restaurado ao sair do contexto ou quando o token assumido expira (branch
 * 401 em services/api.ts → restoreTenantContextBackup).
 */
import {
  api,
  getToken,
  setToken,
  restoreTenantContextBackup,
  TENANT_CONTEXT_BACKUP_KEY,
  TENANT_CONTEXT_META_KEY,
} from './api'

export interface AvailableTenant {
  id: string
  name: string
  slug: string
}

export interface TenantContextMeta {
  tenant_id: string
  tenant_name: string
  tenant_slug: string
  started_at: string
}

interface ListTenantsResponse {
  success: boolean
  data: { tenants: AvailableTenant[] }
}

interface AssumeContextResponse {
  success: boolean
  data: {
    token: string
    tenant: { id: string; name: string; slug: string }
    user: Record<string, unknown>
    expires_in_minutes: number
  }
}

/** Tenants disponíveis para assumir contexto (ativos, com schema válido). */
export async function listAvailableTenants(): Promise<AvailableTenant[]> {
  const res = await api.get<ListTenantsResponse>('/v1/admin/tenant-context/tenants')
  return res.data.tenants
}

/** Há um contexto de tenant assumido ativo neste navegador? */
export function isInTenantContext(): boolean {
  return localStorage.getItem(TENANT_CONTEXT_META_KEY) !== null
}

/** Metadados do contexto assumido (nome/slug do tenant) — p/ o banner. */
export function getTenantContextMeta(): TenantContextMeta | null {
  try {
    return JSON.parse(localStorage.getItem(TENANT_CONTEXT_META_KEY) || 'null')
  } catch {
    return null
  }
}

/**
 * Assume o contexto do tenant: troca o token com backup do original e
 * recarrega. Lança Error com mensagem traduzida em caso de falha (caller
 * mostra Toast).
 */
export async function assumeTenantContext(tenantId: string): Promise<void> {
  const res = await api.post<AssumeContextResponse>(
    `/v1/admin/tenant-context/tenants/${tenantId}/assume`,
    {},
  )
  const { token, tenant, user } = res.data

  // Backup do superadmin ANTES de trocar o token
  const backup = { token: getToken(), user: localStorage.getItem('user') }
  localStorage.setItem(TENANT_CONTEXT_BACKUP_KEY, JSON.stringify(backup))
  localStorage.setItem(
    TENANT_CONTEXT_META_KEY,
    JSON.stringify({
      tenant_id: tenant.id,
      tenant_name: tenant.name,
      tenant_slug: tenant.slug,
      started_at: new Date().toISOString(),
    } satisfies TenantContextMeta),
  )
  setToken(token)
  localStorage.setItem('user', JSON.stringify(user))
  window.location.href = '/'
}

/**
 * Sai do contexto assumido: restaura o token do superadmin salvo em backup.
 * Sem endpoint de backend — a saída é só troca de token local (TTL curto
 * do token assumido já garante que ele expira sozinho).
 */
export function exitTenantContext(): void {
  restoreTenantContextBackup('/admin/tenants')
}
