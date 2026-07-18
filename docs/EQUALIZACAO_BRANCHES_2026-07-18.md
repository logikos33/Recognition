# Equalização de branches develop ↔ staging ↔ main — 2026-07-18

> **Fonte de verdade:** GitHub compare API (`gh api repos/.../compare/<base>...<head>`), NÃO ref local
> (a ref local estava 13 PRs stale por refs quebradas — ver `HIGIENE_REPO_2026-07-18.md`).
> **staging = PRODUÇÃO.** Convergência para staging/main = **gate humano**. Este doc é **plano, não execução**.

## 1. Divergência REAL medida (ancestralidade de commits)

| Comparação | ahead | behind | Leitura |
|---|---|---|---|
| `develop` vs `staging` | develop **+108** | develop **−2** | develop MUITO à frente; staging tem 2 commits que a develop não tem |
| `develop` vs `main` | develop **+114** | develop **−3** | develop à frente; main tem 3 que a develop não tem |
| `staging` vs `main` | staging **+8** | staging **−3** | quase alinhados |

**Heads (via `gh api`):** `develop`=`2a48daf3` · `staging`=`66a2faf6` · `main`=`65d51f24`.

> ⚠️ **O CLAUDE.md dizia "staging 40 commits à frente de develop" (2026-07-13). ISSO SE INVERTEU.** A troca
> ultralytics→ONNX, test console e harness de escala **foram mergeados na develop** desde então (PRs #168–#196).
> Hoje é a **develop que está 108 à frente do staging**. CLAUDE.md atualizado com o número real.

## 2. O que existe SÓ em staging (não na develop) — 2 commits

| SHA | Mensagem | Arquivos |
|---|---|---|
| `e650a72` | fix(ci): remover job license-gate duplicado no ci.yml (staging) | `.github/workflows/ci.yml` |
| `66a2faf` | fix(ci): remover job license-gate duplicado no ci.yml (staging) | `.github/workflows/ci.yml` |

**Natureza:** hotfix de CI aplicado direto no staging (padrão "fix na produção, sem back-port"). **Divergência
real de código** (não só ordem de commit), mas trivial e localizada num arquivo.

## 3. O que existe SÓ em main (não na develop) — 3 commits

- `fix(migration): renumerar colisão de 6 arquivos no prefixo 052 (ADR-0043) (#159)`
- 2× `fix(ci): remover job license-gate duplicado no ci.yml (main)`

**Natureza:** o mesmo hotfix de CI + uma **renumeração de migrations** (colisão 052) aplicada no main. A
renumeração de migration é **divergência real e sensível** (mexe em nomes de arquivo de migration) — precisa ir
para a develop com cuidado (forward-only; não reaplicar se já resolvida por outro caminho).

## 4. O que existe SÓ na develop (não em staging) — 108 commits

Todo o trabalho recente: license-gate ONNX (task-055a/079/080/081), detector RF-DETR servido (#174/175/177),
ONVIF discovery (#183), deployment-mode (#181), cloud-only (#182), zero-shot pre-annotation (#184), soak RVB
task-113 (#196), cenário multi-módulo (#193), campanha de escala (#191/192), telemetria edge (#190), correções
de CI/SCA/deps (#165/169/170), etc. **É o fluxo normal `develop→staging` acumulado, esperando promoção.**

## 5. Divergência real vs ordem de commit

- **staging↔develop:** a única divergência de **conteúdo** que a develop não tem é o hotfix de CI do `ci.yml`
  (2 commits, mesmo arquivo). Os outros 106 "ahead" da develop são trabalho novo a ser promovido — não é
  divergência, é fluxo pendente.
- **main↔develop:** hotfix de CI **+ renumeração de migration-052** (esta é conteúdo real ausente na develop).

## 6. Plano de convergência (passos seguros e reversíveis — NÃO executado, gate humano)

> Nenhum passo abaixo foi executado. Ordem pensada para minimizar risco; cada passo é reversível (revert do
> merge/cherry-pick). **Promoção para staging/main exige aprovação humana.**

1. **Back-port dos hotfixes staging/main → develop** (baixo risco, resolve a divergência "−2/−3"):
   - Cherry-pick (ou reaplicar equivalente) do fix `ci.yml` "remover job license-gate duplicado" para a develop.
     Antes: **verificar por conteúdo** se a develop já não tem o job duplicado resolvido por outro commit (a
     ancestralidade diz "ausente", mas pode haver equivalente — comparar o `ci.yml` real dos dois lados).
   - Avaliar a **renumeração de migration-052 (#159 do main)**: conferir se a develop já está livre da colisão
     052 (rodar o harness de migrations 2×). Se a colisão persistir na develop, portar a renumeração como **nova
     migration forward-only** (nunca editar migration aplicada). Se já resolvida, só registrar.
   - Risco: baixo. Reversível por `git revert`.
2. **Fechar os PRs abertos que devem entrar na develop** (higiene — ver `HIGIENE_REPO_2026-07-18.md`): #197
   (após rebase), #189 (security, gate humano), decidir #194/#78.
3. **Promover `develop → staging`** (gate humano): merge-commit (NUNCA squash — runbook
   `GITHUB_CONTRIBUTIONS_MERGE_MAIN.md`). Traz os 108 commits para produção. **Rodar smoke test antes**
   (`./scripts/smoke_test.sh https://api-v3-production-2b22.up.railway.app`).
   - Risco: ALTO (é produção). Reversível por revert do merge-commit, mas com janela de exposição.
4. **Promover `staging → main`** (gate humano) após validação em produção.
5. **Pós-promoção:** confirmar `develop ≡ staging ≡ main` (compare API `ahead=0 behind=0` nos dois sentidos)
   e limpar branches mergeadas.

## 7. Verificação (repetir com `gh`, não com ref local)
```bash
gh api "repos/logikos33/Recognition/compare/develop...staging" --jq '"ahead=\(.ahead_by) behind=\(.behind_by)"'
gh api "repos/logikos33/Recognition/compare/staging...main"    --jq '"ahead=\(.ahead_by) behind=\(.behind_by)"'
```
