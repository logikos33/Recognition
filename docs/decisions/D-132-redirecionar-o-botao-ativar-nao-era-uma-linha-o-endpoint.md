# D-132 · Redirecionar o botão Ativar não era "uma linha" — o endpoint com gate não fazia hot-reload

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente

Os dois caminhos de ativação divergiam em mais do que o gate:

| | `/training/models/<id>/activate` | `/api/v1/models/<id>/activate` |
|---|---|---|
| Gate campeão×desafiante | ⛔ não | ✅ 409 `eval_rejected`, force só admin |
| Publica `model:reload` | ✅ sim | ⛔ **não** |
| Escopo | por `user_id` | por `tenant_id` |

Redirecionar cru teria consertado a governança e **quebrado o deploy do modelo** — o inference-service
seguiria servindo o modelo antigo, em silêncio. Uma falha silenciosa trocada por outra.

**Consertado:** `_publish_model_reload` adicionado ao handler com gate, **depois** o redirecionamento.
A mensagem do 409 foi reescrita para o usuário final (antes dizia "reenvie com `force=true`", jargão de
API que vazava na tela via toast automático do `api.ts`).

**Sobre o endpoint sem gate — recomendação, não executada:** ⏸️ **manter por ora, com aviso no docstring.**
Motivo: o módulo Qualidade tem rota homônima porém distinta (`/api/v1/quality/training/models/<id>/activate`,
por câmera) e nenhum consumidor foi auditado fora do frontend. **Condição para remover:** quando um `grep`
por chamadas a `/training/models/*/activate` em todos os apps do monorepo e nos scripts de ops voltar
vazio por duas rodadas seguidas.
