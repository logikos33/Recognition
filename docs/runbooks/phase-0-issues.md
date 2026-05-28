# Phase 0 — Issues e Pendências

**Data:** 2026-05-28

## Pendências conhecidas ao final da Fase 0

### PEND-001: Docker build local não validado

**Status:** Pendente  
**Motivo:** Docker Desktop não disponível no ambiente de execução durante a Fase 0.  
**Risco:** Baixo — Dockerfiles foram inspecionados e não têm erros de sintaxe. Builds em CI/Railway validarão em deploy real.  
**Ação:** Validar antes do primeiro deploy de staging que tocar esses serviços:

```bash
docker build -t test-api -f services/api/Dockerfile .
docker build -t test-inf -f services/inference/Dockerfile services/inference/
docker build -t test-fe  -f apps/frontend/Dockerfile apps/frontend/
docker build -t test-land -f apps/landing/Dockerfile apps/landing/
```

**Responsável:** Vitor (validação manual antes de subir staging)

---

### PEND-002: 11 testes pré-existentes baselinados

**Status:** Documentado, deselected no CI  
**Detalhes:** Ver `docs/runbooks/test-baseline-phase0.md`  
**Ação:** Corrigir em sprint de qualidade futura

---

### PEND-003: 319 erros ruff pré-existentes baselinados

**Status:** Documentado, regras mínimas no CI  
**Detalhes:** Ver `docs/runbooks/lint-baseline-phase0.md`  
**Ação:** Ampliar regras graduamente em sprint de qualidade futura

---

### PEND-004: railway_start.py ainda na raiz do repo

**Status:** Aceito por design  
**Contexto:** `railway_start.py` fica na raiz porque precisa de acesso a `infra/migrations/` e `requirements/`, que não estão dentro de `services/api/`. O `services/api/Dockerfile` usa build context = repo root para acessar esses arquivos.  
**Risco:** Nenhum — Railway usa `dockerfilePath = "services/api/Dockerfile"` sem `rootDirectory`, então build context é repo root.

---

### PEND-005: services/api/migrations/ vazio mas existe

**Status:** Cosmético  
**Contexto:** `services/api/migrations/` existe (era pasta na raiz do antigo `backend/`) mas não contém as migrations (que foram para `infra/migrations/`).  
**Ação:** Pode ser removido em PR futuro após confirmar que nada referencia esse path.
