# Constitution — Recognition Platform

**Versão:** 1.0
**Data:** 2026-06-02
**Owner:** Logikos / Vitor Emanuel

Princípios INEGOCIÁVEIS do projeto, numerados e citáveis por código e documentação.
Para detalhe operacional, ver `CLAUDE.md`, `AGENT.md` e `AGENTS.md` — mas em caso de conflito,
**a constitution prevalece**.

Fontes: `docs/DECISIONS.md`, `docs/decisions/adr/`, runbooks Sprint 0.5/0.6,
`docs/architecture/HARNESS_EXPLORATORIO.md`.

---

## C-01 — Multi-tenant sempre

Toda tabela tem `tenant_id UUID REFERENCES tenants(id)`. Toda query filtra por `tenant_id`
(extraído de `get_tenant_id()` em `app/core/auth.py` via JWT).
Nenhuma tabela nova é criada sem este campo. Nenhuma query retorna dados cross-tenant.

**Fontes:** `docs/DECISIONS.md ADR-002`, `docs/decisions/adr/0004-schema-per-tenant-multitenancy.md`,
`docs/decisions/adr/0017-tenant-isolation-enforcement.md`, `CLAUDE.md § Multi-tenant`.

---

## C-02 — Migrations forward-only e idempotentes

Apenas `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`.
Nunca `DROP`, `DELETE FROM`, `TRUNCATE`, `ALTER COLUMN TYPE`, `ALTER TYPE`.
Toda migration deve ser executável 2× sem produzir erro novo.

**Fontes:** `docs/DECISIONS.md ADR-005`, `CLAUDE.md § Banco de dados`.
**Eval:** `tests/harness/migrations/` (Fase D1) — valida automaticamente a cada PR.

---

## C-03 — psycopg2 + RealDictCursor, zero ORM

Driver: `psycopg2` com `RealDictCursor` como padrão. Zero SQLAlchemy, zero qualquer ORM.
Todo SQL fica nos repositories (`app/infrastructure/database/repositories/`).
Sem SQL em routes, services ou helpers.

**Fontes:** `docs/DECISIONS.md ADR-001`, `CLAUDE.md § Banco de dados`.

---

## C-04 — Ver schema REAL antes de assumir

"Quem infere em vez de verificar, quebra." (`docs/architecture/HARNESS_EXPLORATORIO.md:19`)
Em dúvida, consultar `information_schema`, rodar o harness D1
(`bash tests/harness/migrations/run.sh`) ou executar SQL direto contra o banco de dev.
Nunca inferir schema a partir de migrations antigas, logs ou memória.

**Fontes:** runbooks Sprint 0.5/0.6 (`docs/runbooks/sprint-0.6-complete.md`),
`docs/architecture/HARNESS_PLANO_IMPLEMENTACAO.md:137`.

---

## C-05 — Segurança no chão

- `CORS(app, origins=config.CORS_ORIGINS)` — nunca `CORS(app)` bare.
- `RTSPUrlValidator` antes de qualquer URL chegar ao FFmpeg.
- Zero SQL com f-string de input do usuário.
- Zero `print()` no backend — usar `logging.getLogger(__name__)`.
- Tokens RSA-256 para comunicação edge → cloud (`docs/decisions/adr/0019-device-tokens-rs256.md`).

**Fontes:** `CLAUDE.md § Segurança`, `CLAUDE.md § Qualidade`.

---

## C-06 — Branch flow e checkpoints

```
feature/X  →  develop  →  staging  →  main
```

Nunca push direto em `main`. Toda PR para `main` exige checkpoint humano.
PRs para `develop` não exigem checkpoint (merge autônomo após CI verde).

**Fontes:** `CLAUDE.md § Branching e Commits`.

---

## C-07 — Definição de "concluído"

Uma tarefa é concluída quando:

1. Implementada e testável manualmente.
2. TypeScript compila sem erros (`npx tsc --noEmit`).
3. Zero erros de lint (`ruff check`, `eslint`).
4. CI verde: `ruff` + `pytest` + `tsc` + `gitleaks` + `migrations-harness`.
5. Commit em Conventional Commits (`feat|fix|refactor|docs(scope): descrição`).
6. Push para `staging` com `/health` 200.

**Fontes:** `CLAUDE.md § Definição de Concluído`.

---

## C-08 — Eval-driven para mudanças de schema

Toda alteração de schema (nova migration) ou função SQL (`CREATE OR REPLACE FUNCTION`)
passa pelo harness D1 antes de merge. Se a 2ª passada do runner falhar → a mudança volta.
Nunca editar uma migration já aplicada — criar nova migration para corrigir.

**Fontes:** `docs/EVALS.md`, `docs/architecture/HARNESS_PLANO_IMPLEMENTACAO.md § Fase D1`.

---

## Adendo — Erros legados conhecidos

A migration `038_operations.sql` referencia `ip_cameras` (tabela renomeada para `cameras` na 013).
Em banco virgem, falha com `relation "ip_cameras" does not exist`. A 047 recria `operations` com
FK correta para `cameras(id)`. O runner do harness trata isso como erro legado conhecido (não fatal).
**Não corrigir a 038** (regra C-02 — não editar migration aplicada). Abrir nova migration se necessário.
