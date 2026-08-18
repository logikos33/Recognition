# D-139 · O botão "Ativar" chama o endpoint SEM gate — e o gate já existe, testado

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente

Existem **dois** caminhos de ativação de modelo:

| Caminho | Gate de avaliação |
|---|---|
| `POST /training/models/{id}/activate` — `training/job_handlers.py:265-280` | ⛔ **nenhum** |
| `POST /api/v1/models/{id}/activate` — `models/registry_handlers.py:244-284` | ✅ 409 `eval_rejected` se `verdict='reject'`; `force=true` só admin/superadmin; 404 cross-tenant |

O botão "Ativar" da aba Modelo (`TrainingPage.tsx:244`) chama **o primeiro**.
`trainingService.ts:49` e `useTraining.ts:88` idem. **Nada no frontend chama o segundo.**

E a avaliação campeão×desafiante **roda sozinha a cada treino bem-sucedido**
(`training.py:311-316` dispara `evaluate_challenger_model`), grava `verdict` em `model_evaluations`,
e o resultado **não aparece em lugar nenhum da tela**.

**Resultado:** um modelo que o próprio sistema já reprovou é ativado com um clique, em silêncio.

**A decisão:** redirecionar a chamada do frontend para o endpoint com gate e tratar o 409.
É o item de **maior retorno sobre esforço da rodada** — esforço P, e fecha um furo de governança de modelo.
