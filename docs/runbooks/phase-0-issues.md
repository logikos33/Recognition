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

---

### PEND-006: Worker requirements instala CUDA completo (~2.5 GB)

**Status:** Pendente — registrado em 2026-05-28  
**Descoberta:** Validação local do `Dockerfile.worker` pós-Fase 0 revelou que o build baixa >2.5 GB de pacotes `nvidia-*-cu13` e `cuda-toolkit=13.0.2` via `torch>=2.0.0`.  
**Evidência:** Build local consumiu >2.5 GB só de libs CUDA vindas como dependência transitiva do PyTorch default.  
**Impacto:**
- Imagem final do worker estimada em 6-8 GB
- Deploy Railway lento (upload da imagem)
- Boot lento (camadas maiores)
- Custo de storage Railway maior
- Libs CUDA inúteis em ambiente cloud sem GPU

**Causa:** `requirements/worker.txt` declara `torch>=2.0.0` sem especificar variante CPU. O índice default do PyPI instala a build com CUDA.

**Plano (executar em sprint de otimização de imagens — Fase 1.5 ou Fase 4):**
1. Auditar `requirements/worker.txt` e `requirements/base.txt`
2. Confirmar se worker realmente precisa de torch (tasks de YOLO inferência provavelmente pertencem ao `inference` service, não ao worker)
3. Se worker precisa torch CPU-only: usar `--index-url https://download.pytorch.org/whl/cpu`
4. Se worker NÃO precisa torch: remover do requirements
5. Re-medir tamanho da imagem após correção

**Bloqueador para PR #6?** Não — problema pré-existente, não introduzido por esta branch.
