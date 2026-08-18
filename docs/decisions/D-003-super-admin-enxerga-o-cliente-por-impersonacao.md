# D-003 · Super admin enxerga o cliente por impersonação

**Seção:** Segurança e multi-tenancy · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**03/08 · Vitor (AskUserQuestion) · ✅ vigente · PR #279 mergeado**

Descartadas: visão cross-tenant agregada (superfície de vazamento nova) e tenant fixo na conta
(quebra no segundo cliente).
Desenho: token curto (30 min) com o schema do alvo + claim `impersonated_by`, banner permanente,
log de auditoria (migration 108).
⛔ **Restrição inegociável:** não mexer em `get_tenant_schema()` / `get_tenant_id()`. Se a solução
precisar tocar neles, está errada. Fallback de tenant continua banido (ADR-0017).
