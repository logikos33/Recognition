# Benchmark de Boas Práticas de Engenharia — Recognition

> **Objetivo:** comparar o que o projeto já pratica com os padrões de mercado (repo hygiene, ADR/arquitetura,
> segurança, privacidade/LGPD, testes, dependências, observabilidade) e listar as lacunas priorizadas.
> **Data:** 2026-07-14 · **Fontes:** ver §Fontes. **Precedência:** constitution → diretriz de operação → CLAUDE.md.

## Como ler
Cada linha traz: prática de mercado · o que já temos · lacuna · prioridade (P0 crítico → P3 baixo). Os itens
marcados **[criado nesta rodada]** já entraram no repo; os demais são recomendação com dono/decisão.

## 1. Higiene de repositório (arquivos-padrão)

| Prática (benchmark) | Já temos? | Lacuna / Ação | Prioridade |
|---|---|---|---|
| README explicando o produto, setup e uso | ✅ `README.md` | ok | — |
| Guia de contribuição / setup dev | ❌ | **[criado]** `CONTRIBUTING.md` | P1 |
| Política de segurança / reporte de vulnerabilidade | ❌ | **[criado]** `SECURITY.md` | P0 (produto de segurança) |
| Template de PR forçando evidência | ❌ | **[criado]** `.github/PULL_REQUEST_TEMPLATE.md` | P1 |
| Templates de issue (bug/feature) | ❌ | **[criado]** `.github/ISSUE_TEMPLATE/` | P2 |
| CODEOWNERS (revisão obrigatória em caminhos sensíveis) | ❌ | **[criado]** `.github/CODEOWNERS` | P1 |
| Template de ADR | ❌ (há 41 ADRs, sem molde) | **[criado]** `docs/decisions/adr/0000-template.md` | P2 |
| Índice/mapa da documentação | ❌ (muitos docs, sem índice) | **[criado]** `docs/README.md` | P2 |
| Atualização automática de dependências | ❌ | **[criado]** `.github/dependabot.yml` | P1 |
| Licença | ✅ código fechado (nota no README) | manter proprietário; **não** adicionar licença OSS | — |
| Notícias de terceiros (licenças) | ✅ `THIRD_PARTY_NOTICES.txt` + license-gate no CI | ok | — |

## 2. Arquitetura & decisões

| Prática | Já temos? | Lacuna / Ação | Prioridade |
|---|---|---|---|
| ADRs (registro imutável de decisão) | ✅ 41 ADRs | manter; usar o template novo | — |
| Modelo C4 (Context/Container/Component) como doc vivo | ⚠️ parcial (diagrama Miro + docs soltos) | Consolidar um `docs/architecture/ARCHITECTURE.md` nível C4 (contexto+contêiner) espelhando o diagrama do Miro | P2 |
| arc42 (template estruturado) | ❌ | opcional; C4 + ADR já cobrem 80% para o porte atual | P3 |
| Diagrama versionado como código (Mermaid/PlantUML) | ⚠️ há `.svg` e Miro | migrar diagramas-chave pra Mermaid no repo (revisável em PR) | P3 |

## 3. Segurança (produto multi-tenant + edge)

| Prática | Já temos? | Lacuna / Ação | Prioridade |
|---|---|---|---|
| Secret scanning no CI | ✅ gitleaks (`security-scan.yml` + `.gitleaks.toml`) | ok | — |
| Gate de licença (sem AGPL no servido) | ✅ `check_license_gate.py` no CI | ok | — |
| SAST (análise estática de segurança) | ❌ | adicionar **bandit** (py) e/ou **CodeQL**/semgrep ao `security-scan.yml` | P1 |
| SCA (auditoria de dependências vulneráveis) | ⚠️ só Dependabot proposto | ligar `pip-audit` + `npm audit`/Dependabot alerts | P1 |
| Política de reporte de vulnerabilidade | ❌ | **[criado]** `SECURITY.md` | P0 |
| Threat model / modelo de ameaças | ❌ | escrever `docs/security/THREAT_MODEL.md` (STRIDE nos limites edge↔cloud, isolamento de tenant) | P2 |
| Pre-commit (ruff + detect-secrets local) | ❌ | adicionar `.pre-commit-config.yaml` | P2 |

## 4. Privacidade / LGPD (crítico — CFTV de trabalhadores, Brasil)

| Prática | Já temos? | Lacuna / Ação | Prioridade |
|---|---|---|---|
| RIPD/DPIA (Relatório de Impacto à Proteção de Dados) | ❌ | **[criado — scaffold]** `docs/security/LGPD_PRIVACIDADE_CFTV.md` (precisa revisão jurídica) | **P0** |
| Política de retenção e descarte automático de imagens | ⚠️ há módulo `retention` (retention_days) | documentar prazo (15–90 dias típico) + descarte automático provado; ligar ao RIPD | P0 |
| Base legal + aviso de monitoramento (transparência) | ❓ | registrar base legal (legítimo interesse) e placas/aviso no site do cliente | P1 |
| Minimização / anonimização (blur de rosto/placa quando possível) | ❓ | avaliar no pipeline de evidência (ADR-0033) | P2 |
| Direitos do titular (acesso/eliminação) | ❓ | procedimento operacional documentado | P2 |

> Por que P0: o produto grava imagem de trabalhadores identificáveis (EPI) — é **dado pessoal** sob LGPD. Sem RIPD
> e política de retenção documentados, o cliente âncora (RVB) fica exposto e o produto vira risco de compliance.

## 5. Testes & qualidade

| Prática | Já temos? | Lacuna / Ação | Prioridade |
|---|---|---|---|
| Testes automatizados no CI (pytest/ruff) | ✅ | ok | — |
| Documento de estratégia de teste + meta de cobertura | ❌ | `docs/TESTING.md` (pirâmide, DB real padrão PR#25, harness front 021, meta de cobertura) | P2 |
| Harness front (Vitest+RTL+Playwright) | ✅ task-021 | ok | — |
| Cobertura publicada (badge/relatório) | ⚠️ pytest-cov roda | expor relatório de cobertura no CI | P3 |

## 6. Operação / release

| Prática | Já temos? | Lacuna / Ação | Prioridade |
|---|---|---|---|
| Runbooks operacionais | ✅ `docs/runbooks/` | ok | — |
| Rollback documentado | ✅ `docs/ROLLBACK.md` | manter atualizado | — |
| Keep a Changelog + SemVer | ⚠️ `docs/CHANGELOG.md` existe | padronizar no formato Keep-a-Changelog + adotar SemVer nas releases | P2 |
| Postmortem de incidente (blameless) | ❌ | template `docs/runbooks/POSTMORTEM_TEMPLATE.md` (usar skill incident-response) | P2 |
| Diretriz de atuação do agente | ✅ **[criado]** `docs/DIRETRIZ_OPERACAO_CLAUDE_CODE.md` | ok | — |

## 7. Habilidades/skills disponíveis para manter isto
Já há skills no ambiente que operacionalizam estas práticas — usar em vez de reinventar:
`engineering:documentation` (docs/README/runbook), `engineering:testing-strategy` (docs/TESTING), `engineering:architecture`
(ADR/C4), `engineering:code-review` e o `/security-review` (PRs), `engineering:incident-response` (postmortem),
`operations:runbook` / `operations:process-doc` / `operations:compliance-tracking`, `legal:compliance-check` (LGPD),
`doc-coauthoring` e `skill-creator`.

## Prioridade de execução sugerida
1. **P0 agora:** `SECURITY.md` [feito] · RIPD/LGPD [scaffold feito → revisão jurídica + política de retenção].
2. **P1 na sequência:** CONTRIBUTING/PR template/CODEOWNERS/dependabot [feitos] · SAST (bandit) + SCA no CI.
3. **P2 depois:** THREAT_MODEL · TESTING.md · ARCHITECTURE (C4) · ADR template [feito] · docs/README [feito] · postmortem template · pre-commit.
4. **P3 quando sobrar:** arc42 · diagramas Mermaid · badge de cobertura.

## Fontes (benchmark)
- GitHub Docs — Best practices for repositories: https://docs.github.com/en/repositories/creating-and-managing-repositories/best-practices-for-repositories
- Snyk — 10 GitHub Security Best Practices: https://snyk.io/blog/ten-git-hub-security-best-practices/
- ANPD — Relatório de Impacto à Proteção de Dados (RIPD): https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/relatorio-de-impacto-a-protecao-de-dados-pessoais-ripd
- LGPD em CFTV (boas práticas de retenção/anonimização): https://a3aengenharia.com.br/conteudo/artigos-tecnicos/lgpd-cftv-conformidade/
- Monitoramento do empregado por câmeras e a LGPD: https://almeidaenogueira.com.br/o-monitoramento-do-empregado-por-cameras-e-a-lgpd/
- arc42 + C4 (Documentation as Code) exemplo: https://github.com/bitsmuggler/arc42-c4-software-architecture-documentation-example
- The Ultimate Guide to Software Architecture Documentation: https://www.workingsoftware.dev/software-architecture-documentation-the-ultimate-guide/
