# D-015 · O treino não pode mentir

**Seção:** Flywheel de treino · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude → aceito · 🔄**

Hoje: `LocalProvider` é `_simulate_training` (`training.py:915-946`) — sleep e métricas fabricadas.
E `dataset_version_id` não chega ao job (`training_service.py:23-50`), então **cai em simulação
silenciosamente** e devolve número inventado.

**Terceira aparição da mesma doença** (após `.get(chave, ProductionConfig)` e o fallback de tenant da
ADR-0017): degradação silenciosa em vez de falha alta.

Decidido: simulação só por flag cujo nome diz simulação · dataset ausente = **erro** · artefato de
simulação marcado de forma indelével no banco, no nome do arquivo e na tela · métrica simulada nunca no
mesmo lugar e formato da real.

**Motivo de ser P0:** o Vitor disse que vai validar quando rodar o primeiro treino. Ele não consegue
validar um sistema que mente.
