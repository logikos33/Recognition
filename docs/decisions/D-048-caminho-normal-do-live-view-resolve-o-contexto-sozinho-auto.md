# D-048 · Caminho normal do live view resolve o contexto sozinho — auto-assumir + token renovável

**Seção:** 3ª rodada de 04/08 — "Live view fluido de verdade + causa do SIGTERM" (D-48..D-53) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Vitor (AskUserQuestion) · ✅ vigente · PR #302**

A causa do congelamento ([[D-40]]) foi tornada **visível** pelo banner do #296, mas não **resolvida**: o
superadmin (home tenant = Logikos `22222222`) abria a grade das 8 câmeras da RVB (`63c219d8`) e precisava
assumir o contexto **manualmente** a cada sessão (e re-assumir quando o TTL de 30 min expirava). O item 3
do prompt cravou: *o passo manual É o bug*.

Decisão do Vitor entre 3 opções (persistir tenant "pinado" · auto-assumir · manter manual): **auto-assumir
+ token renovável** (Opção B+C). Ao abrir a grade, se **todas** as câmeras estrangeiras são de **um único**
tenant, o frontend assume o contexto automaticamente (`useAutoAssumeTenantContext`), com guard anti-loop em
`sessionStorage` (gravado antes do reload do `assumeTenantContext`, limpo ao confirmar contexto, debounce
60s). Um endpoint novo `POST /api/v1/admin/tenant-context/renew` reemite o token (mesmas claims + TTL cheio)
e um timer renova a ~25 min, para o contexto não cair no meio do trabalho.

**Por que NÃO a Opção A (pin persistente):** é a mais próxima do que a §9 do contrato veta (acesso
quase-permanente da Logikos dentro do cliente). A B mantém a impersonação **por-sessão, auditada**
(`tenant_ctx=True` + `impersonated_by` em todo token → `tenant_context_audit` da migration 108 grava cada
requisição; `audit_log` grava assume/renew) e **atribuível ao ato** de abrir a grade — não acesso
permanente. Nada toca `get_tenant_id()` (ADR-0017); cross-tenant continua **404** (C-01). Sem migration.
