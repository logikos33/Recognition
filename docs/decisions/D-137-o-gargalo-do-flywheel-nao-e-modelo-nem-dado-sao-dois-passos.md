# D-137 · O gargalo do flywheel não é modelo nem dado — são dois passos que só existem como API

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Rodada:** auditoria da aba de Treinamento (2026-08-17) · **Status:** ✅ vigente
**Evidência:** clone fresco de `origin/develop` em `/Users/vitoremanuel/Logikos-mutirao/audit-training`,
HEAD `98056cf7`, 111 migrations (máx. `122`). Banco DEV, tenant `rvb`.

O ciclo de treino está **inteiro construído** — captura no edge, extração de NVR, curadoria, estúdio de
anotação, classificação por recorte, propagação SAM+DINOv2, busca OWLv2, export COCO com split por
câmera+dia, dispatch para GPU, verificação de artefato, avaliação campeão×desafiante, hot-reload.

**E produziu 0 modelos ativos.**

Dois passos obrigatórios existem no backend e **não têm nenhuma tela**:

| Passo | Endpoint | Chamador no frontend |
|---|---|---|
| Extração de frames do NVR — origem de **100%** do acervo RVB | `POST /api/v1/recorders/<id>/extract-frames` (`recorders/routes.py:162`) | ⛔ zero — "recorder" não aparece **nenhuma vez** em `apps/frontend/src` |
| Export do dataset COCO — **pré-requisito de todo treino** | `POST /api/v1/datasets/<id>/versions` (`datasets/routes.py:104`) | ⛔ zero — as 14 ocorrências de "dataset" são tooltip, tipo e texto de admin |

**Consequência medida:** 12 training jobs, **9 `failed`** (o dispatch levanta erro correto quando não há
`coco_r2_key`), 2 `completed`, 1 `stopped`. E o beat diário de auto-treino **pula em silêncio** —
`auto_train_skip` é log INFO (`auto_training.py:161-163`), nada chega à tela.

**A decisão:** parar de tratar isto como problema de modelo ou de volume de dados. **É problema de correia.**
Dos 8 itens do TO-BE, **4 são ligar frontend a backend que já existe e já está testado.**

⚠️ **Isto NÃO é "o endpoint não existe".** É o inverso — e a distinção é a que uma rodada anterior errou.
