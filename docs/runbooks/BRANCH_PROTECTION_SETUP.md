# Branch Protection — passo a passo (aplicar manualmente)

**Data:** 2026-07-14
**Por que este documento existe:** o Claude Code não deve alterar controles de acesso do
repositório (permissões, proteção de branch) sozinho — é uma ação que exige o gate humano do
Vitor. Este runbook é o "produzir em docs/" pedido no lugar de tentar configurar via API.

## Estado verificado em 2026-07-14

```
gh api repos/logikos33/Recognition/branches/develop/protection  → 404 Branch not protected
gh api repos/logikos33/Recognition/branches/staging/protection  → 404 Branch not protected
gh api repos/logikos33/Recognition/branches/main/protection     → 404 Branch not protected
```

Nenhuma das três branches de longa duração tem proteção hoje. Push direto (inclusive
force-push) é tecnicamente possível em todas — só a disciplina do fluxo de trabalho
(`docs/DIRETRIZ_OPERACAO_CLAUDE_CODE.md`) impede isso hoje, não o GitHub.

## O que configurar (GitHub → Settings → Branches → Add branch protection rule)

Repita para `staging` e `main` (branch pattern = nome exato da branch).

### 1. Require a pull request before merging
- ✅ **Require a pull request before merging**
- ✅ **Require approvals** — mínimo 1
- ✅ **Require review from Code Owners** (depende de um `.github/CODEOWNERS` existir e estar
  commitado — hoje não existe em `develop`; é item do PR de governança-docs)
- ✅ **Dismiss stale pull request approvals when new commits are pushed**

### 2. Require status checks to pass before merging
- ✅ **Require branches to be up to date before merging**
- Marcar como **required** os checks que hoje são gate real (rodam no `ci.yml`):
  - `License gate (no AGPL/GPL in serving path)`
  - `Lint (ruff)`
  - `Tests (pytest)`
  - `TypeScript check`
  - `Migrations harness (D1)`
  - `Secret detection (gitleaks)`
- **Não marcar como required** (ainda são sinal, não gate — ver
  `docs/runbooks/sast-sca-baseline-phase0.md`):
  - `SAST (bandit)`, `SCA (pip-audit)` (matrix), `SCA (npm audit)` (matrix), `SBOM (Syft / CycloneDX)`
  - Marcá-los como required hoje bloquearia todo PR permanentemente, porque os 198 achados
    do bandit e as ~15 vulnerabilidades transitivas do npm audit (achado real do PR #165)
    ainda não foram triados.

### 3. Outras regras recomendadas
- ✅ **Require conversation resolution before merging**
- ✅ **Require linear history** — opcional; o projeto já usa merge commit (não squash) pra
  `staging`/`main`, então esta regra pode conflitar com o runbook de merge — **não marcar**
  se o fluxo de merge commit for mantido.
- ✅ **Do not allow bypassing the above settings** — inclui administradores; garante que nem
  o dono do repo faz push direto sem querer.
- ❌ **Allow force pushes** — manter desmarcado.
- ❌ **Allow deletions** — manter desmarcado (protege as branches de longa duração).

### 4. Via `gh` (alternativa à UI, para o Vitor rodar)

```bash
# staging
gh api --method PUT repos/logikos33/Recognition/branches/staging/protection \
  -f required_status_checks.strict=true \
  -f 'required_status_checks.contexts[]=License gate (no AGPL/GPL in serving path)' \
  -f 'required_status_checks.contexts[]=Lint (ruff)' \
  -f 'required_status_checks.contexts[]=Tests (pytest)' \
  -f 'required_status_checks.contexts[]=TypeScript check' \
  -f 'required_status_checks.contexts[]=Migrations harness (D1)' \
  -f 'required_status_checks.contexts[]=Secret detection (gitleaks)' \
  -f enforce_admins=true \
  -f required_pull_request_reviews.required_approving_review_count=1 \
  -f required_pull_request_reviews.dismiss_stale_reviews=true \
  -f restrictions=null

# repetir trocando "staging" por "main"
```

> A sintaxe exata de `gh api` para arrays aninhados varia por versão do CLI — testar em modo
> dry-run (`--input -` com o JSON completo) se o comando acima falhar. A UI é o caminho mais
> confiável se a CLI der problema de payload.

## Depois de aplicar

- Reconfirmar com `gh api repos/logikos33/Recognition/branches/<branch>/protection` (deve
  retornar 200, não mais 404).
- Atualizar este runbook com a data em que cada branch foi protegida.
- Quando o baseline de bandit/pip-audit/npm-audit estiver triado (ver
  `docs/runbooks/sast-sca-baseline-phase0.md`), promover esses checks para `required` também.
