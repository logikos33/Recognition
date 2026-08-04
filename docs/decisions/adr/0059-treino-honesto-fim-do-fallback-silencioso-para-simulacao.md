# ADR-0059 — Treino honesto: fim do fallback silencioso para simulação; Vast.ai passa a exigir opt-in de nuvem de terceiro

**Status:** Proposta — implementado e testado nesta task (branch `claude/treino-honesto`); aguardando
aprovação humana antes de merge/deploy. · **Data:** 2026-08-04 · **Autores:** Vitor Emanuel (Logikos) —
implementação por sessão Claude Code
**Relaciona:** ADR-0049 (fecha a "decisão pendente"), ADR-0047 (treino LGPD-clean), ADR-0039 (TrainingCompute), ADR-0017 (fail-loud, não fallback silencioso)

## Contexto

ADR-0049 (2026-07-15) documentou e deixou em aberto: `LocalProvider`/`_simulate_training` é simulação
pura (sleep + métricas fabricadas por fórmula, nenhum artefato real gerado) e era, na prática, **o
fallback padrão** para qualquer tenant sem chave Vast.ai configurada — sem nenhuma flag, sem nenhum
sinal ao usuário. Essa é a terceira aparição do "fallback silencioso" no projeto (ADR-0017 já havia
nomeado o padrão duas vezes antes). ADR-0049 recomendou (a) aceitar o limite por ora, com Vast.ai como
único caminho real confiável — mas essa recomendação assumia implicitamente que o dispatch Vast.ai
REST real (`_dispatch_vast_ai`/`_run_vast_remote_training`) **não** era gateado por
`training_third_party_cloud_enabled` (só Hub e o fluxo legado Vast+Roboflow eram).

Esta task ("treino honesto") revisita as duas premissas:

1. Simulação como fallback padrão é inaceitável — mesmo documentado, continua enganando qualquer
   tenant sem GPU configurada (o caso mais comum: dev, demo, tenant novo).
2. Vast.ai **é** GPU de terceiro (pode ser RunPod por baixo — investigação de infra em curso,
   fora de escopo desta task) — tratá-lo como não-terceiro no gate do ADR-0047 era uma inconsistência:
   o caminho de dispatch externo mais usado em produção não tinha nenhum gate de opt-in por tenant.

## Decisão

1. **Simulação só roda com opt-in explícito e inequívoco**: env `TRAINING_SIMULATION_ENABLED=true`
   (nome deliberadamente não ambíguo com nenhuma env de GPU real). `get_training_compute` (ADR-0039)
   não cai mais em `LocalProvider` por default — sem provedor real disponível e sem esse opt-in,
   levanta `RuntimeError` com mensagem clara; `dispatch_training` marca o job `failed` (nunca
   `completed` com um artefato fake). `_simulate_training` replica o mesmo check internamente
   (defesa em profundidade).
2. **`training_third_party_cloud_enabled` (ADR-0047) passa a gatear TODO caminho de dispatch externo**,
   Vast.ai REST real incluído — não só Hub e o fluxo legado. Flag OFF (default) + tentativa de
   dispatch externo = erro alto, nunca simulação nem substituição silenciosa.
3. **Dataset ausente (sem `coco_r2_key` exportado) é erro alto e específico** — `_dispatch_vast_ai`
   não desvia mais automaticamente para `_dispatch_vast_ai_legacy` nesse caso: esse fluxo legado
   treina no dataset **público do Roboflow**, não no dataset do tenant, o que seria uma substituição
   silenciosa tão desonesta quanto simular. `_dispatch_vast_ai_legacy` continua existindo no módulo
   (não deletado — pode ser invocado explicitamente no futuro, ex. endpoint admin dedicado), mas não é
   mais alcançável pelo caminho automático.
4. **Artefato simulado nasce marcado, de forma indelével**, quando a simulação de fato roda (flag
   ligada): `metrics['simulated'] = True` (campo JSONB `metrics` já existente desde a migration 098 em
   `trained_models`, e o mesmo campo em `training_jobs` desde a 003 — nenhuma migration nova) +
   `model_path` com prefixo `SIMULATED_` no filename + badge visual "SIMULAÇÃO" no frontend
   (`apps/frontend/src/pages/TrainingPage.tsx`), nunca no mesmo formato de uma métrica real.

## Consequências

- **Positivo:** nenhum tenant recebe silenciosamente um "modelo" fake achando que é real; nenhum
  tenant tem seu dataset silenciosamente trocado pelo dataset público do Roboflow; a decisão de usar
  GPU de terceiro (custo, dados saindo do perímetro do tenant) é sempre explícita.
- **Operacional (⚠️ requer ação humana antes/durante o rollout):** qualquer tenant que hoje treina via
  Vast.ai REST real **sem** ter `training_third_party_cloud_enabled=true` no `tenants.feature_flags`
  passa a ter os jobs de treino falhando com erro claro após este deploy — incluindo, possivelmente, o
  tenant RVB (cliente âncora). **Verificar/setar a flag para os tenants que já usam treino real antes
  de subir para staging/produção.**
- Nenhuma migration nova (reusa `training_jobs.metrics` e `trained_models.metrics`, JSONB já
  existentes). Nenhum enum renomeado (`GpuProvider` inalterado).
- Testes: `services/api/tests/unit/infrastructure/test_training_compute.py`,
  `test_training_dispatch_task.py`, `test_dispatch_vast_real.py`; frontend
  `apps/frontend/src/test/components/TrainingPageSimulationBadge.test.tsx`.

## Notas

Fecha a "decisão pendente" da ADR-0049 optando por uma variante mais estrita que a (a) recomendada lá:
em vez de aceitar o `LocalProvider` como fallback padrão documentado, ele deixa de ser fallback e passa
a ser opt-in puro — e o próprio Vast.ai, antes tratado como "não-terceiro", passa pelo mesmo gate de
opt-in que Hub/legado já tinham desde o ADR-0047.
