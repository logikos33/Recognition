# ESTADO — LOOP DO PROPOSITOR (reentrante)

> 1º ato de toda sessão: `git fetch` + ler este arquivo do `origin/develop`. Ele MANDA sobre o prompt.

## Marcos

| marco | estado |
|---|---|
| **M0** · #502 âncora `id:0` no ar | ✅ `bea3a5c2` |
| **M1** · `v8-propositor` congelado | ✅ `57670afd` — train=1293 val=303 **test=154** (o v7 tinha 26) |
| **M2** · pré-voo | ✅ **PASSOU** — âncora OK, filhas OK, ids contíguos, remap idêntico nos 3 splits, fonte batendo exato |
| **M3** · treino 50 ép | 🔄 **bloqueado por deploy do worker** |
| **M4** · runner → propostas | ⏳ |

## 🔴 Custo acumulado: **US$ 0,00** (teto US$ 12 · por pod US$ 5) — nenhum pod disparado

## M3 — onde está travado

Três disparos, três `pending` eternos. Causa achada e consertada (#503, `45b1acdf`):
**`%s` dentro de COMENTÁRIO SQL também é placeholder** — o psycopg2 interpola na string crua, antes
de qualquer parser. Um comentário meu explicando o conserto do #416 continha `` `metrics = %s` `` e
virou o 11º placeholder para 10 parâmetros → `IndexError` no dispatch, **antes do pod** (US$ 0).

⚠️ **O worker ainda não serve o conserto.** O deploy dele começou **3 segundos** depois do merge do
#503 e pegou o commit anterior. `railway redeploy` **não resolve** — ele REUSA a imagem. É preciso um
**build novo por git** (este commit serve de gatilho).

**Ao retomar:** confirmar que o worker roda o commit com o conserto ANTES de re-disparar. O sintoma
de que não roda: `dispatch_training` estoura `IndexError: tuple index out of range` em
`training.py:378`.

## Jobs criados (todos `pending`, sem pod, US$ 0)
`9194b36b` · `41361259` · `35f7e8e5` — nenhum provisionou GPU.

## M1-A · Congelamento é FOTOGRAFIA, ⛔ não cadeado
A `dataset_version` é snapshot imutável **deste** treino. **A anotação ao vivo NÃO para** — o Vitor
pode estar anotando durante o freeze, zero impacto. Todo veredito dado durante/depois **entra no
banco** e estreia na **próxima** versão (candidato de quinta). ⛔ Nada é perdido.

O runner respeita por desenho: ⛔ não propõe sobre veredito humano, com cheque **na escrita**.

⚠️ Implementação futura que pause a anotação para exportar é **BUG**.

**Baseline M1-A.3:** anotações `humana` antes do freeze = **2.656** (eram 2.157 há poucas horas —
o Vitor anotou ~500 durante a sessão, sem qualquer interferência).

## Fatos herdados
`v7-SEM-ANCORA` etiquetado como inválido (⛔ sem DELETE) · propostas `ai` no banco: **zero** ·
flag DINO+SAM **OFF** · pós-proc corrigido (#470, por FORMA) · split do v8 muito melhor que o v7,
mas ainda com suporte fraco em 3 classes no test → números do harness seguem **ruído declarado**.

## Fila depois da missão
D-165 vira código até quinta (gate do candidato) · PR refill+retry da tela de boxes · quinta:
candidato com gate (régua D-163) · sexta: shadow + pacote main.

## 2026-08-20 · ordem de emergência do pod em loop — FECHADA

- **Não havia loop.** Dois pods do mesmo job escreviam no MESMO `pod.log` do R2; o log
  intercalado é que parecia retreino. Causa real: redeploy do worker → Celery reentregou o
  dispatch → 2º dispatch **regravou o `callback_token`** → 403 em todo callback do pod nº 1
  desde 22:16Z (`job_handlers.py:613`, `callback_token_invalido` — não é TTL). Issue #510.
- **Artefatos preservados ANTES de matar**: `treino1/{model.onnx,weights.pth,metrics.json}`
  copiados server-side. Pod `z0z4m9isubxvxg` → DELETE 204; consulta nova: **0 pods vivos**.
- **Custo real US$ 0,83** gravado em `training_jobs.metrics.gpu_cost.actual_usd`. Teto US$12 intacto.
- **Job 21ea3d00 fechado na mão** a partir do artefato (`completed`, 50 ép.).
- **M4 no ar**: lote `c760865a` · 9 propostas em 40 frames (Botas 5, Protetor auditivo 4,
  **zero mascara**) · conf. mediana 0,710 · todas resolvem contra o catálogo (nenhum 500 na tela).
- **Destino da proposta era outro**: `frame_annotations` só aceita `manual|pre_annotation` por
  check constraint. A fila real é o jsonb `training_frames.pre_annotations`, que o
  `annotation_service` converte para `source:'ai'`. A constraint barrou a escrita errada — 0 linhas sujas.
- ⚠️ **O ONNX servido é a ÚLTIMA época, não a melhor** (issue #511): o runner escolhe
  `checkpoint_best_total.pth` mas exporta o modelo em memória. As 9 propostas vieram do pior
  checkpoint. Conversão do `.pth` bom em andamento.
- ⚠️ **Furo de prova**: sem `E2E_ANNOT_PASSWORD` no ambiente, a verificação parou na camada de
  serviço (mapeamento label→class_id provado por SQL). Falta o passe pela fronteira HTTP e a
  conferência na tela.

**Lição — mudança de política varre TODOS os pontos de aplicação, env incluída.** A política de
5h existia no papel enquanto `RUNPOD_MAX_SECONDS=5400` (90 min) matava o treino na época 16.
Trocar a regra sem varrer as variáveis de ambiente é trocar metade da regra.

### Correção do export e o que ela revelou

O ONNX publicado pelo treino tinha **três** defeitos no mesmo ponto (`model.export()` exporta o
objeto como foi *construído*, não como foi *treinado*) — issue #511:
1. última época em vez do `checkpoint_best_total.pth` escolhido logo acima;
2. resolução **560** (default) contra **616** de treino;
3. (consequência) o modelo servido nunca foi o que o harness mediu.

Reexportado localmente do `.pth` bom: head 14 = head do checkpoint, `allclose` dos pesos = True,
entrada 616. Guardado em `treino1/model_best_616.onnx`.

**A/B nos MESMOS 25 frames, limiar 0,55:** pior 9 propostas × BEST 3. Não é qualidade, é
calibração — o sobreajuste deixou o modelo mais confiante, não mais certo. Em **0,35** o BEST
reproduz exatamente o volume do pior em 0,55. O sinal de qualidade continua sendo o AP@50 do
harness (0,366 × 0,290), não a contagem.

**Achado duro (#513): `mascara` dá ZERO em toda a faixa 0,30–0,55.** É a classe do piloto de
sexta. O propositor entrega Botas e Protetor auditivo e não entrega a que importa — ele não
substitui anotação de máscara na preparação do piloto.

## 2026-08-20 · FREEZE v9 (marco)

Snapshot tirado com a query EXATA do export (`versioning_v2.py:160`), não com um `count(*)` solto.
**1849 frames elegíveis · 2847 caixas · 13 classes.** O que entrar depois disto é v10.

| classe | v8 (train+test) | **v9** | Δ |
|---|---|---|---|
| Protetor auditivo | 621 | **834** | +213 |
| Botas | 358 | **415** | +57 |
| mascara | 322 | **413** | +91 ← Vitor anotou hoje |
| Óculos | 164 | **255** | +91 |
| Sem Luvas | 169 | **245** | +76 |
| Sem mascara | 146 | **184** | +38 |
| **Luvas** | 140 | **149** | **+9** |
| Sem protetor de ouvido | 110 | **139** | +29 |
| Uso incorreto de mascara | 91 | **130** | +39 |
| Sem Óculos | 51 | **79** | +28 |
| Capacete / Sem Capacete / Sem botas | 4 | 4 | 0 |

### 🔴 A pergunta das LUVAS, respondida — e a culpa é minha

**Luvas NÃO é classe vazia: 149 caixas em 115 frames**, 7ª em volume, mais que "Sem protetor de
ouvido" (139). O modelo v8 treinou com 119 caixas de Luvas. Ele *sabe* Luvas.

O silêncio nas propostas era **bug do meu runner**: existem DOIS catálogos —
`public.module_classes` (global do módulo epi, `class_id` CRU 0..7: gloves/Luvas=4, glasses/Óculos=6)
e `public.yolo_classes` (custom do tenant, `class_id` = 100000+id). Meu runner só consultava
`yolo_classes`, então descartava toda proposta de Luvas e Óculos como "classe fora do catálogo".
O `annotation_service` (linha 92-106) **já une os dois** e aceita `class_name` e `display_name` —
a tela sempre pôde receber Luvas. Corrigido: as 5 classes de presença agora passam pelo catálogo unido.

**Quanto falta para Luvas existir de verdade:** ela já existe para treinar (149 caixas). O que falta
é comparação — Protetor auditivo tem 5,6× mais caixas (834) e é a classe que o Vitor achou "muito boa".
Como régua honesta: as classes que ele aprovou têm ≥400 caixas; Luvas está em 149. Para Luvas chegar
ao patamar de Botas (415, "boa") faltam ~266 caixas.

### ⚠️ Colisão de namespace — armadilha viva

`frame_annotations.class_id` mistura os dois namespaces. Um `JOIN ... ON a.class_id = c.id` ingênuo
troca rótulo em silêncio: 255 caixas de Óculos leem como "mascara", 149 de Luvas leem como
"Protetor auditivo". Eu caí nessa na primeira contagem desta sessão e reportei números errados antes
de refazer. O export já se defende (resolve nome por `class_name` da própria linha, task-077,
documentado em `versioning_v2.py:130`). Qualquer análise nova tem de fazer o mesmo.
