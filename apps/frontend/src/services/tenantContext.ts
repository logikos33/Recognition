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
 *
 * D-48 (opção C) — renovação proativa: o token de contexto tem TTL curto
 * (30min, TENANT_CONTEXT_TTL_MINUTES espelhado abaixo). scheduleTenantContextRenewal
 * agenda um POST /tenant-context/renew ~5min antes do TTL expirar, trocando
 * o token em localStorage SEM reload — uma sessão de trabalho longa não cai
 * no meio. Falha no renew não reagenda: o token simplesmente expira e o
 * branch 401 de services/api.ts já cuida de restaurar o superadmin.
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
  cancelTenantContextRenewal()
  restoreTenantContextBackup('/admin/tenants')
}

// ── Renovação proativa (D-48, opção C) ───────────────────────────────────

/** Espelha TENANT_CONTEXT_TTL_MINUTES de app/core/tenant_context.py — só
 * para calcular QUANDO agendar a renovação; o TTL de verdade é sempre o que
 * o backend emite no token (fonte da verdade). */
const TENANT_CONTEXT_TTL_MINUTES = 30
/** Renova com essa folga antes do TTL expirar. */
const RENEW_BEFORE_EXPIRY_MINUTES = 5

interface RenewContextResponse {
  success: boolean
  data: {
    token: string
    tenant: { id: string }
    user: Record<string, unknown>
    expires_in_minutes: number
  }
}

let renewTimer: ReturnType<typeof setTimeout> | null = null

/**
 * Renova o token de contexto assumido — mesmas claims, TTL cheio de novo —
 * SEM reload. Só deve ser chamada enquanto isInTenantContext() for true
 * (o backend rejeita renovar um token que não é de contexto assumido).
 */
export async function renewTenantContext(): Promise<void> {
  const res = await api.post<RenewContextResponse>('/v1/admin/tenant-context/renew', {})
  const { token, user } = res.data
  setToken(token)
  localStorage.setItem('user', JSON.stringify(user))
}

/**
 * Agenda a renovação proativa do contexto assumido (~TTL - 5min). Sucesso
 * reagenda a próxima renovação — uma sessão longa continua renovando
 * enquanto o contexto seguir ativo. Falha NÃO reagenda: deixa o token
 * expirar naturalmente (branch 401 de services/api.ts restaura o
 * superadmin). Só agenda se isInTenantContext() — nunca renova um token
 * base.
 *
 * Deliberadamente setTimeout cru (não usePolling — ver hooks/AGENTS.md):
 * não é polling de status, é um heartbeat de renovação de token de baixa
 * frequência (~25min) vivendo num módulo de serviço, não amarrado ao ciclo
 * de vida de um componente específico — TenantContextBanner só liga/desliga
 * o agendamento via cancelTenantContextRenewal.
 */
export function scheduleTenantContextRenewal(): void {
  cancelTenantContextRenewal()
  if (!isInTenantContext()) return

  const delayMs = Math.max(0, TENANT_CONTEXT_TTL_MINUTES - RENEW_BEFORE_EXPIRY_MINUTES) * 60_000
  renewTimer = setTimeout(() => {
    renewTenantContext()
      .then(() => scheduleTenantContextRenewal())
      .catch(() => {
        // best-effort — deixa expirar naturalmente, sem reagendar
      })
  }, delayMs)
}

/** Cancela o agendamento de renovação (saída do contexto ou expiração). */
export function cancelTenantContextRenewal(): void {
  if (renewTimer) {
    clearTimeout(renewTimer)
    renewTimer = null
  }
}
