/**
 * Auto-assume de contexto de tenant (D-48, opção B) — grade de monitoramento.
 *
 * Quando o superadmin (home tenant = Logikos) abre uma grade cujas câmeras
 * cross-tenant reportadas (ver services/crossTenantCameras.ts) pertencem
 * TODAS a um ÚNICO tenant estrangeiro, este hook assume o contexto daquele
 * tenant automaticamente — reusando o MESMO fluxo auditado de
 * assumeTenantContext (services/tenantContext.ts) que o
 * CrossTenantCameraBanner já oferece manualmente. Zero passo extra pro caso
 * comum (a grade da RVB é hoje o único tenant "estrangeiro" que o superadmin
 * de fato opera no dia a dia).
 *
 * Quando há 2+ tenants estrangeiros na grade, o hook NÃO decide por conta
 * própria — mantém o banner manual (CrossTenantCameraBanner) como único
 * caminho, de propósito: a plataforma não pode adivinhar em qual cliente
 * entrar.
 *
 * Anti-loop (CRÍTICO): assumeTenantContext troca o token e recarrega a página
 * inteira (aqui, na MESMA rota — ver a chamada abaixo). Sem um guard
 * que sobrevive ao reload, um assume que falhar silenciosamente (ou uma
 * grade que continua reportando o mesmo tenant a cada render) dispararia o
 * mesmo POST /assume em loop. Guard em sessionStorage (sobrevive ao reload,
 * some ao fechar a aba — mesmo raciocínio das chaves TENANT_CONTEXT_EXPIRED_*
 * de services/api.ts):
 *   1. ANTES de chamar assumeTenantContext, grava
 *      `auto_assume_attempt:<tenantId>` = Date.now() em sessionStorage.
 *   2. Sucesso: assumeTenantContext recarrega a página → no próximo mount,
 *      isInTenantContext() já é true, então o efeito nem chega a reavaliar
 *      o guard — só o limpa (idempotente; permite um novo auto-assume numa
 *      sessão futura se esse contexto expirar).
 *   3. Falha (sem reload): o guard persiste. Enquanto durar < 60s, novas
 *      execuções do efeito (ex.: re-render por store atualizado) NÃO
 *      re-disparam o assume — cai no fallback do banner manual. Passado
 *      60s, uma nova tentativa é permitida.
 */
import { useEffect } from 'react'
import { useAuth } from './useAuth'
import { useCrossTenantCamerasStore } from '../services/crossTenantCameras'
import { assumeTenantContext, getTenantContextMeta, isInTenantContext } from '../services/tenantContext'

const ATTEMPT_KEY_PREFIX = 'auto_assume_attempt:'
const DEBOUNCE_MS = 60_000

function attemptKey(tenantId: string): string {
  return `${ATTEMPT_KEY_PREFIX}${tenantId}`
}

/**
 * Exportado só para teste do anti-loop — não é API pública do hook.
 * `now` injetável para testar a borda dos 60s sem fake timers.
 */
export function hasRecentAutoAssumeAttempt(tenantId: string, now: number = Date.now()): boolean {
  const raw = sessionStorage.getItem(attemptKey(tenantId))
  if (!raw) return false
  const elapsed = now - Number(raw)
  return elapsed >= 0 && elapsed < DEBOUNCE_MS
}

/**
 * Monta o efeito de auto-assume. Sem retorno — o consumidor (
 * CrossTenantCameraBanner) continua dono da UI de fallback manual.
 */
export function useAutoAssumeTenantContext(): void {
  const { isSuperAdmin } = useAuth()
  const tenants = useCrossTenantCamerasStore((s) => s.tenants)

  useEffect(() => {
    if (!isSuperAdmin) return

    if (isInTenantContext()) {
      // Sucesso confirmado (ou contexto assumido manualmente/por sessão
      // anterior) — libera o guard do tenant ativo pra permitir um novo
      // auto-assume caso esse contexto expire mais tarde.
      const meta = getTenantContextMeta()
      if (meta) sessionStorage.removeItem(attemptKey(meta.tenant_id))
      return
    }

    // 2+ tenants estrangeiros na grade: a plataforma não adivinha em qual
    // cliente entrar — banner manual continua sendo o único caminho.
    if (tenants.length !== 1) return

    const tenantId = tenants[0].tenantId
    if (hasRecentAutoAssumeAttempt(tenantId)) return // fallback: banner manual

    sessionStorage.setItem(attemptKey(tenantId), String(Date.now()))
    // Destino explícito = a tela corrente. O auto-assume dispara COM a grade
    // de monitoramento aberta; mandar para a home (o default do serviço)
    // arrancaria a pessoa da grade que ela acabou de abrir. Mesmo argumento
    // do `SeletorTenant`. (#760: antes ia para o default `'/'`, que logado
    // caía no front ANTIGO — aqui o destino nunca deveria ter sido a home.)
    void assumeTenantContext(
      tenantId,
      window.location.pathname + window.location.search,
    ).catch(() => {
      // Falhou sem reload — guard permanece (expira em 60s); o banner
      // manual segue disponível como fallback nesse meio-tempo.
    })
  }, [isSuperAdmin, tenants])
}
