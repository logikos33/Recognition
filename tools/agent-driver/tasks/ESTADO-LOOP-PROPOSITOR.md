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

## 2026-08-20 · TREINO v9 despachado (marco)

Pré-voo COMPLETO antes do dispatch, na ordem da carta:
1. **#510 consertado e no ar**: reivindicação atômica por `gpu_instance_ref` (reentrega do broker
   sai calada) + terminal não ressuscita ('running' de reentrega nunca sobrescreve completed/failed).
   24 testes verdes. Achado da verificação: `visibility_timeout` default de 1h faz o broker
   reentregar TODO dispatch longo — a guarda não é para o caso raro, é para o caso de todo dia.
2. **FREEZE v9** = `v9-limpo` (train 1291 · val 235 · test 327). O primeiro export saiu com
   **514 frames de val vazando do train** (re-tentativa + shuffle sem semente reescreveu o mesmo
   prefixo — issue #515, versão renomeada `v9-VAZADA-515`). Re-export conferido pela régua
   independente: **zero intrusos, zero interseção nos 3 pares**. v8 conferido retroativamente: limpo.
3. **Régua #509 no zip**: contagem do zip conferida contra `images[]` do COCO baixado por chave
   determinística — nunca pela mesma `list_keys`.

**A verificação adversarial pagou o dia**: o patch original do treino morreria no pip em 100% dos
jobs (`rfdetr==1.9.3` + `transformers<5` = ResolutionImpossible) e foi auditado contra a versão
errada — produção resolve **1.5.2**. Reescrito para a superfície REAL da 1.5.2 (medida em venv
limpo): `lr_drop=15` (cosine não existe), `early_stopping patience=8 use_ema`, export do BEST por
mtime (nome fixo `inference_model.onnx` sobrescreve — diff de conjuntos não detecta). Provado
ponta a ponta no venv 1.5.2 contra o best.pth real: entrada 616, head 14, 3 checks OK.

**imgsz=560** (não 640→616): treinar em 616 mantinha a codificação posicional dimensionada para
560 (PE=37 preso ao pré-treino DINOv2) — candidato forte à localização ruim do #514
(presença 0,82 × IoU 0,28: o modelo sabe O QUE está no frame, não ONDE).

**Tela (banda E) → issue #516** com spec: o 1º draft foi REPROVADO por bloqueador de integridade
(proposta de tipo escondido virava anotação humana automática). Frontend revertido, diff preservado.

Job v9: `4b275fd5` · dataset `v9-limpo` · worker deployado ANTES do dispatch (janela sem pod).
Tetos: 5h / US$5 / missão US$12 (US$0,83 gastos).

### Incidente no 1º dispatch do v9 — pego a tempo, custo US$ 0

O 1º dispatch foi consumido pelo **worker velho**: meu `railway up` rodado DO WORKTREE morre
silenciosamente no "Indexing..." — o `.git` de worktree é um arquivo, o CLI não acha a raiz do
projeto, sobe até o `$HOME`, esbarra em `~/Music` sem permissão e **aborta com exit 0, sem subir
nada**. O deployment ativo continuava sendo o de 3h antes (hash `f0a889bf`, pré-consertos).
Percebido ANTES do pod: `status='stopped'` no job (o recheck pré-`create_pod` honrou) e consulta
fresca ao RunPod: **0 pods, nenhum centavo**. Não era problema de merge/push — o commit `822a9ce2`
estava no remoto; era o deploy.

**Regra nova: `railway up` NUNCA de worktree.** Receita: `git archive <commit>` para diretório
limpo + `railway link` + `up` de lá — e a prova de que subiu é a linha "Uploading..." com URL de
Build Logs; "Indexing..." sozinho = não subiu nada. Verificar SEMPRE por `railway deployment list`
(hash + horário), nunca pelo exit code.

A guarda do #510 teria segurado o estrago do lado do job (o 2º dispatch sairia calado), mas não
teria impedido o pod nascer com o runner VELHO — a ordem "deploy confirmado ANTES do dispatch" é
a defesa real.

### Treino v9 NO AR (job `c4c953e2`, pod `nuzczjwhaai7dr`)

Redispatch limpo após o incidente do worker velho (2º incidente da noite: o 1º redispatch levou um
job_id SUJO — o `.jobv9` capturou "INSERT 0 1" junto do UUID; o dispatch morreu na 1ª query, sem
zip, sem pod, US$ 0. Guarda de sanidade: `assert len(id)==36` antes de todo send_task).

- Callbacks fluindo (época sobe no Postgres — token estável, #510 no ar)
- Régua zip×COCO (#509) passou no build do zip
- **Projeção pela conta certa** (ritmo da ép.1 em diante + preparo separado):
  1,5 min/época · preparo 5 min · pior caso 80 min · esperado com early-stop 30-45 min
  · custo projetado US$ 0,35-0,70 (teto US$5) · timeout 18000s folgado
- Ao terminar: A/B v9-best × treino1-best (harness AP@50 + mesmos 80 frames) — só o vencedor
  roda a base inteira (5650 frames, ~20 min CPU local com prefetch; GPU dispensada por medição)

## 2026-08-20 · ACEITE DA CARTA — Propostas do v9 na BASE INTEIRA ✅

**Treino v9** (job `c4c953e2`): early-stop na **época 22** de 50 (não pagou as 28 que pioravam),
export do BEST @560 direto no pod (#511 fechado no runner), custo real **US$ 0,15** (3090 @ $0,22/h).
Pod se auto-deletou — 0 vivos por consulta fresca. Custo da missão: **US$ 0,98** de US$ 12.

**A/B ida-e-volta** (interseção test-v8∩test-v9 = 0 — split por grupo migra blocos inteiros):
cada modelo medido no SEU campo virgem. treino1: presença 0,73 / IoU **0,29**. v9: presença 0,64 /
IoU **0,49**. Em casa ambos inflam (0,74 e 0,69 de IoU) — decorar a casa é real. **Vencedor: v9**,
pela caixa: proposta aceita vira dado do v10, e caixa do treino1 erra 71% em dado virgem.
A hipótese do PE@560 (#514) se confirmou: IoU honesta subiu 0,29 → 0,49.

**Base inteira**: 5504 frames em 22 min (CPU local + prefetch; pod de inferência dispensado por
medição — gargalo era rede). Limiar por classe calibrado no campo virgem do v9:

| classe | limiar | propostas | leitura honesta |
|---|---|---|---|
| Protetor auditivo | 0,25 | **2045** | forte (precisão presença ~0,75+) |
| mascara | 0,25 | **484** | melhorou com volume; precisão 0,86 @0,50 |
| Óculos | 0,30 | **255** | ok, cobertura baixa |
| **Luvas** | — | **0** | ⛔ nenhum limiar ≥50% precisão. Dado raso: 149 caixas (Botas "boa" tem 415). Falta DADO, não modelo |
| **Botas** | — | **0** | ⛔ idem — e era a que engolia o frame inteiro |

**Filtro de área: 2229 caixas barradas (44,5%)** — quase metade do que o modelo queria propor era
caixa-frame-inteiro. Sem o filtro, a fila teria 5000 propostas com metade de lixo.

**Fila final: 2809 frames com 2959 propostas pendentes** — "Propostas no ar" na base inteira,
por lote (`a3da2b66` + anteriores), com proveniência de modelo/lote em cada proposta.

**Pendências que ficam:** #516 (filtro por classe na tela, spec pronta) · prova HTTP/tela
(precisa `E2E_ANNOT_PASSWORD` no ambiente) · P1 do #510 (registro em trained_models quando a
guarda dispara — issue a abrir) · Luvas/Botas voltam ao propositor quando o DADO crescer.

## 2026-08-21 · Hotfix da fila de 48 (#518) — DEPLOYADO

Relato do Vitor em revisão ao vivo: a fila do estúdio parava em 48. Causa: família #499 —
`openStudioAt` entregava a PÁGINA da galeria (60 → 48 anotáveis) e o estúdio nunca pedia a página 2.
Conserto: reabastecimento contínuo — a galeria entrega uma closure de busca do MESMO filtro
(`ContinuacaoDaFila`); o `TrainingPage` (dono do estado; a galeria desmonta no estúdio) anexa
páginas no sinal `onNearEnd` (≤12 à frente). Deslizamento do #500 tratado: re-busca a página 1
(o filtro `pending_review` encolhe ao revisar) com dedup por id, anexo sempre ao fim (#487).
Contador mostra "· 2.809 na fila". 12 testes vitest (fluxo 48→108 sem repetição) + tsc limpo.
Commit `58bfddee` (Fixes #518) · Frontend DEV `c6af599a` SUCCESS 06:47Z, via git-archive (regra
do railway-up-nunca-de-worktree).

## 2026-08-21 · Seletor de classe no local da caixa — DEPLOYADO

Pedido do Vitor em revisão ao vivo: escolher a classe ONDE a bounding box é desenhada. A paleta
lateral e a rota `/modules/epi/classes` estavam íntegras (global ∪ tenant, conferido no serviço) —
o que faltava era a UI junto à caixa. Menu flutuante ancorado à caixa selecionada (abaixo; acima
quando ela encosta no rodapé), mesmo dataset da paleta; teclas 1-9 continuam valendo.
Commit `6ccbaa5e` · Frontend DEV `c6e12f8e` SUCCESS 07:05Z (via git-archive).
Pergunta do merge respondida: DEV recebe por deploy direto da branch (develop + fixes, develop
tem 0 commits a mais); merge na develop pende do PR #512 (gate humano).

## 2026-08-21 · CICLO v10 — A · números frescos (marco)

**Anotado humano agora (régua do export) vs FREEZE v9:** Protetor auditivo 834→**1909** · mascara
413→**823** · Óculos 255→**433** · Botas 415→**445** · Luvas 149→**184** · Sem Luvas 245→253 ·
Sem protetor 139→247 · Sem mascara 184→220 · Uso incorreto 130→194 · Sem Óculos 79→114.
Das caixas novas, **1414 vieram de proposta aceita** (auditivo 958, mascara 318, Óculos 112, Botas 22,
Luvas 4) — o propositor já é a maior fonte de dado.

**🔴 ACEITAÇÃO (o multiplicador real):** 2008 frames revisados do lote v9 → **80,0% aceitas**
(treino1: 55-79%). Por classe: Botas 93,8% (n=32) · Óculos 85,0% · mascara 82,6% · auditivo 76,8% ·
Luvas 75,0% (n=12). **Por faixa de confiança do v9: 0,25-0,35 → 62% · 0,35-0,50 → 77% ·
0,50-0,65 → 86% · ≥0,65 → 95%** — monotônico: a confiança PREVÊ aceitação (base da "confiança
visível" e de limiar por faixa). Pendentes: 816 frames.

**Luvas: 184 caixas** (+35; rumo a 300 ainda longe — 62% do caminho). Botas 445. Ambas seguem
fora do propositor até passarem a régua de 50% de precisão no campo virgem do v10.

### FREEZE v10 — limpo · e a armadilha do head no fine-tune

`v10-freeze`: **3492 frames** (train 2368 · val 532 · test 592), régua de vazamento ✅ (0 intrusos,
0 interseção nos 3 pares), **14 categorias** (âncora + 13 — "Sem Capacete" voltou).

⚠️ **Fine-tune a partir do v9 NÃO pode reaproveitar a cabeça**: v9 tem 13 saídas e os índices
DESLOCAM no v10 (v9: Luvas=2 · v10: Sem Capacete=2, Luvas=3). Reaproveitar o `class_embed` ensinaria
"índice 2 = Sem Capacete" ao neurônio que aprendeu Luvas — catástrofe silenciosa. Regra para o runner:
`num_classes` vem do DATASET (como o treino normal), nunca do checkpoint; backbone+decoder do v9 entram,
cabeça reinicializa (é o que o loader da 1.5.2 faz quando num_classes difere — e o runner deve LOGAR
isso). O ganho do fine-tune está no backbone/decoder (localização); a cabeça linear reaprende em 2 épocas.

### ⚠️ CORREÇÃO da nota acima — a cabeça NÃO reinicializa, ela FATIA

Lido na wheel da 1.5.2 pela frente fine-tune: `reinitialize_detection_head` não randomiza — faz
repeat+truncate POR ÍNDICE (lwdetr.py:124). Com a mesma taxonomia é identidade; com taxonomia/ordem
diferente a cabeça treinada aponta para a classe ERRADA em silêncio. Logo minha regra "num_classes do
dataset, cabeça reinicializa" estava ERRADA: a 1.5.2 reaproveitaria o head do v9 deslocado.
**Regra certa:** fine-tune exige o dataset com EXATAMENTE a taxonomia do checkpoint (o runner agora
confere `args.class_names` do .pth contra as classes do dataset e RECUSA se diferir — "treino não
pode mentir"). Consequência prática: o v10-freeze (14 cats, "Sem Capacete" no índice 2) não serve
para fine-tune. O único frame com "Sem Capacete" (1 caixa, classe fora da taxonomia RVB — gate de
procedência) foi EXCLUÍDO da curadoria (UPDATE, sem DELETE) e o re-export `v10b-freeze` sai com as
13 categorias do v9 na mesma ordem (o export ordena por class_id). v10-base e v10-ft treinam AMBOS
no v10b — mesmo test split = A/B direto e justo entre eles.

Verificação adversarial do ciclo: 2 frentes aprovadas (confiança visível + toggle H; filtro por
classe #516 com o bloqueador de integridade fechado por teste) · 4 reprovadas com bloqueadores
localizados em conserto (fine-tune: yolox com chave mentia + resolução do ckpt não conferida;
intercalada: loop infinito com cadência inválida + default deve ser DESLIGADO; aba de modelos:
escopo oferecia classe sem suporte; runner: compare-and-swap no UPDATE).

## 2026-08-21 · CICLO v10 — B/D/E entregues no DEV · treinos despachados (marco)

**Commits** (branch `feat/proposta-proveniencia`, push verificado `22a85b55`):
- `ef91571a` feat(training): fine-tune a partir de checkpoint próprio — `hyperparams.init_weights_r2_key`
  → dispatch valida (só rfdetr; prefixo `models/{tenant}/`; sem `..`; exists) e injeta `INIT_WEIGHTS_URL`;
  runner confere taxonomia (class_names do ckpt == dataset) e resolução (ckpt@560 ⇒ imgsz=560) e RECUSA
  se diferir. 18+56 testes.
- `957a1893` feat(frontend): filtro por classe (#516, bloqueador fechado por teste de componente) ·
  confiança visível "· IA NN%" na caixa e no crop · toggle H · intercalação opt-in (loop infinito com
  cadência inválida reproduzido e fechado). 502 testes front, tsc 0.
- `22a85b55` feat(cameras): aba de modelos por câmera — GET/POST `/api/cameras/<id>/model-config` sobre
  `model_deployments.config.classes_scope`; UI `CameraModelScope` (modelo + classes que o modelo de fato
  prevê); cross-tenant 404.

**Deploys DEV via git-archive** (0 pods antes): celery-worker `7d9f5d00` · API-V3 `78a5ad4b` ·
Frontend `347e93c7` — todos SUCCESS 09:29Z.

**Treinos v10** (dataset `v10b-freeze` 42023066, 13 cats = v9, imgsz=560):
- v10-base job `3091cfc9` (hyperparams.variante=v10-base)
- v10-ft job `ce4e1969` (init_weights_r2_key = weights.pth do c4c953e2)
Despachados 09:30Z no worker novo. A/B a seguir: v10-ft × v10-base no test-v10b (virgem para os dois)
e v9 no campo inclinado; quem ganhar propõe só no não-anotado (runner com CAS).

**Gap do lado edge (aba de modelos, honesto):** o escopo de classes por câmera está gravado e a UI
pronta, mas o caminho servido (`tasks/inference.py::_resolve_camera_model` → detector singleton de ENV)
ainda não lê `model_deployments` por câmera nem filtra por `classes_scope` — issue a abrir com file:line.
Corrida inversa do runner (humano aceita por ÍNDICE a vista antiga) — fix certo no backend:
accept-suggestion validar por conteúdo/lote — issue a abrir.

### Treinos v10 em voo — sensor do fine-tune POSITIVO (ép.3)

Pods: base `jo5ya294roaiso` · ft `kjabj59mn9kvud` (régua zip×COCO passou nos dois). Log do ft:
`rfdetr_fine_tune: init=init.pth classes=12` → `Loading pretrain weights` → WARNING de fatiamento
(13 = 12+fundo; identidade com taxonomia igual — era o previsto).
**Mesma época 3: base mAP(EMA) 0,175 · ft 0,292 (1,7×); loss ép.1 base 8,93 × ft 7,06.** O ft parte
de onde o v9 parou — a cabeça e o backbone entraram. Ritmo ~2,5 min/época (2× dados); pior caso
125 min, esperado 40-60 com early-stop; custo projetado ~US$ 0,25 por pod @ $0,22/h.
Issues abertas: #519 (gap edge: inference.py:40-41/382-387/428 lê detector de ENV, não
model_deployments por câmera; sem filtro por classes_scope) · #520 (accept-suggestion por índice).
