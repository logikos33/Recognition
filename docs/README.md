# Índice da Documentação — Recognition

Mapa dos documentos do projeto. Precedência de regras: **`constitution.md` → `DIRETRIZ_OPERACAO_CLAUDE_CODE.md` → `CLAUDE.md`**.

## Governança / como atuar
- [`../constitution.md`](../constitution.md) — princípios inegociáveis (C-01..C-08).
- [`DIRETRIZ_OPERACAO_CLAUDE_CODE.md`](./DIRETRIZ_OPERACAO_CLAUDE_CODE.md) — como o agente atua (fluxo, equalização, higiene de branch, ADRs, evidência, histórico).
- [`../CLAUDE.md`](../CLAUDE.md) · [`../CONTRIBUTING.md`](../CONTRIBUTING.md) · [`../SECURITY.md`](../SECURITY.md)
- [`BENCHMARK_BOAS_PRATICAS.md`](./BENCHMARK_BOAS_PRATICAS.md) — benchmark de boas práticas + lacunas priorizadas.

## Contexto vivo (retomar o projeto)
- `HANDOFF_CONTINUIDADE.md` — estado, decisões pendentes, próximo passo (chega via PR `fix/admin-users-null-tenant-id`, ainda não em `develop`; linkar quando mergeado).
- `PLANO_EXECUCAO_MIGRACAO_V3.md` — plano-mestre em 6 fases (idem — ainda não em `develop`).
- [`ROADMAP_GO_LIVE.md`](./ROADMAP_GO_LIVE.md) — tasks até o go-live RVB.
- [`../EDGE_DEPLOYMENT_PLAN.md`](../EDGE_DEPLOYMENT_PLAN.md) — fases do edge.

## Arquitetura & decisões
- [`decisions/adr/`](./decisions/adr/) — ADRs 0001–0041 · template: [`0000-template.md`](./decisions/adr/0000-template.md).
- [`DECISIONS.md`](./DECISIONS.md) — decisões menores (não-arquiteturais).
- [`architecture/`](./architecture/) — notas de arquitetura e escala · [`architecture/ARCHITECTURE.md`](./architecture/ARCHITECTURE.md) — visão C4 (Contexto + Contêiner).

## Contrato FE↔BE
- [`API_CONTRACT_MAP.md`](./API_CONTRACT_MAP.md) · [`quality/CONTRATO_FRONT_BACK.md`](./quality/CONTRATO_FRONT_BACK.md)

## Dados
- [`DATABASE.md`](./DATABASE.md) — schema · migrations em `infra/migrations/` (forward-only).

## Segurança & privacidade
- [`../SECURITY.md`](../SECURITY.md) — política de segurança e reporte.
- [`security/LGPD_PRIVACIDADE_CFTV.md`](./security/LGPD_PRIVACIDADE_CFTV.md) — RIPD/LGPD (scaffold, revisão jurídica).
- [`security/THREAT_MODEL.md`](./security/THREAT_MODEL.md) — modelo de ameaças STRIDE (edge↔cloud, isolamento multi-tenant).

## Testes
- [`TESTING.md`](./TESTING.md) — estratégia de testes, política de DB real, harness de frontend, meta de cobertura.

## Operação
- [`runbooks/`](./runbooks/) · [`runbooks/POSTMORTEM_TEMPLATE.md`](./runbooks/POSTMORTEM_TEMPLATE.md) · [`ROLLBACK.md`](./ROLLBACK.md) · [`CHANGELOG.md`](./CHANGELOG.md)

## Design v3
- [`design/recognition-v3/`](./design/recognition-v3/) — fonte única + wiring spec + cobertura.

## Tasks
- `tools/agent-driver/tasks/` — specs · `queue.txt` / `queue-hardware.txt` — filas.
