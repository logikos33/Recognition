# ADR-0049 — Pipeline de treino RF-DETR: gaps do ADR-0047 fechados; fallback local real é decisão pendente

**Status:** Proposta — os fixes de código descritos aqui já foram implementados e testados nesta task
(agent/task-086-rf-detr-training-pipeline); a decisão sobre investir em treino local real (seção
"Decisão pendente") está em aberto, aguardando aprovação humana. · **Data:** 2026-07-15 ·
**Autores:** Vitor Emanuel (Logikos) — investigação e proposta por sessão Claude Code (task-086)
**Relaciona:** ADR-0047 (treino LGPD-clean), ADR-0044 (RF-DETR/YOLOX plugável), ADR-0039 (compute providers),
ADR-0048 (task-085, mesmo padrão de investigação C-04)

## Contexto

task-086 pedia: "Treino RF-DETR (dataset COCO versionado) via TrainingCompute (Vast.ai/local — ADR-0039)
→ export ONNX → registry/linhagem. Roboflow cloud = opcional atrás de flag + DPA + anonimização (não
default)." Critério de aceite: "Um treino RF-DETR end-to-end (fallback local) gera ONNX servível;
registry atualizado; sem envio a terceiro por padrão."

Investigação de código (C-04, arquivo por arquivo, mesmo padrão da task-085/ADR-0048) mostrou que **a
maior parte já estava implementada e testada**, de trabalho anterior:

- `training/vast/remote_train.py` — `train_rfdetr()`/`train_yolox()` reais (`pip install rfdetr`,
  Apache 2.0), `model.export()` pra ONNX, validação real com `onnxruntime.InferenceSession.run()`.
  Roda remotamente numa instância Vast.ai via `onstart` (o script inteiro é embutido por heredoc —
  a instância não tem acesso ao repo).
- `services/api/app/infrastructure/queue/tasks/training.py::_run_vast_remote_training` — dispatch REST
  real fechado ponta a ponta: presigned URLs (dataset↓, ONNX/pesos/métricas↑) → instância Vast.ai →
  `remote_train.py` reporta progresso por callback HTTP (`progress-callback`) → `_watch_vast_job`
  faz polling do status no Postgres → ao completar, `dispatch_training` insere em `trained_models`.
  `destroy_instance` sempre roda em `finally` (nunca vaza GPU paga).
- `services/api/app/infrastructure/gpu/training_compute.py` (ADR-0039) — abstração `TrainingCompute`
  com `VastAiProvider` (wrapper validado em produção) e `EdgeProvider` (corretamente marcado
  BLOQUEADO-HARDWARE no próprio docstring, fora de escopo).
- Testes reais cobrindo o ciclo (mock de rede/DB, mas exercitando a lógica de verdade):
  `test_dispatch_vast_real.py`, `test_training_dispatch_task.py`, `test_training_compute.py`.

## Gaps reais encontrados e FECHADOS nesta task

1. **Ultralytics Hub e o fluxo legado Vast+Roboflow (`provision_and_train.sh`) disparavam só por env
   var estar setada no processo Celery**, sem nenhum opt-in por tenant — para QUALQUER tenant sem chave
   Vast.ai própria, se `ULTRALYTICS_HUB_API_KEY` estivesse configurada globalmente no Railway, o
   dispatch caía automaticamente em SaaS de terceiro. Isso viola o espírito do ADR-0047 ("Roboflow
   cloud = opcional, atrás de flag... não default") mesmo não sendo literalmente Roboflow no caso do
   Hub. **Fix:** feature flag por tenant `training_third_party_cloud_enabled`
   (`tenants.feature_flags`, mesmo mecanismo já usado pelo `training_compute_target` do ADR-0039),
   fail-safe (qualquer erro de leitura bloqueia o caminho de risco, nunca libera). Gate aplicado em
   `dispatch_training` (Hub) e em `_dispatch_vast_ai_legacy` (Vast+Roboflow).
2. **`INSERT INTO trained_models` não propagava `framework`/`r2_onnx_key`/`dataset_version_id`**,
   apesar de essas colunas existirem desde a migration 098 — linhagem completa
   (dataset_version → job → framework → artefato R2) ficava incompleta mesmo em treinos reais via
   Vast.ai. **Fix:** INSERT agora seleciona `tj.framework` via join e recebe `dataset_version_id` (já
   era parâmetro de `dispatch_training`); `r2_onnx_key` só é preenchido quando `origin == "vast_ai"`
   (único caso em que `model_path` é de fato um objeto R2 real).
3. **Modelos com `origin == "simulated"` disparavam `evaluate_challenger_model` automaticamente** —
   um artefato fake (ver seção seguinte) competindo/potencialmente substituindo um modelo real no
   registry. **Fix:** o trigger de avaliação campeão×desafiante agora é pulado explicitamente para
   `origin == "simulated"`.

Testes cobrindo os três fixes: `services/api/tests/unit/infrastructure/test_training_dispatch_task.py`
(`TestDispatchPrecedence`, `TestVastAiLegacyThirdPartyGate`, `TestTrainedModelInsertPropagation`,
`TestSimulatedOriginSkipsChallengerEval`) e `test_training_compute.py`.

## Decisão pendente (NÃO implementada nesta task — retornada para aprovação humana)

**`LocalProvider`/`_simulate_training` é simulação pura, não um treino real.** Lido linha a linha:
faz `time.sleep(2)` × 10 steps, calcula métricas fake por fórmula matemática (seno + interpolação
linear), nunca baixa dataset, nunca chama `rfdetr`/`yolox`/`onnxruntime`, nunca gera nenhum arquivo
`.onnx`/`.pth` em disco ou R2. O `model_path` retornado (`models/{job_id}/best.pt`) é uma string que
não aponta pra nenhum artefato real. **O critério de aceite literal da task-086 — "um treino RF-DETR
end-to-end (fallback local) gera ONNX servível" — não é satisfeito por este caminho.**

Isso é, hoje, o comportamento padrão para qualquer tenant sem chave Vast.ai configurada e sem edge
disponível — ou seja, é o fallback mais comum na prática (dev, demo, tenant novo antes de configurar
GPU paga).

Corrigir isso "de verdade" (o `LocalProvider` produzir um RF-DETR realmente treinado, mesmo que
trivial) exigiria trazer `torch`/`rfdetr`/`onnxruntime` — dependências pesadas de treino (peso de
imagem de container, tempo de build, tempo de CPU não trivial mesmo pra poucas épocas/dataset
pequeno) — para o processo Celery worker do `api`/`worker` no Railway, que hoje não tem GPU nem essas
dependências. Isso é uma decisão de custo/infra que não deve ser tomada unilateralmente por uma sessão
de código (mesma disciplina aplicada pela task-085/ADR-0048 ao decidir NÃO subir CVAT/Label Studio sem
necessidade concreta).

### Alternativas para decisão

- **(a) Aceitar o limite, documentar (esta ADR) e não investir mais agora.** `LocalProvider` continua
  sendo simulação de fluxo/UI (útil pra dev/demo/teste de fila), nunca produz modelo real; Vast.ai
  continua sendo o ÚNICO caminho real de treino. Custo: zero. Risco: tenant sem crédito Vast.ai fica
  sem nenhuma forma de treinar um modelo real até configurar GPU paga.
- **(b) Investir em treino local mínimo real** (CPU, poucas épocas, dataset pequeno) — exige adicionar
  `torch`/`rfdetr` a `requirements/worker.txt` (ou criar uma fila/worker dedicado, pra não pesar o
  worker principal com uma dependência gigante usada raramente), aceitar tempo de treino de CPU (pode
  ser lento até pra poucas épocas) e overhead de build/imagem maior no Railway.
- **(c) Adiantar o `EdgeProvider`** (treino no Jetson do cliente, já desenhado no ADR-0039) como o
  "local real" de fato, em vez de investir em CPU no worker cloud — hoje BLOQUEADO-HARDWARE (sem
  Jetson físico pra validar), fora de escopo até a validação de hardware acontecer.

**Recomendação (não é decisão):** (a) por agora — o comportamento simulado já é honesto no código
(`origin="simulated"`, `is_active=FALSE`, agora também sem disparar avaliação campeão×desafiante) e
Vast.ai já é um caminho real, testado e barato o suficiente (GPU spot) pra cobrir o caso de uso
principal. Revisitar (b)/(c) se surgir demanda concreta (ex. cliente sem crédito Vast.ai configurado
que precise de um fallback funcional de verdade).

## Consequências

- Positivas: os três gaps reais de ADR-0047/ADR-0017 encontrados na investigação estão fechados e
  testados; a linhagem do registry (`trained_models`) está completa para treinos reais; nenhum
  artefato simulado entra mais automaticamente na avaliação campeão×desafiante.
- Em aberto: `LocalProvider` continua sem produzir artefato real — documentado explicitamente aqui
  como limite conhecido, não como bug escondido.
- Nenhuma migration nova (colunas de linhagem já existiam desde a 098); nenhum contrato FE↔BE alterado.

## Notas

Investigação completa (arquivo por arquivo) registrada em
`tools/agent-driver/tasks/task-086-rf-detr-training-pipeline.md`, seção "Status (2026-07-15)".
