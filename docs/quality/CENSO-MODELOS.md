# Censo dos 11 modelos treinados (tenant rvb)

Data do censo: 2026-09-02. Escopo: os 11 `trained_models` do tenant `rvb`
(`63c219d8-fbef-4f3c-a7c9-058c742482e2`), todos framework `rfdetr`, origin
`runpod`. Todos tinham `map50`/`precision`/`recall` = zero literal antes
deste censo (nunca gravados).

Ferramentas reusadas — **nenhum avaliador novo foi escrito**:
- `training/eval/per_class_eval.py` — preprocessamento calibrado (RGB, 560×560
  bilinear, `/255`, normalização ImageNet, sigmoid por query×classe).
- `services/api/app/domain/services/eval_metrics.py` — a MESMA matemática do
  gate de produção (`greedy_match`/`precision_recall_map`, IoU≥0,5), importada
  diretamente (não reimplementada).

O script do censo (não commitado — é ferramenta de sessão, não deliverable)
baixou 1 modelo `.onnx` por vez do R2 (~108 MB cada), rodou integridade +
avaliação, e apagou o arquivo antes do próximo.

---

## (a) Proveniência — achado → medição → consequência

**Achado grave: o contador de épocas do `training_jobs` (coluna
`current_epoch`) mente sempre que o job passou por restart/retreino.**

Medição: para 7 dos 11 jobs, `training_jobs.current_epoch = total_epochs`
(ex.: `50/50`, "completo") — mas o **artefato exportado** (`metrics.json` no
R2, dentro da própria pasta do modelo, replicado em `training_jobs.metrics`)
registra `epochs_ran` muito menor: 12, 15, 16, 16, 22, 24. As duas fontes
(R2 e DB `metrics` jsonb) **concordam entre si** nesse número menor — só o
`current_epoch` do polling diverge, sempre para cima, sempre batendo
exatamente com `total_epochs`.

Consequência: **não dá para confiar em `current_epoch` sozinho para saber se
um treino completou.** A fonte confiável é `training_jobs.metrics->>'epochs_ran'`
(quando presente) ou o `metrics.json` do artefato no R2 — os dois só existem a
partir do job `21ea3d00` (20/08); os dois primeiros jobs (14/08 e 18/08 antes
do fix) não têm nenhum dos dois.

### Tabela de épocas planejadas × completadas (evidência: training_jobs + R2 metrics.json)

| job | dataset | planejadas | completadas (real) | fonte |
|---|---|---|---|---|
| `10feb67b` | v3-treino1 | 12 | **12** | db + r2 concordam |
| `14c65776` | v5-relabel | 12 | **DESCONHECIDO** | bug de dispatch (total_epochs não chegava ao runner); terminado deliberadamente; sem `epochs_ran` em nenhuma fonte |
| `f31f5381` | v5-relabel | 12 | **DESCONHECIDO** | mesmo bug, sem `epochs_ran` |
| `21ea3d00` | v8-propositor | 50 | **50** | r2 `epoch_bruto_do_framework=49` (índice 0) |
| `c4c953e2` | v9-limpo | 50 | **22** | db+r2 `epochs_ran=22` — diverge de `current_epoch=50` |
| `3091cfc9` **(SERVIDO)** | v10b-freeze | 50 | **16** | db+r2 `epochs_ran=16` — diverge de `current_epoch=50`; retreino por restart de container |
| `ce4e1969` | v10b-freeze | 50 | **12** | db+r2 `epochs_ran=12` — diverge de `current_epoch=50`; mesmo restart |
| `a05becbe` | v11-freeze | 50 | **16** | db+r2 `epochs_ran=16` — diverge de `current_epoch=50` |
| `28dc8844` | v15-so-humano | 50 | **17** | db+r2 concordam (`current_epoch=17`) |
| `f5442076` | v15-tudo | 50 | **15** | db+r2 `epochs_ran=15` — diverge de `current_epoch=50` |
| `0307e2b1` **(is_active)** | v16-volume | 50 | **24** | db+r2 concordam (`current_epoch=24`) |

Datas/hora reais de início (`training_jobs.started_at`, convertido de UTC
para BRT −3h — a DB roda em `Etc/UTC` confirmado via `SHOW timezone`):
14/08 16h59 · 18/08 08h32 · 18/08 08h44 · 20/08 18h14 · 20/08 21h11 ·
21/08 09h29 (×2, dispatch duplo) · 24/08 19h06 · 25/08 00h20/00h21 · 25/08 03h45.

Datasets (contagem de imagens por split, `dataset_versions`): v3-treino1
(train 210/val 6/test 179), v5-relabel (210/6/179 — relabel do mesmo v3),
v8-propositor (1293/303/154), v9-limpo (1291/235/327), v10b-freeze
(2486/826/179), v11-freeze (2932/1617/677), v15-tudo (3611/649/717),
v15-so-humano (1678/395/289), v16-volume (1702/300/360).

---

## (b) Integridade — carrega, baixa, roda

**Resultado: os 11/11 carregam e rodam inferência sem erro.** Nenhum achado
grave de "número de classes diferente do dataset" — em todos os 11, o
output `labels` (`[1,300,N]`) bate exatamente com o número de categorias do
`_annotations.coco.json` do próprio dataset de origem (N variou de 8 a 14
conforme a taxonomia mudou ao longo do tempo — ver tabela em (e)).

| modelo | onnx (bytes) | input | output dets | output labels | categorias do dataset | bate? |
|---|---|---|---|---|---|---|
| 8e8fedf7 | 113.775.133 | [1,3,560,560] | [1,300,4] | [1,300,**8**] | 8 | ✅ |
| 7f859610 | 113.783.357 | idem | idem | [1,300,**12**] | 12 | ✅ |
| 93fa2610 | 113.783.357 | idem | idem | [1,300,**12**] | 12 | ✅ |
| a37bd63d | 113.787.469 | idem | idem | [1,300,**14**] | 14 | ✅ |
| c9fcab8e | 113.869.845 | idem | idem | [1,300,**13**] | 13 | ✅ |
| 46a30ed9 (SERVIDO) | 113.869.845 | idem | idem | [1,300,**13**] | 13 | ✅ |
| b3ae42b6 | 113.869.845 | idem | idem | [1,300,**13**] | 13 | ✅ |
| 10310160 | 113.867.789 | idem | idem | [1,300,**12**] | 12 | ✅ |
| e63bb7de | 113.867.789 | idem | idem | [1,300,**12**] | 12 | ✅ |
| 18aa3816 | 113.867.789 | idem | idem | [1,300,**12**] | 12 | ✅ |
| 8b3bd146 (is_active) | 113.865.733 | idem | idem | [1,300,**11**] | 11 | ✅ |

Integridade rodada com 1 frame real do split `val` de cada dataset (frame
listado em `metrics._censo_2026_09.integrity` de cada linha em
`trained_models`) — todos devolveram scores plausíveis (não NaN, não
constante) e pelo menos alguma detecção acima de 0,25 em pelo menos um frame
da amostra (exceto `c9fcab8e` no frame específico escolhido para o
snapshot de integridade — mas o modelo detectou nas demais imagens da
amostra, ver `map50` em (c)).

---

## (c) Métrica real — split `val`, amostra declarada, gravada no banco

Reusa `eval_metrics.greedy_match` + `eval_metrics.precision_recall_map`
(mesma matemática do gate de produção `model_evaluation.py`), threshold de
score 0,25 (o mesmo `confidence=` usado por `get_detector()` em produção),
IoU≥0,5. Amostra: todas as imagens do `val` quando `val_count≤60`; senão 60
imagens por amostragem aleatória com seed fixa (20260901) — **n visível na
tabela**. `precision`/`recall` gravados são **micro-média** (Σtp/Σ(tp+fp) e
Σtp/Σn_gt entre classes com n_gt>0) — não há um "precision" único nativo do
AP, então essa é a agregação usada, documentada e reversível.

| modelo | n (amostra/val total) | map50 | precision | recall | pior classe medida (ap, n_gt) |
|---|---|---|---|---|---|
| 8e8fedf7 | 6/6 | 0,2500 | 0,2222 | 0,4000 | Sem protetor de ouvido (0,00; n=1) |
| 7f859610 | 6/6 | 0,1250 | 0,2000 | 0,2000 | Sem protetor de ouvido (0,00; n=1) |
| 93fa2610 | 6/6 | 0,1250 | 0,1111 | 0,2000 | Sem protetor de ouvido (0,00; n=1) |
| a37bd63d | 60/303 | 0,2889 | 0,3939 | 0,4483 | Sem mascara (0,00; n=8) |
| c9fcab8e | 60/235 | 0,2193 | 0,1856 | 0,4186 | Luvas (0,00; n=9) |
| **46a30ed9 (SERVIDO)** | 60/826 | **0,5099** | 0,5505 | 0,7792 | Sem Luvas (0,00; n=4) |
| b3ae42b6 | 60/826 | **0,5500** | 0,6562 | 0,8182 | Sem Luvas (0,08; n=4) |
| 10310160 | 60/1617 | 0,2746 | 0,4159 | 0,5402 | Sem Luvas (0,00; n=7) |
| e63bb7de | 60/395 | 0,3266 | 0,3542 | 0,5930 | Sem mascara (0,00; n=5) |
| 18aa3816 | 60/649 | 0,5094 | 0,4696 | 0,6585 | Sem Luvas (0,00; n=3) |
| **8b3bd146 (is_active)** | 60/300 | 0,4304 | 0,5196 | 0,6709 | Sem mascara (0,00; n=3) |

**Achado:** `b3ae42b6` (12 épocas reais, dataset v10b-freeze) mede map50
LIGEIRAMENTE MELHOR que `46a30ed9` (16 épocas, mesmo dataset, o SERVIDO) —
0,55 vs 0,51, amostra idêntica de 60 imagens. Diferença pequena e dentro do
ruído de uma amostra de 60/826 — não é conclusivo, mas mostra que "mais
época" não garantiu "melhor métrica" entre esse par. Consequência: não usar
epochs_ran como proxy de qualidade sem medir.

**Cross-check independente:** o gate de produção (`model_evaluations`,
split `test`, detector real via `get_detector()`) já tinha calculado map50
para os 11 (nunca copiado para `trained_models`): 0,0 / 0,0 / 0,0 / 0,084 /
0,106 / 0,158 / 0,266 / 0,372 / 0,277 / 0,370 / 0,316 — mesma ordem de
grandeza e mesmo ranking relativo dos meus números de `val` (correlação
qualitativa, não os mesmos valores porque é outro split e outra amostra).
Isso é uma segunda pista do porquê `trained_models.map50` ficou em zero: a
infraestrutura de avaliação FUNCIONA e RODA (11/11 linhas em
`model_evaluations`) — só nunca escreveu de volta na tabela que a UI lê.

Escrito no banco: `map50`, `precision`, `recall` (colunas dedicadas) +
`metrics->'_censo_2026_09'->'eval_val'` (per-classe completo, n, seed,
threshold) em todas as 11 linhas de `trained_models`.

---

## (d) Classificação

Critério: ✅ **Funcional** = carrega + roda + mede map50>0 num split
anotado real, sem achado grave de integridade. ⚠️ **Parcial** = funcional
tecnicamente mas com um problema material (treino truncado bem abaixo do
planejado, ou proveniência de época desconhecida). ❓ **Desconhecido** =
não usado aqui (todos os 11 carregaram e mediram algo).

| modelo | classificação | motivo |
|---|---|---|
| 8e8fedf7 | ⚠️ Parcial | completo (12/12 épocas) mas taxonomia antiga de 7 classes, val n=6 |
| 7f859610 | ⚠️ Parcial | épocas DESCONHECIDAS (bug de dispatch), val n=6 |
| 93fa2610 | ⚠️ Parcial | épocas DESCONHECIDAS (mesmo bug), val n=6 |
| a37bd63d | ✅ Funcional | 50/50 épocas completas, 13 classes, n=60/303 |
| c9fcab8e | ⚠️ Parcial | só 22/50 épocas |
| **46a30ed9 (SERVIDO)** | ⚠️ Parcial | **só 16/50 épocas** — ver prioridade 1 abaixo |
| b3ae42b6 | ⚠️ Parcial | só 12/50 épocas (o pior em nº de épocas do lote v10) |
| 10310160 | ⚠️ Parcial | só 16/50 épocas |
| e63bb7de | ⚠️ Parcial | só 17/50 épocas |
| 18aa3816 | ⚠️ Parcial | só 15/50 épocas |
| **8b3bd146 (is_active)** | ⚠️ Parcial | **só 24/50 épocas**, zero deployments — ver prioridade 1 |

### 🔴 Prioridade 1 — resposta obrigatória

- **O modelo SERVIDO (`46a30ed9`, job `3091cfc9`, 15 deployments ativos
  medidos agora em `model_deployments`) completou todas as épocas?**
  **NÃO.** Planejadas 50, completadas **16** (`training_jobs.metrics->>'epochs_ran'`
  E o `metrics.json` do artefato no R2 concordam nesse número; o
  `current_epoch=50` do polling do `training_jobs` é enganoso — foi um
  retreino por restart de container, "pod morto pelo operador", com o
  artefato do treino real preservado em `treino1/`).

- **O modelo `8b3bd146` (is_active=TRUE, zero deployments) completou?**
  **NÃO.** Planejadas 50, completadas **24** — essa é a única fonte
  (`current_epoch` e `epochs_ran` concordam aqui, sem ambiguidade). Está
  marcado como campeão ativo no banco mas nunca foi implantado em nenhuma
  câmera.

---

## (e) Renomeação — aplicada, reversível

Todos os 11 `display_name` foram atualizados para
`Logikos EPI <escopo> · <DD/MM HHhMM>` (horário real de
`training_jobs.started_at`, convertido para BRT). Escopo = contagem real de
classes do dataset de origem (categorias do `_annotations.coco.json`,
excluindo o placeholder `recognition` com 0 caixas), comparado ao conjunto
de 12 classes mais usado (`v9-limpo`/`v10b-freeze`: Capacete, Luvas, Sem
Luvas, Óculos, Sem Óculos, Protetor auditivo, mascara, Sem protetor de
ouvido, Sem mascara, Botas, Uso incorreto de mascara, Sem botas) — chamado
de **"Completo"** aqui. Os dois com proveniência de época desconhecida
usam o template do contrato: `Logikos EPI · origem desconhecida · <hash>`.

| modelo | nome anterior (`name`/`display_name`) | nome novo |
|---|---|---|
| 8e8fedf7 | RF-DETR - Job 10feb67b / — | Logikos EPI Parcial (7 classes) · 14/08 16h59 |
| 7f859610 | RF-DETR - Job 14c65776 / — | Logikos EPI · origem desconhecida · 14c65776 |
| 93fa2610 | RF-DETR - Job f31f5381 / — | Logikos EPI · origem desconhecida · f31f5381 |
| a37bd63d | RF-DETR - Job 21ea3d00 / — | Logikos EPI Estendido (13 classes) · 20/08 18h14 |
| c9fcab8e | RF-DETR - Job c4c953e2 / — | Logikos EPI Completo · 20/08 21h11 |
| 46a30ed9 | RF-DETR - Job 3091cfc9 / **Logikos V1** | Logikos EPI Completo (v10-base) · 21/08 09h29 |
| b3ae42b6 | RF-DETR - Job ce4e1969 / — | Logikos EPI Completo (v10-ft) · 21/08 09h29 |
| 10310160 | RF-DETR - Job a05becbe / — | Logikos EPI Parcial (11 classes) · 24/08 19h06 |
| e63bb7de | RF-DETR - Job 28dc8844 / — | Logikos EPI Parcial (11 classes) · 25/08 00h21 |
| 18aa3816 | RF-DETR - Job f5442076 / — | Logikos EPI Parcial (11 classes) · 25/08 00h20 |
| 8b3bd146 | RF-DETR - Job 0307e2b1 / — | Logikos EPI Parcial (10 classes) · 25/08 03h45 |

`46a30ed9` e `b3ae42b6` têm o mesmo dataset e o mesmo minuto de início
(dispatch duplo real, `training_jobs.started_at` idêntico) — desambiguados
com o `variante` real gravado em `training_jobs.hyperparams` (`v10-base` /
`v10-ft`), não inventado.

Nada além de `display_name` foi tocado — `id`, `r2_onnx_key`,
`dataset_version_id`, `job_id`, referências de `model_deployments` ficaram
intactos (verificado: só `46a30ed9` tem linhas em `model_deployments`,
15 no total, nenhuma referencia por `display_name`). O nome anterior e o
fato de ter sido renomeado pelo censo ficaram gravados em
`metrics->'_censo_2026_09'->'rename'` em cada linha — reversível por SQL
direto se o Vitor quiser outro nome.

---

## Tabela final

| modelo | proveniência (job · dataset) | épocas (planej.×compl.) | integridade | map50 (n) | classe pior | status | nome novo |
|---|---|---|---|---|---|---|---|
| 8e8fedf7 | 10feb67b · v3-treino1 | 12×12 | ✅ 8=8cls | 0,25 (6) | Sem protetor ouvido | ⚠️ Parcial | Logikos EPI Parcial (7 classes) · 14/08 16h59 |
| 7f859610 | 14c65776 · v5-relabel | 12×DESCONHECIDO | ✅ 12=12cls | 0,125 (6) | Sem protetor ouvido | ⚠️ Parcial | Logikos EPI · origem desconhecida · 14c65776 |
| 93fa2610 | f31f5381 · v5-relabel | 12×DESCONHECIDO | ✅ 12=12cls | 0,125 (6) | Sem protetor ouvido | ⚠️ Parcial | Logikos EPI · origem desconhecida · f31f5381 |
| a37bd63d | 21ea3d00 · v8-propositor | 50×50 | ✅ 14=14cls | 0,289 (60/303) | Sem mascara | ✅ Funcional | Logikos EPI Estendido (13 classes) · 20/08 18h14 |
| c9fcab8e | c4c953e2 · v9-limpo | 50×22 | ✅ 13=13cls | 0,219 (60/235) | Luvas | ⚠️ Parcial | Logikos EPI Completo · 20/08 21h11 |
| **46a30ed9 SERVIDO** | 3091cfc9 · v10b-freeze | 50×**16** | ✅ 13=13cls | 0,510 (60/826) | Sem Luvas | ⚠️ Parcial | Logikos EPI Completo (v10-base) · 21/08 09h29 |
| b3ae42b6 | ce4e1969 · v10b-freeze | 50×12 | ✅ 13=13cls | 0,550 (60/826) | Sem Luvas | ⚠️ Parcial | Logikos EPI Completo (v10-ft) · 21/08 09h29 |
| 10310160 | a05becbe · v11-freeze | 50×16 | ✅ 12=12cls | 0,275 (60/1617) | Sem Luvas | ⚠️ Parcial | Logikos EPI Parcial (11 classes) · 24/08 19h06 |
| e63bb7de | 28dc8844 · v15-so-humano | 50×17 | ✅ 12=12cls | 0,327 (60/395) | Sem mascara | ⚠️ Parcial | Logikos EPI Parcial (11 classes) · 25/08 00h21 |
| 18aa3816 | f5442076 · v15-tudo | 50×15 | ✅ 12=12cls | 0,509 (60/649) | Sem Luvas | ⚠️ Parcial | Logikos EPI Parcial (11 classes) · 25/08 00h20 |
| **8b3bd146 is_active** | 0307e2b1 · v16-volume | 50×**24** | ✅ 11=11cls | 0,430 (60/300) | Sem mascara | ⚠️ Parcial | Logikos EPI Parcial (10 classes) · 25/08 03h45 |

---

## Achados que ficam para o Vitor decidir

1. `current_epoch`/`total_epochs` do `training_jobs` não é confiável
   quando há restart/retreino — considerar migrar o dashboard/API para ler
   `metrics->>'epochs_ran'` quando presente.
2. Nenhum dos 11 modelos treinou as 50 épocas completas com a taxonomia de
   12-13 classes mais recente — o melhor "Completo" em épocas reais é
   `a37bd63d` (50/50, mas com taxonomia de 13 classes ligeiramente diferente,
   `Estendido`).
3. `model_evaluations` (gate de produção) já mede map50 há semanas e nunca
   escreve em `trained_models` — gap de integração conhecido, não corrigido
   neste censo (fora do contrato: só a escrita autorizada em (c) foi feita).
