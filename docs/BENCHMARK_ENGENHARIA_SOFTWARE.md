# Benchmark de Engenharia de Software — Recognition

> Companion do `docs/BENCHMARK_BOAS_PRATICAS.md` (aquele = documentação/hygiene; **este = maturidade de
> engenharia**: entrega/DORA, CI/CD, testes, observabilidade, supply chain, release, progressive delivery).
> **Data:** 2026-07-14 · Estado do repo validado contra `origin/develop` e os workflows do CI (C-04). Fontes no fim.

## O que o projeto já faz bem (não mexer, só manter)
Migrations forward-only + harness idempotente 2x · license-gate (sem AGPL no servido) · secret scanning (gitleaks)
· mapa de contrato FE↔BE (`API_CONTRACT_MAP.md`) · feature flags por tenant (`feature_flags`, `ui_v3`,
`DEPLOYMENT_MODE`) · Sentry (erros) · healthcheck (`/api/v1/health`) · smoke test + scale harness 4→28 câmeras
· CI com ruff + pytest + cobertura mínima (60% no CI) · lockfiles npm (`package-lock.json`).

---

## 1. Entrega & DORA (fluxo de release)

| Prática (benchmark) | Estado no repo | Lacuna / Ação | Prioridade |
|---|---|---|---|
| Fluxo de branch definido | ✅ `develop→staging→main` com gates humanos | consciente; **não** migrar pra trunk-based agora (gates são de propósito) | — |
| **Branch protection** (required checks, no push direto) | ❓ não verificável no sandbox | **Confirmar/ativar** no GitHub: `staging` e `main` exigem PR + CI verde + review (CODEOWNERS) | P1 |
| Métricas DORA (deploy freq, lead time, CFR, MTTR) | ❌ não medidas | Passar a marcar releases (tags) e medir as 4 métricas — base para saber se melhora | P2 |
| Ambientes efêmeros / preview por PR | ❌ | avaliar preview no Railway por PR (valida antes de `develop`) | P3 |
| Commits assinados (GPG/SSH) | ❓ | opcional; ativar signing + "require signed commits" nas branches protegidas | P3 |

## 2. CI/CD

| Prática | Estado | Lacuna / Ação | Prioridade |
|---|---|---|---|
| CI com lint + testes + gates | ✅ ci.yml (license-gate, ruff, pytest) | ok | — |
| **Actions pinadas por SHA** (não por tag mutável) | ❌ usa `@v4`/`@v2` | pinar por commit SHA (supply-chain: tag é mutável) | P1 |
| SAST / SCA no pipeline | ⚠️ só gitleaks | adicionar bandit (SAST) + pip-audit (SCA) — ver benchmark de docs | P1 |
| Jobs em runner efêmero e isolado | ✅ GitHub-hosted | ok | — |
| CD automatizado | ✅ push→Railway (staging) | manter; documentar promoção como parte do fluxo | — |

## 3. Testes

| Prática | Estado | Lacuna / Ação | Prioridade |
|---|---|---|---|
| Unit/integração (pytest, DB real) + front (Vitest/RTL/Playwright) | ✅ | ok | — |
| Meta de cobertura | ⚠️ `--cov-fail-under=60` no CI (pyproject diz 30, "subir gradual") | **alinhar** o número entre pyproject e CI; escada 60→70; documentar em `docs/TESTING.md` | P2 |
| **Contract testing** FE↔BE | ❌ (há o MAPA, falta teste executável) | aproveitar `API_CONTRACT_MAP.md`: Schemathesis (contra o OpenAPI) ou Pact — pega quebra de contrato no CI | P2 |
| Mutation testing (qualidade do assert) | ❌ | amostral com `mutmut`/`cosmic-ray` em módulos críticos (auth, tenant, counting) | P3 |
| Teste de carga como gate | ⚠️ scale harness existe, manual | rodar o harness no CI (nightly) com limiar de degradação | P2 |

## 4. Observabilidade

| Prática | Estado | Lacuna / Ação | Prioridade |
|---|---|---|---|
| Error tracking | ✅ Sentry | ok | — |
| **Logs estruturados** (JSON, correlação por request/tenant) | ⚠️ `logging` padrão | padrão de log estruturado + `request_id`/`tenant_id` em todo log; doc curto | P2 |
| Métricas (Prometheus/`/metrics`) | ❌ | expor métricas de app (latência de rota, fila Celery, FPS por câmera) | P2 |
| Tracing distribuído (OpenTelemetry) | ❌ | OTel no caminho câmera→edge→api→worker (padrão de mercado; ajuda debug edge↔cloud) | P3 |
| **SLO + error budget** + alerta de burn-rate | ❌ | definir SLOs (uptime API, latência de evento <5s, sucesso de ingest) em `docs/SLO.md` | P2 |
| Synthetic / uptime check | ❌ | monitor sintético batendo no healthcheck + fluxo crítico (barato, alto valor) | P2 |

## 5. Supply chain (cadeia de suprimentos)

| Prática | Estado | Lacuna / Ação | Prioridade |
|---|---|---|---|
| Lockfile de dependências | ⚠️ npm ✅ · **Python não pinado** (`>=`) | pinar Python: `pip-tools`/`uv` gerando lock com hashes por requirements/ | P1 |
| Atualização automatizada de deps | ⚠️ Dependabot proposto | ligar `.github/dependabot.yml` (já redigido) | P1 |
| **SBOM** por build | ❌ | gerar SBOM (Syft/CycloneDX) no CI e anexar como artefato | P2 |
| Verificação de integridade em CI | ⚠️ | validar lockfile/hashes no build | P2 |
| Actions por SHA | ❌ | (ver §2) | P1 |

## 6. Release & progressive delivery

| Prática | Estado | Lacuna / Ação | Prioridade |
|---|---|---|---|
| Changelog | ✅ `docs/CHANGELOG.md` | padronizar Keep-a-Changelog | P2 |
| **SemVer + tags de release** | ❌ | taggear releases (base p/ DORA e rollback preciso) | P2 |
| Feature flags | ✅ por tenant + `ui_v3` | ok; falta **processo de ciclo de vida** da flag (remover flag morta) | P3 |
| Canary + rollback automático por erro | ❌ | rollback automático em regressão de taxa de erro (shift-right) — futuro | P3 |

## Prioridade de execução
1. **P1:** branch protection (confirmar/ativar) · Actions por SHA · pinar deps Python + ligar Dependabot · SAST/SCA no CI.
2. **P2:** contract testing (usar o contrato) · SLO + synthetic check · logs estruturados + métricas · SBOM · scale harness nightly · `docs/TESTING.md` + alinhar cobertura · SemVer/tags.
3. **P3:** OpenTelemetry tracing · mutation testing · canary/auto-rollback · preview envs · ciclo de vida de flags.

> Observação estratégica: os itens de **maior retorno por hora** aqui são branch protection, pin de Actions/deps
> e um synthetic check + SLO — baratos e cobrem risco real (supply chain e detecção de queda). Tracing/OTel e
> mutation testing rendem menos agora e podem esperar o pós-go-live RVB.

## Fontes
- DORA — métricas de entrega: https://dora.dev/guides/dora-metrics/
- Atlassian — Trunk-based development: https://www.atlassian.com/continuous-delivery/continuous-integration/trunk-based-development
- OpenTelemetry — Observability primer: https://opentelemetry.io/docs/concepts/observability-primer/
- Testing/coverage & shift-right (2026 guide): https://codersera.com/blog/software-testing-complete-guide-2026/
- Docker — Software supply chain security best practices: https://www.docker.com/blog/software-supply-chain-security-best-practices/
- Oligo — Ultimate guide to software supply chain security (2025): https://www.oligo.security/academy/ultimate-guide-to-software-supply-chain-security-in-2025
- Python supply chain (pinning/hashes): https://bernat.tech/posts/securing-python-supply-chain/
