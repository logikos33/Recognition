# D-188 · #375/#293/#259 não mergeados — valor extraído em 17/08, recomendação de fechar

**Data:** 2026-08-17 · **Status:** 📌 dívida/constatação — o #375 continua aberto e conflitante

> **Nota de port.** Corpo verbatim da entrada que os PRs #385/#386 acrescentavam a
> `../REGISTRO_DE_DECISOES.md` — arquivo **congelado**. Lá nascia como `D-118`, número já ocupado na
> `develop`. Portada com número livre; os PRs de origem foram fechados sem merge.

**17/08 · Claude · 📄 análise**

**Extraído.** #375: métrica por classe no worker (migration 098 dormente) + 3 bugfixes de export/executor + entrada
D-102 → reextrair num branch limpo **sobre develop** (que já tem #378), nunca mergear como está. #293: cadastro das
8 câmeras já é operacional; D-33..D-36 já em develop. #259: achado `edge/routes.py:586` (`file.read()` antes da
validação de 5 MB → teto não protege memória) — vale como issue. **Fechar PR é ato do Vitor.**

**Veredito: ⛔ não mergear — recomendar fechar após reextrair.**

## Depois (2026-08-21, no port)

Esta é a única das três entradas portadas que ⛔ **não** envelheceu — e a recomendação ficou mais forte, ⛔ não
mais fraca:

- **#375 segue aberto**, `CONFLICTING`, agora **240 commits atrás** da `develop`, conflitando em
  `training.py` · `runpod_runner.py` · `remote_train.py` · `versioning_v2.py` — os arquivos mais quentes do
  repositório;
- ⚠️ e a **métrica por classe** que era o valor do PR foi medida **antes do #470**, que provou que o produto
  lia o ONNX de cabeça para baixo (tensores trocados, `softmax` sobre coordenadas). Os números daquela época
  precisam ser **remedidos** de qualquer jeito, o que esvazia o motivo de reconciliar 240 commits de conflito.

**Continua sendo ato do Vitor.** O que este registro fixa é que o valor já foi extraído e o custo de mergear
só cresceu.
