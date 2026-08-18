# D-016 · 🔴 O provedor de GPU é RunPod, não Vast.ai

**Seção:** Flywheel de treino · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Vitor (correção) · 🔄**

> *"Nós não utilizamos Vast AI, utilizamos RunPod, e já tem uma conexão gerada."*

Os relatórios anteriores diziam "Vast.ai" porque **é o que está escrito no código**:

| Onde | O que diz |
|---|---|
| `config.py:41-43` | `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID` — comentados como *"fallback"* |
| `constants.py:130` | `GpuProvider.VAST_AI` — **não existe valor RUNPOD no enum** |
| `job_handlers.py:260-265` | `gpu_enabled` checa `VAST_API_KEY` / `VAST_AI_API_KEY` / `ULTRALYTICS_HUB_API_KEY` — **não checa `RUNPOD_API_KEY`** |
| `training/vast/` | os scripts reais de treino |
| `training_compute.py` | `_dispatch_vast_ai` / `_dispatch_hub` / `_simulate_training` |

**A validar:** onde está a conexão RunPod · o caminho `vast_ai` é RunPod com nome errado ou são dois
provedores · se o Vitor usa RunPod, `gpu_enabled` reporta GPU desabilitada e **a tela mente**.

⛔ Não renomear o enum agora — `gpu_provider` é coluna com valores gravados (migration 097); é migração
de dados, não refactor.

**Por que é P0:** o contrato vai **nomear o suboperador** que processa as imagens. Documento dizendo
Vast.ai com realidade RunPod = contrato errado sobre transferência internacional de dado pessoal.
