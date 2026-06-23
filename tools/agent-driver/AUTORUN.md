# AUTORUN.md — Execução autônoma da fila (Recognition)

> **Para o agente (Claude Code):** este arquivo é a sua constituição para esta sessão.
> Objetivo: **processar TODA a fila `tools/agent-driver/queue.txt`, do topo ao fim, sem parar**,
> validando, corrigindo e mergeando cada task, até que **tudo esteja funcionando** (CI verde em
> `develop`). Não pare para pedir confirmação entre tasks. Só pare nas condições de parada
> explícitas da seção §7. Quando a fila esvaziar, rode a verificação final (§6) e entregue o
> relatório (§8).

---

## 0. Princípios inegociáveis
1. **Nunca** fazer push direto em `main`. Fluxo: `agent/task-NNN-slug` → PR → `develop`.
2. **Nunca** mergear com CI vermelho. Verde = todos os checks do GitHub Actions passando.
3. **Nunca** mergear código com vulnerabilidade real não resolvida (ver §5, risco security).
4. **Uma task = um branch = um PR.** Nada de juntar tasks.
5. **Anti-sweep (CRÍTICO):** o PR de uma task só pode conter os arquivos daquela task.
   Nunca `git add -A`/`git add .`. Ver §4.6.
6. Respeitar `CLAUDE.md` e `AGENTS.md` (regras absolutas: psycopg2 sem ORM, SQL parametrizado,
   `tenant_id` em toda tabela, migrations só aditivas, zero `print()`, CORS explícito, etc.).
7. **Verificar o código real antes de assumir schema/colunas.** Não inferir de memória.

---

## 1. Pré-condições da sessão (rodar uma vez no início)
```bash
git checkout develop && git pull --ff-only
git status --porcelain        # DEVE estar vazio. Se não, ver §7.A
gh auth status                # gh logado (PRs/merge dependem disso)

# Subir Postgres+Redis locais p/ os testes (mesma config do CI):
docker compose -f docker-compose.dev.yml up -d
# Garantir que .coverage / *.coverage estão no .gitignore (anti-sweep). Se não, adicionar e commitar:
grep -q '^\.coverage' .gitignore || printf '\n.coverage\n*.coverage\n' >> .gitignore
```
Variáveis de ambiente para os testes (idênticas ao CI — `.github/workflows/ci.yml`):
```bash
export DATABASE_URL=postgresql://test:test@localhost:5432/recognition_test
export REDIS_URL=redis://localhost:6379
export JWT_SECRET_KEY=ci-test-secret-key-32chars-minimum
export SERVICE_TYPE=api
```

---

## 2. Loop principal
Leia `tools/agent-driver/queue.txt`. Cada linha é `task-NNN risk:<low|security>` (ignore linhas
em branco e comentários `#`). Processe **na ordem, de cima para baixo**. Para cada task, execute
§3 → §4 → §5. Ao concluir (merge), marque a linha como feita em `queue.txt` (prefixe `# DONE `) e
**vá para a próxima sem parar**.

---

## 3. Preparar a task
1. `git checkout develop && git pull --ff-only` (partir sempre de develop atualizado).
2. `git status --porcelain` vazio (§0.5). Se sujo → §7.A.
3. Abra `tools/agent-driver/tasks/task-NNN-*.md` e leia o spec **inteiro**.
4. **Verifique as premissas no código real** (grep/leitura): colunas existem? endpoint existe?
   Ajuste o plano ao que de fato está lá — o spec pode supor algo que mudou.
5. Crie o branch: `git checkout -b agent/task-NNN-<slug>`.

---

## 4. Implementar + validar (o portão)
### 4.1 Implementar
Faça a mudança mínima que satisfaz os **critérios de aceite** do spec. Siga os padrões de
`CLAUDE.md` (responses `success/error`, `DatabasePool`, repositories, etc.).

### 4.2 Migrations (se a task precisar)
- Diretório `infra/migrations/`. Numeração **sequencial** — cheque a última:
  `ls infra/migrations/*.sql | sort | tail -1` e use o próximo número.
- **APENAS** `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` /
  `CREATE INDEX IF NOT EXISTS`. **NUNCA** `DROP`, `ALTER COLUMN TYPE`, `DELETE`, `TRUNCATE`.
- Toda tabela nova: `tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE`.
- Coluna em tabela por-tenant (`{schema}.cameras` etc.): loop de backfill por tenant
  (`DO $$ ... FOR r IN SELECT schema_name FROM public.tenants WHERE schema_name IS NOT NULL ...
  EXECUTE format('ALTER TABLE %I.cameras ADD COLUMN IF NOT EXISTS ...')`).
- **Testar idempotência:** rodar o runner 2x sem erro:
  `python run_migrations.py && python run_migrations.py` (DB de teste).
- Atualizar model + repository + service + route + types do frontend na MESMA task (checklist do
  "Migration Protocol" do CLAUDE.md). Migration sem refletir nas camadas = incompleto.

### 4.3 Validação local — espelha o CI exatamente
Rode os três checks. **Todos verdes** antes de prosseguir:
```bash
# 1) Lint backend
ruff check services/api/

# 2) Testes backend (mesmos deselects e cov mínimo do CI)
pytest services/api/tests/ -v --tb=short -q --cov=app --cov-report=term-missing --cov-fail-under=30 \
  --deselect=tests/unit/core/test_validators.py::TestRTSPUrlValidator::test_invalid_scheme \
  --deselect=tests/unit/infrastructure/test_r2_storage.py::TestR2StorageInit::test_upload_file_calls_upload_file \
  --deselect=tests/unit/domain/test_camera_service.py::TestCameraService::test_delete_camera_success \
  --deselect=tests/unit/domain/test_camera_service.py::TestCameraService::test_delete_camera_wrong_user \
  --deselect=tests/unit/domain/test_camera_service.py::TestCameraService::test_delete_camera_admin_override \
  --deselect=tests/unit/domain/test_camera_service.py::TestCameraService::test_build_rtsp_url_with_override \
  --deselect=tests/unit/domain/test_camera_service.py::TestCameraService::test_build_rtsp_url_generated \
  --deselect=tests/unit/domain/test_camera_service.py::TestCameraService::test_build_rtsp_url_wrong_user_raises \
  --deselect=tests/unit/infrastructure/test_repositories.py::TestCameraRepository::test_create_camera \
  --deselect=tests/test_demo_videos.py::TestDemoVideoServiceIsolation::test_get_for_camera_returns_video_for_superadmin \
  --deselect=tests/quality/test_wiser_integration.py::test_export_pdf_creates_file

# 3) TypeScript (se a task tocou apps/frontend)
cd apps/frontend && npm ci --legacy-peer-deps && npx tsc --noEmit && cd -
```
> **Cobertura:** para módulos/arquivos NOVOS, mire ≥80% (regra do AGENTS.md), mesmo que o portão
> global do CI seja 30%. Escreva testes do que você criou.

> **Skills disponíveis** (use-as como apoio, não como substituto dos comandos acima):
> `engineering:testing-strategy` para desenhar os testes, `engineering:code-review` / `review`
> para auto-revisão antes do commit, `engineering:deploy-checklist` antes do merge,
> `security-review` nas tasks `risk:security` (§5).

### 4.4 Loop de correção
Se qualquer check falhar: leia o erro, **corrija a causa raiz** (não desabilite teste, não baixe
o threshold), re-rode 4.3. Repita até verde. **Não prossiga com nada vermelho.**

### 4.5 Não quebrou o resto
Garanta que sua mudança não derrubou testes pré-existentes que passavam. Os 11 testes
deselecionados no CI são baseline conhecido (`docs/runbooks/test-baseline-phase0.md`) — não
precisa consertá-los, mas **não adicione** novos vermelhos.

### 4.6 Stage cirúrgico (anti-sweep)
```bash
git status                      # revise TUDO que aparece
git add <somente os arquivos desta task, por caminho explícito>
git status                      # confirme: nada de docs/produto alheio, .coverage, queue.txt,
                                #           graphify-out/, *.pyc, scratch
```
- **Nunca** `git add -A` / `git add .`.
- Se aparecer arquivo não relacionado (ex.: `.coverage`, `docs/products/*`, `queue.txt`),
  **não inclua** — gitignore o que for gerado, deixe o resto fora do commit.

### 4.7 Commit + push
```bash
git commit -m "feat(<scope>): <descrição>"   # Conventional Commits (scopes do CLAUDE.md)
git push -u origin agent/task-NNN-<slug>
```

---

## 5. PR, CI e merge
### 5.1 Abrir PR para develop
```bash
gh pr create --base develop --head agent/task-NNN-<slug> \
  --title "feat(<scope>): task-NNN <título>" \
  --body "Implementa task-NNN. Critérios de aceite atendidos. CI local verde (ruff+pytest+tsc)."
```
> Se `gh pr create` der timeout da API do GitHub (já aconteceu antes), **re-tente**; o branch já
> está no remoto. Não recrie o branch.

### 5.2 Esperar o CI ficar verde
```bash
gh pr checks --watch        # aguarda ruff, pytest, tsc e security-scan
```
- CI vermelho → `gh run view --log-failed` (ou abra os logs), corrija na sua branch, push,
  e espere de novo. Loop até verde. **Nunca** mergear vermelho.

### 5.3 Portão de revisão por risco
- **`risk:low`** → com CI verde, faça auto-revisão adversarial (`engineering:code-review`/`review`):
  procure N+1, SQL não parametrizado, vazamento cross-tenant, segredo hardcoded, `any` no TS,
  arquivo >200 linhas. Se limpo → **merge** (§5.4).
- **`risk:security`** → rode `security-review` + escrutínio extra (SSRF em URL de câmera, deleção
  de dados fora de escopo, authz por role, exposição de credencial/R2). 
  - Limpo e seguro → **merge** (§5.4).
  - Achou vuln real que **você não consegue corrigir com segurança** → **PARE nesta task** (§7.B):
    deixe o PR aberto, escreva o motivo, e **siga para a próxima task da fila** (não bloqueie as
    outras). Registre no relatório final.

### 5.4 Merge
```bash
gh pr merge agent/task-NNN-<slug> --squash --delete-branch
git checkout develop && git pull --ff-only
```
Confirme que develop continua verde (CI do push em develop). Marque a task como `# DONE` em
`queue.txt`. Próxima task.

---

## 6. Verificação final (quando a fila esvaziar)
Em `develop` atualizado, rode o portão completo uma última vez e confirme tudo verde:
```bash
ruff check services/api/
pytest services/api/tests/ -q --cov=app --cov-fail-under=30  # (com os mesmos deselects da §4.3)
cd apps/frontend && npx tsc --noEmit && cd -
```
Se houver script de smoke e a API local subir, rode:
```bash
./scripts/smoke_test.sh http://localhost:5001   # ou a URL de staging, se aplicável
```

---

## 7. Condições de PARADA (as únicas)
**A. Working tree sujo no início** e você não tem certeza do que é: `git stash -u` o que for
scratch/gerado e siga; se forem mudanças reais não commitadas de trabalho anterior, **pare** e
reporte — não arrisque perder trabalho.

**B. Vulnerabilidade de segurança real** numa task `risk:security` que não dá pra corrigir com
segurança: deixe o PR aberto, **pule** essa task e continue a fila; liste no relatório.

**C. Task fundamentalmente bloqueada** (dependência externa ausente, spec ambíguo a ponto de não
dar pra decidir com segurança, credencial/serviço indisponível): marque `# BLOCKED <motivo>` em
`queue.txt`, **pule** e siga. Não invente/finja implementação.

**D. CI infra quebrada** (não é seu código — runner caiu, secret faltando): re-tente algumas
vezes; se persistir, pare e reporte com o log.

Fora dessas quatro, **não pare** — corrija e siga até a fila acabar.

---

## 8. Relatório final
Ao terminar (fila vazia ou só com itens BLOCKED/PARADOS), entregue uma tabela:

| Task | Risco | Branch | PR | CI | Merge | Observações |
|------|-------|--------|----|----|-------|-------------|

E um resumo: quantas mergeadas, quantas bloqueadas (e por quê), e o estado final do `develop`
(verde/vermelho). Se algo ficou aberto (security/blocked), liste o que falta para um humano.

---

## Referência rápida
- **Fila:** `tools/agent-driver/queue.txt` · **Specs:** `tools/agent-driver/tasks/task-*.md`
- **CI fonte da verdade:** `.github/workflows/ci.yml` + `security-scan.yml`
- **Backend:** `services/api/` (ruff + pytest) · **Frontend:** `apps/frontend/` (tsc)
- **Migrations:** `infra/migrations/` via `run_migrations.py` (aditivas, idempotentes)
- **Branch alvo:** `develop` (NUNCA `main`)
- **Regras absolutas:** `CLAUDE.md` e `AGENTS.md`
