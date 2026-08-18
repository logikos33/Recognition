# D-177 · Avaliação sem predição é reject, não promote

**Data:** 2026-08-18 · **Status:** ✅ vigente

**O defeito (issue #417).** As 3 avaliações em `public.model_evaluations` tinham `tp=0` **e** `fp=0` em
todas as classes — o modelo não emitiu **nenhuma** predição — e mesmo assim saíram com
`verdict=promote` e `map50=0.0`. O gate do botão **Ativar** aprovava a ausência de medição.

O ramo culpado era literal: `if champion_metrics is None: return PROMOTE`. Sem campeão, promovia sem
olhar contagem nenhuma.

**Decisão.** Um veredito só é veredito se houve o que julgar. Antes de qualquer comparação
campeão×desafiante, a avaliação passa por um **piso de medição** — e não passar é `reject`:

| condição | leitura |
|---|---|
| `per_class` vazio | o split não produziu métrica |
| `tp + fp == 0` | o modelo não emitiu predição — o instrumento não mediu |
| `tp == 0` | nenhum acerto |
| `map50 == 0` | idem, pelo outro lado |
| `images_evaluated == 0` | ⛔ nem grava linha: registrar isso seria registrar ausência como medida |

⚠️ **"Sem campeão" deixa de ser promoção automática.** O primeiro modelo de um tenant também tem de
provar que detecta alguma coisa.

**O piso não explica POR QUE o modelo ficou cego** — só impede que a cegueira vire aprovação. Duas
causas concretas foram consertadas junto (lado do ONNX adotado do próprio modelo em vez de 640
fixo; classes vindas do COCO do dataset em vez de COCO-91). A divergência de pós-processamento
contra o harness calibrado (`training/eval/per_class_eval.py`) — ordem das saídas, `sigmoid` × `softmax`,
`topk` query×classe — **não foi tocada**: exige o artefato para verificar e mexe na inferência ao vivo.
Está registrada como issue própria.

**Descartado:** criar um veredito `indeterminate`. O CHECK `chk_model_evaluations_verdict` só aceita
`pending|promote|reject`, e mudar isso pedia migration — risco desnecessário para dizer o que `reject`
já diz. O motivo do piso vai no log e no `metrics`.
