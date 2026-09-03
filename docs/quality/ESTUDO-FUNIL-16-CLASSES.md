# Estudo do funil ANOTADO → TREINADO — 16 classes, tenant RVB, módulo EPI

**Data da medição:** 2026-09-02 · **Banco:** DEV (`DATABASE_PUBLIC_URL`) · **Tenant:** `rvb` = `63c219d8-fbef-4f3c-a7c9-058c742482e2`
**Código medido:** `services/api/app/infrastructure/queue/tasks/versioning_v2.py` (branch `v2/treino`, HEAD `75bfcc0f`)

Toda linha numérica abaixo tem a query ou o `arquivo:linha` que a produziu. O que não foi medido está na
seção **NÃO MEDIDO** e está escrito lá, não escondido aqui.

---

## 0. Resumo executivo

O funil **fecha exatamente**: `bruto − curadoria − classe arquivada − rótulo-de-frame = COCO`, classe por
classe, sem resto. Não há perda misteriosa. Há **três** filtros que derrubam anotação, e um deles responde
por 96% de tudo que se perde.

| | caixas |
|---|---:|
| Anotado no banco (RVB, epi) | **7.489** |
| Perdido — frame com `curation_status='excluida'` | 50 |
| Perdido — classe do tenant arquivada (`yolo_classes.archived_at`) | 2 |
| Perdido — **`_e_rotulo_de_frame`** (caixa cobre o frame inteiro) | **1.098** |
| Perdido — procedência (pré-anotação não revisada) | **0** (medido) |
| Perdido — dimensões irresolvíveis | **0** (medido) |
| Perdido — câmera arquivada | **0** (o export não filtra por câmera) |
| **Chega ao COCO (braço de produção)** | **6.339** |

**A perda no treino é real. A perda que o dono LEU na tela é outra coisa — e é pior.** Dois achados
independentes:

**1. No export:** o maior sumidouro é `_e_rotulo_de_frame` — 1.098 caixas (14,7% de tudo), e ele é
**desproporcionalmente cruel com as classes de ausência**: leva 50% de `Sem Luvas`, 54% de `Sem mascara`,
45% de `Sem Óculos`. Para a **variante B** (ausência como classe do detector) esse filtro sozinho apaga
**494 das 1.658 caixas "Sem X" — 30% do material da variante inteira**. Ele descarta **em silêncio**:
o número que a versão registra já é o de depois do corte (§3.1).

**2. 🔴 Na tela:** a comparação que o dono fez cruza **duas telas incompatíveis** — `Classes`
(caixas, filtro nenhum) contra `Cobertura` (frames distintos, filtro do export). E a tela `Cobertura`
tem um **bug de JOIN não escopado por tenant** que **funde três pares de classes e apaga outras três**:
o que ela chama de `Protetor auditivo` é `Protetor auditivo + Luvas`; `mascara` é `mascara + Óculos`;
`Sem protetor de ouvido` é `Sem protetor de ouvido + Sem Óculos`; e `Sem Luvas`, `Capacete` e
`Sem Capacete` **não aparecem**. São 6 linhas onde deveriam ser 13. É o mesmo bug que o export já
corrigiu na task-077 e que não foi propagado (§3.2 — `annotation_repository.py:219-231`).

**3. 🛑 Bloqueio para o novo escopo:** as variantes A e B **não podem compartilhar holdout hoje**.
`datasets/routes.py:152-161` não passa `split_seed`, então cada build sorteia de novo — medido em três
sementes sobre o MESMO pool, o treino de `Sem protetor de ouvido` varia 35% e `Luvas` chega a ficar com
**zero** instâncias no test (§2f). Correção de 6 linhas, e o caminho estável já existe e já é testado.

Duas coisas que o dono suspeitava e que **NÃO estão acontecendo** (medidas, não presumidas):

- **Proposta aceita NÃO está sendo excluída** na rota de produção. `POST /datasets/<id>/versions`
  (`datasets/routes.py:152-161`) não passa `somente_humano`, então vale o default `False`
  (`versioning_v2.py:699`) e as 3.257 propostas aceitas entram. O A/B #536 está honrado.
- **Câmera arquivada NÃO derruba nada.** O filtro foi removido (correção B4) e a ausência dele está
  documentada e deliberada em `versioning_v2.py:82-93`. 72 caixas vivem em câmera `is_active=false` e
  **todas entram** no export.

---

## 1. Tabela das 16 classes — cadeia inteira

Universo: `public.frame_annotations a JOIN public.training_frames tf ON tf.id=a.frame_id`,
`tf.tenant_id = <rvb>`. Todas as 7.489 linhas têm `tf.module_code='epi'` e `tf.is_annotated=TRUE`
— esses dois predicados do export derrubam **zero**.

Colunas de perda, na ordem em que o código as aplica:

| # | filtro | onde |
|---|---|---|
| P1 | `tf.curation_status != 'excluida'` | `versioning_v2.py:116` (pool) e `:184` (anotações) |
| P2 | classe custom do tenant arquivada | `versioning_v2.py:185-186` |
| P3 | procedência: `source='manual' OR reviewed_by IS NOT NULL` | `versioning_v2.py:208` |
| P4 | **`_e_rotulo_de_frame`** — `w*h ≥ 0,95` | `versioning_v2.py:254-277`, aplicado em `:232` |
| P5 | dimensões irresolvíveis (`_resolve_dimensions`) | `versioning_v2.py:562-584` |
| P6 | classe sem suporte no split de treino | `versioning_v2.py:813-825` + descarte em `:629` |
| SPLIT | train/val/test — **perda legítima** | `versioning_v2.py:768-771` |

| classe | anotado | P1 cura­doria | P2 classe arq. | P3 proce­dência | P4 rótulo-de-frame | P5 dim | P6 sem-mapa | **COCO** | SPLIT val+test | **treino** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Protetor auditivo | 3.087 | 11 | 0 | 0 | **247** | 0 | 0 | **2.829** | 669 | **2.160** |
| mascara | 972 | 10 | 0 | 0 | **74** | 0 | 0 | **888** | 325 | **563** |
| Botas | 829 | 10 | 0 | 0 | **115** | 0 | 0 | **704** | 193 | **511** |
| Óculos | 635 | 4 | 0 | 0 | **120** | 0 | 0 | **511** | 121 | **390** |
| Sem protetor de ouvido | 536 | 4 | 0 | 0 | **27** | 0 | 0 | **505** | 45 | **460** |
| Sem Luvas | 363 | 2 | 0 | 0 | **183** | 0 | 0 | **178** | 93 | **85** |
| Luvas | 304 | 1 | 0 | 0 | **48** | 0 | 0 | **255** | 70 | **185** |
| Sem mascara | 294 | 2 | 0 | 0 | **158** | 0 | 0 | **134** | 30 | **104** |
| Uso incorreto de mascara | 253 | 3 | 0 | 0 | **31** | 0 | 0 | **219** | 61 | **158** |
| Sem Óculos | 210 | 1 | 0 | 0 | **95** | 0 | 0 | **114** | 14 | **100** |
| Capacete | 3 | 1 | 0 | 0 | 0 | 0 | 0 | **2** | 0 | **2** |
| Sem Capacete | 1 | **1** | 0 | 0 | 0 | 0 | 0 | **0** | 0 | **0** |
| Sem botas | 1 | 0 | **1** | 0 | 0 | 0 | 0 | **0** | 0 | **0** |
| incluir blur | 1 | 0 | **1** | 0 | 0 | 0 | 0 | **0** | 0 | **0** |
| Colete | 0 | — | — | — | — | — | — | **0** | 0 | **0** |
| Sem Colete | 0 | — | — | — | — | — | — | **0** | 0 | **0** |
| **TOTAL** | **7.489** | **50** | **2** | **0** | **1.098** | **0** | **0** | **6.339** | **1.621** | **4.718** |

`Colete` / `Sem Colete` existem em `public.module_classes` (`class_id` 2 e 3) e **nunca foram anotadas**
no RVB — são as classes 15 e 16 das "16 classes". Consistente com a taxonomia RVB = 6 classes
(Capacete/Colete OUT) já registrada no gate de procedência.

**Como a coluna SPLIT/treino foi obtida.** O split é por hash da semente
(`f"{dataset_id}:{version}"`, `versioning_v2.py:769`) — muda a cada versão. Os números acima são de uma
simulação com semente `'rvb-epi:v17'` que **replica o código linha a linha** e foi validada contra o
artefato real `v15-tudo` (`dataset_versions.class_distribution`): Protetor 2.829 simulado vs 2.827 real,
mascara 888/888, Botas 704/704, Óculos 511/510, Sem protetor 505/505, Luvas 255/255, Uso incorreto
219/219, Sem Luvas 178/178, Sem mascara 134/134, Sem Óculos 114/110, Capacete 2/2. Os deltas ≤4 são
anotações criadas entre 25/08 (build do v15) e hoje. **A coluna COCO é determinística; a coluna treino
é dependente da semente** — trocar a versão redistribui.

<details><summary>Query do funil P1–P4 (reprodutível)</summary>

```sql
WITH base AS (
  SELECT a.class_name, a.class_id, a.source, a.reviewed_by,
         a.width AS aw, a.height AS ah,
         tf.is_annotated, tf.curation_status, tf.module_code AS fmod,
         c.id AS yc, c.archived_at
    FROM public.frame_annotations a
    JOIN public.training_frames tf ON tf.id = a.frame_id
    LEFT JOIN public.yolo_classes c
      ON a.class_id >= 100000 AND c.id = a.class_id - 100000
     AND c.tenant_id = tf.tenant_id
   WHERE tf.tenant_id = '63c219d8-fbef-4f3c-a7c9-058c742482e2')
SELECT class_name, count(*) AS anotado,
  count(*) FILTER (WHERE fmod='epi' AND is_annotated
                     AND curation_status <> 'excluida')                       AS pos_P1,
  count(*) FILTER (WHERE fmod='epi' AND is_annotated AND curation_status <> 'excluida'
     AND (class_id < 100000 OR (yc IS NOT NULL AND archived_at IS NULL)))     AS pos_P2,
  count(*) FILTER (WHERE fmod='epi' AND is_annotated AND curation_status <> 'excluida'
     AND (class_id < 100000 OR (yc IS NOT NULL AND archived_at IS NULL))
     AND (source='manual' OR reviewed_by IS NOT NULL))                        AS pos_P3,
  count(*) FILTER (WHERE fmod='epi' AND is_annotated AND curation_status <> 'excluida'
     AND (class_id < 100000 OR (yc IS NOT NULL AND archived_at IS NULL))
     AND (source='manual' OR reviewed_by IS NOT NULL)
     AND NOT (aw*ah >= 0.95))                                                 AS pos_P4
FROM base GROUP BY class_name ORDER BY anotado DESC;
```
</details>

---

## 2. As suspeitas do dono, uma a uma, com número

### (a) Câmera arquivada — **NÃO derruba nada hoje. 72 caixas expostas se a regressão voltar.**

O export **não tem** filtro de câmera. A ausência é deliberada e documentada
(`versioning_v2.py:82-93`, correção da família B4). Medido:

| classe | caixas em câmera `is_active=false` |
|---|---:|
| Óculos | 19 |
| Botas | 14 |
| Sem protetor de ouvido | 13 |
| Sem mascara | 12 |
| Protetor auditivo | 9 |
| Sem Óculos | 5 |
| **total** | **72** |

RVB tem 11 câmeras `is_active=false` e 18 ativas (`select is_active, count(*) from public.cameras where
tenant_id=<rvb> group by 1`). **Nenhuma dessas 72 caixas é perdida** — o `_snapshot_labeled_frames`
(`:105-121`) e o `_fetch_annotations` (`:170-190`) não fazem join com `cameras`.
⚠️ A tabela é `public.cameras`, **não** `public.ip_cameras` (essa não existe neste banco).

### (b) Proposta aceita — **entra no treino. O A/B #536 está honrado na rota de produção.**

Medido, por classe, sobre o pool pós-curadoria:

| classe | `source='manual'` | proposta **aceita** (`pre_annotation` + `reviewed_by` NOT NULL) | proposta **pendente** (`reviewed_by` NULL) |
|---|---:|---:|---:|
| Protetor auditivo | 1.068 | **2.008** | **0** |
| mascara | 497 | 465 | 0 |
| Botas | 437 | 382 | 0 |
| Óculos | 300 | 331 | 0 |
| Luvas | 232 | 71 | 0 |
| Sem protetor de ouvido | 532 | 0 | 0 |
| Sem Luvas | 361 | 0 | 0 |
| Sem mascara | 292 | 0 | 0 |
| Uso incorreto de mascara | 250 | 0 | 0 |
| Sem Óculos | 209 | 0 | 0 |
| **total** | **4.180** | **3.257** | **0** |

Dois fatos que saem daqui:

1. **Zero propostas pendentes.** O gate de procedência (`versioning_v2.py:208`) derruba **0** caixas —
   toda pré-anotação do RVB já foi revisada. O filtro está lá e está correto; hoje ele não corta nada.
2. **Nenhuma classe de ausência tem proposta.** As 1.658 caixas "Sem X" são **100% desenhadas à mão**.
   Isso importa para a variante B: o material de ausência não sofre nada do debate #536.

O braço que **excluiria** proposta aceita é `somente_humano=True` (`versioning_v2.py:196-204`), e ele
**não é alcançável pelo produto**: `grep -rn "somente_humano"` fora de `versioning_v2.py` e dos testes
retorna **vazio**. As versões `v*-so-humano` do banco foram disparadas por script ad-hoc fora do repo.
Se esse braço fosse usado, ele custaria **2.008 caixas de Protetor auditivo** (65% da classe) — é o
único cenário que chega perto da magnitude que o dono descreveu.

### (c) Recorte × frame cheio — **nenhum filtro do export derruba um dos formatos.**

`only_crops` é heurística de dimensão da **fila de anotação**
(`frame_repository.py:694-712`), não do export. O `grep` por `only_crops|is_crop` em
`versioning_v2.py` retorna vazio. Composição real do acervo anotado (recorte = `training_frames.width < 1000`):

| classe | recorte | frame cheio |
|---|---:|---:|
| Protetor auditivo | 2.849 | 227 |
| mascara | 935 | 27 |
| Botas | 806 | 13 |
| Óculos | 618 | 13 |
| Sem protetor de ouvido | 503 | 29 |
| Sem Luvas | 361 | 0 |
| Sem mascara | 292 | 0 |
| Sem Óculos | 209 | 0 |
| Luvas | 274 | 29 |
| Uso incorreto de mascara | 236 | 14 |

**92,5% do acervo anotado é recorte de pessoa.** As classes de ausência são **100% recorte**
(exceto `Sem protetor de ouvido`, 94,5%). Isso é a explicação física do item (d) abaixo: num recorte de
pessoa, marcar "esta pessoa está sem luva" com a caixa cobrindo o recorte inteiro é o gesto natural — e
é exatamente o que `_e_rotulo_de_frame` joga fora.

Também medido: `tf.source` é `'nvr'` para **100%** das 7.437 linhas pós-curadoria; `'upload'` = 0.

### (d) Dedup — **não existe.**

`grep -rn "dedup\|phash\|hash_frame\|distinct"` em `versioning_v2.py` e
`domain/services/dataset_service.py` retorna **vazio**. Nenhuma anotação é perdida por deduplicação
porque não há deduplicação. (O agrupamento por `camera+dia` em `_group_key` (`:296-322`) **não** remove
nada — só mantém frames parecidos no mesmo split.)

### (e) Polaridade / classe fora do catálogo — **2 caixas, e não é polaridade.**

`is_violation` **não aparece** em `versioning_v2.py` (`grep` vazio) — o export não filtra por polaridade.
`Sem Óculos` (`module_classes.class_id=7`) e `Uso incorreto de mascara` (`yolo_classes.id=11`) têm
`is_violation` **NULL** e passam pelo export sem problema.

O que derruba são 2 caixas, por **classe arquivada** (`versioning_v2.py:185-186`):

| classe | `class_id` | `yolo_classes.id` | `archived_at` | caixas perdidas |
|---|---:|---:|---|---:|
| `Sem botas` | 100012 | 12 | 2026-08-22 00:22:32 | **1** |
| `incluir blur` | 100008 | 8 | 2026-08-10 15:20:10 | **1** |

`Protetor auricular` (`yolo_classes.id=5`, arquivada em 2026-08-10) tem **0** anotações — não custou nada.

### (f) Split train/val/test — **perda legítima, 1.621 caixas, separada do resto.**

Coluna `SPLIT val+test` da tabela da §1. Isso **não** é perda: é avaliação. Mas duas ressalvas medidas:

- O split de produção é o **instável** (`estavel=False`), porque `datasets/routes.py:152-161` não passa
  `split_seed`. Ele decide por **posição numa lista embaralhada dos grupos presentes**
  (`versioning_v2.py:416-433`), não por hash do grupo — mudar a população remaneja tudo. É a dívida
  D-165, e é por isso que `Sem Luvas` sai com 85 no treino nesta semente e sairia diferente na próxima.
- `Capacete` tem **2 caixas no mundo**. Se a semente jogá-las fora do `train`, o filtro P6
  (`versioning_v2.py:813-825`) **apaga a classe dos três splits**. Aconteceu de verdade: o `v14-tudo` e o
  `v16-volume` registraram `"__sem_suporte_treino__": ["Capacete"]` no `class_distribution`.

**Quanto o split oscila — medido, três sementes, MESMO pool de 4.983 frames:**

| | `v17` | `v18` | `v19` | amplitude |
|---|---:|---:|---:|---:|
| frames em `train` (pedido: 70%) | 3.763 (75,5%) | 3.280 (65,8%) | 3.649 (73,2%) | **9,7 pp** |
| Protetor auditivo — train | 2.160 | 1.899 | 2.272 | 373 caixas |
| Botas — train | 511 | 454 | 373 | **138 caixas (−27%)** |
| Sem protetor de ouvido — train | 460 | 410 | 299 | **161 caixas (−35%)** |
| Sem mascara — train | 104 | 98 | 76 | 28 caixas |
| **Luvas — test** | 14 | **0** | 58 | classe **cega na avaliação** em `v18` |
| Capacete — train | 2 | 1 | 1 | — |

Trocar só o rótulo da versão muda o treino de `Sem protetor de ouvido` em 35%. Na semente `v18`,
`Luvas` sai com **zero** instâncias no `test` — o `_diagnosticar_split` (`:534-539`) grita, mas o
export segue.

> 🛑 **Consequência direta para o novo escopo (variantes A e B).** O enunciado exige *"mesma base e mesmo
> holdout"*. **Hoje isso é impossível pela rota do produto**: `datasets/routes.py:152-161` não passa
> `split_seed`, então `estavel=False` (`versioning_v2.py:770-771`) e cada build sorteia de novo. Dois
> builds — um por variante — cairiam em holdouts diferentes, e a comparação A×B mediria o sorteio, que é
> exatamente o confundidor que a docstring de `_limita_frames` (`:325-345`) e a de `_split_estavel`
> (`:348-364`) descrevem tendo já queimado o A/B do #536 (1.701 de 2.362 frames trocaram de split).
>
> **Correção mínima:** aceitar `split_seed` no body e repassá-lo, o que liga o caminho `estavel=True`
> que já existe e já é testado:
>
> ```diff
> --- a/services/api/app/api/v1/datasets/routes.py
> +++ b/services/api/app/api/v1/datasets/routes.py
> @@
>      augmentations = body.get("augmentations")
>      if augmentations is not None and not isinstance(augmentations, dict):
>          return error("Campo 'augmentations' deve ser objeto", 400)
> +    split_seed = body.get("split_seed")
> +    if split_seed is not None and not isinstance(split_seed, str):
> +        return error("Campo 'split_seed' deve ser string", 400)
> @@
>          export_format=export_format,
>          module_code=dataset.get("module_code") or "epi",
> +        split_seed=split_seed,
>      )
> ```
>
> Com isso, as duas variantes rodam com o MESMO `split_seed` e herdam a mesma partição por construção —
> é literalmente o que `_split_estavel` foi escrito para garantir (`:359-361`: *"qualquer SUBCONJUNTO
> herda a mesma decisão"*). Sem isso, **não adianta acertar o funil**: o A×B sai sem sentido de novo.

---

## 3. Perdas INDEVIDAS, ordenadas por tamanho

### 3.1 — `_e_rotulo_de_frame` descarta 1.098 caixas **em silêncio** (494 delas de ausência)

**Arquivo:linha:** `services/api/app/infrastructure/queue/tasks/versioning_v2.py:254-277`
(predicado), aplicado em `:232`, avisado só por `logger.warning` em `:245-250`.

```python
# versioning_v2.py:273-277
largura = row.get("width")
altura = row.get("height")
if largura is None or altura is None:
    return False
return float(largura) * float(altura) >= _AREA_ROTULO_DE_FRAME   # 0.95
```

**O que ele derruba, por classe:**

| classe | derrubadas | % da classe | destino |
|---|---:|---:|---|
| Protetor auditivo | 247 | 8,0% | presença |
| **Sem Luvas** | **183** | **50,4%** | **ausência** |
| **Sem mascara** | **158** | **53,7%** | **ausência** |
| Óculos | 120 | 18,9% | presença |
| Botas | 115 | 13,9% | presença |
| **Sem Óculos** | **95** | **45,2%** | **ausência** |
| mascara | 74 | 7,6% | presença |
| Luvas | 48 | 15,8% | presença |
| **Uso incorreto de mascara** | **31** | **12,3%** | **ausência** |
| **Sem protetor de ouvido** | **27** | **5,0%** | **ausência** |
| **total** | **1.098** | **14,7%** | — |
| **subtotal ausência** | **494** | **29,8% de 1.658** | — |

**O predicado está certo; o que está errado é ele ser invisível e terminal.** Uma caixa `[0,0,1,1]`
realmente não é verdade de localização para um detector. Mas:

1. Nada registra a perda onde alguém a veja. O único sinal é um `logger.warning` no pod, que expira com
   o pod. `dataset_versions.class_distribution` mostra o número **depois** do corte — então a tela do
   dono diz "134 Sem mascara" e não diz que 158 foram descartadas. **É exatamente a queixa "mais de
   1.000 anotações não chegam ao modelo": elas não chegam, e o produto não conta que não chegaram.**
2. Para a **variante B**, esse filtro decide sozinho se a classe é treinável: `Sem mascara` cai de 292
   para 134, `Sem Luvas` de 361 para 178.

**Correção mínima proposta (diagnóstico — não aplicada).** Reaproveitar o padrão de chave reservada que
o próprio arquivo já usa em `:867-870` (`__sem_suporte_treino__`) — sem migration, `class_distribution`
já é `jsonb`:

```diff
--- a/services/api/app/infrastructure/queue/tasks/versioning_v2.py
+++ b/services/api/app/infrastructure/queue/tasks/versioning_v2.py
@@ def _sem_rotulos_de_frame(
-    restantes = [a for a in annotations if not _e_rotulo_de_frame(a)]
-    rotulos = len(annotations) - len(restantes)
+    restantes = [a for a in annotations if not _e_rotulo_de_frame(a)]
+    descartadas = [a for a in annotations if _e_rotulo_de_frame(a)]
+    rotulos = len(descartadas)
+    # Perda por classe fica DISPONÍVEL para quem chama registrar na versão —
+    # aviso que só existe no log do pod é silêncio com passos extras (D-165).
+    por_classe: dict[str, int] = {}
+    for a in descartadas:
+        por_classe[a["class_name"]] = por_classe.get(a["class_name"], 0) + 1
@@
-    return restantes, [f for f in frames if str(f["id"]) not in esvaziados]
+    return restantes, [f for f in frames if str(f["id"]) not in esvaziados], por_classe

@@ def build_dataset_version_v2(
-        annotations, frames = _sem_rotulos_de_frame(annotations, frames, tinham_caixa)
+        annotations, frames, rotulos_por_classe = _sem_rotulos_de_frame(
+            annotations, frames, tinham_caixa
+        )
@@ (junto do bloco de :867)
         if sem_treino_registradas:
             class_distribution["__sem_suporte_treino__"] = sorted(
                 sem_treino_registradas
             )
+        if rotulos_por_classe:
+            class_distribution["__rotulo_de_frame_descartado__"] = rotulos_por_classe
```

Mais o mesmo dado em `result` (`:955-973`), ao lado de `split_warnings`. Assinatura de
`_sem_rotulos_de_frame` muda — o único chamador é `:742` e o teste
`services/api/tests/unit/infrastructure/test_export_rotulo_de_frame.py`.

> Isto **recupera a visibilidade, não as caixas**. Recuperar as caixas para o detector é decisão de
> produto (§4), não de bug: um `[0,0,1,1]` sobre recorte de pessoa é veredito de classificação, e a
> ADR-0065/0067 já manda não jogá-lo fora — manda **roteá-lo** para o classificador de recorte.

### 3.2 — 🔴 A aba **Cobertura** funde três pares de classes e some com outras três

Não é perda no treino — é **perda de verdade na tela onde o dono lê os números**. E é a razão pela qual
a conta dele não fecha com o export.

**Arquivo:linha:** `services/api/app/infrastructure/database/repositories/annotation_repository.py:219-231`
(fragmento `_COVERAGE_UNIVERSE`, usado pelas células em `:259-268` e pela procedência em `:279-286`).

```sql
  JOIN yolo_classes c
    ON c.id = CASE WHEN a.class_id >= 100000
                   THEN a.class_id - 100000 ELSE a.class_id END
```

**O JOIN não é escopado por tenant e não distingue catálogo de classe custom.** Para uma classe do
catálogo global (`class_id < 100000`) ele casa `c.id = a.class_id` — resolvendo o id do catálogo contra
a tabela de classes **do tenant**. É exatamente o bug que o export corrigiu na task-077 e documentou em
`versioning_v2.py:136-149` (*"class_id 6 (Óculos, module_classes) caía em yolo_classes.id=6 (mascara do
tenant) e o dataset saía ensinando máscara com foto de óculos"*). **A correção entrou no export e não
entrou no Cobertura.**

Medido, rodando o SQL exato do endpoint contra o DEV:

| linha que a tela mostra | o que ela **realmente** soma | boxes | images |
|---|---|---:|---:|
| `Protetor auditivo` | `Protetor auditivo` (3.076) **+ `Luvas` (303)** | 3.379 | 3.138 |
| `mascara` | `mascara` (962) **+ `Óculos` (631)** | 1.593 | 1.409 |
| `Sem protetor de ouvido` | `Sem protetor de ouvido` (532) **+ `Sem Óculos` (209)** | 741 | 702 |
| `Botas` | `Botas` | 819 | 756 |
| `Sem mascara` | `Sem mascara` | 292 | 286 |
| `Uso incorreto de mascara` | `Uso incorreto de mascara` | 250 | 247 |

**São 6 linhas onde deveriam ser 13.** Além das três fusões:

- **`Sem Luvas` (361 caixas) desaparece por completo.** `class_id=5` → `yolo_classes.id=5` =
  `Protetor auricular`, que está **arquivada** (`archived_at` 2026-08-10) → o predicado
  `c.archived_at IS NULL` (`:229`) apaga a classe inteira da tela.
- **`Capacete` e `Sem Capacete` desaparecem.** `class_id` 0 e 1 não existem em `yolo_classes` → o
  `JOIN` (INNER) descarta.

A tela ainda anuncia, em `CoverageMatrix.tsx:100`: *"Conta igual ao export de treino (só anotação
humana/aprovada, sem classe arquivada)."* **Ela não conta igual** — o export lê `a.class_name` da própria
linha (`versioning_v2.py:172`, task-077) e por isso acerta; o Cobertura reconstrói o nome pelo JOIN e por
isso erra. O script `scripts/ops/verify_coverage_matches_export.py` compara **só totais globais**, que
batem justamente porque a fusão preserva a soma.

**Correção mínima proposta:** aplicar no Cobertura a mesma regra do export — escopar o JOIN por tenant e
só para classe custom, e ler o nome de `a.class_name`:

```diff
--- a/services/api/app/infrastructure/database/repositories/annotation_repository.py
+++ b/services/api/app/infrastructure/database/repositories/annotation_repository.py
@@ _COVERAGE_UNIVERSE
       FROM frame_annotations a
-      JOIN yolo_classes c
-        ON c.id = CASE WHEN a.class_id >= 100000
-                        THEN a.class_id - 100000 ELSE a.class_id END
+ LEFT JOIN yolo_classes c
+        ON a.class_id >= 100000
+       AND c.id = a.class_id - 100000
+       AND c.tenant_id = tf.tenant_id
       JOIN training_frames tf ON tf.id = a.frame_id
  LEFT JOIN public.cameras pc
         ON pc.id = tf.camera_id AND pc.tenant_id = tf.tenant_id
      WHERE tf.tenant_id = %s AND tf.module_code = %s
        AND tf.is_annotated = TRUE AND tf.curation_status <> 'excluida'
-       AND c.archived_at IS NULL
+       AND (a.class_id < 100000
+            OR (c.id IS NOT NULL AND c.archived_at IS NULL))
        AND (COALESCE(a.source, 'manual') = 'manual' OR a.reviewed_by IS NOT NULL)
```

…e trocar `c.id AS class_id, c.name AS class_name` (`:259-260`) por `a.class_id, a.class_name`, com o
`GROUP BY` correspondente (`:268`). Isso alinha o Cobertura ao `_fetch_annotations`
(`versioning_v2.py:170-190`) linha a linha — que é o que a legenda da tela já promete.

⚠️ O `class_name` de `[D]` (`annotation_repository.py:195-208`, `get_classes_with_counts`, usado por
`tenant_class_service.py:76-81`) tem **o mesmo defeito** — `LEFT JOIN frame_annotations a ON a.class_id
= c.id`, sem desfazer o offset e sem escopar por tenant. Mesma correção se aplica.

### 3.3 — `curation_status != 'excluida'` é NULL-inseguro (latente: 0 hoje)

**Arquivo:linha:** `versioning_v2.py:116` e `versioning_v2.py:184`.

`NULL != 'excluida'` avalia para `NULL`, não `TRUE` — todo frame com `curation_status` NULL sairia do
export **em silêncio**. Medido hoje: `select curation_status, count(*) from public.training_frames group
by 1` → `active` 8.984, `excluida` 3.470, **nenhum NULL** (soma 12.454 = total da tabela). Perda atual
**zero**; risco vivo, porque a coluna é nullable e qualquer INSERT que a omita cria o buraco.

```diff
-           AND tf.curation_status != 'excluida'
+           AND tf.curation_status IS DISTINCT FROM 'excluida'
```

(duas ocorrências: `:116` e `:184` — as duas queries precisam concordar, como a própria docstring de
`_fetch_annotations` exige em `:162-168`).

### 3.4 — `frame_annotations.module_code` NULL em 2.852 linhas do RVB (armadilha, não perda)

O export filtra por `tf.module_code` (`:114`, `:182`), **não** por `a.module_code` — por isso não perde
nada. Mas a coluna existe e está NULL em: Protetor auditivo 1.800, mascara 410, Botas 363, Óculos 223,
Luvas 56 = **2.852 linhas**. Qualquer consulta futura que filtre por `a.module_code='epi'` perde
silenciosamente 38% do acervo. **Sem correção proposta no export** (ele está certo); fica registrado
como mina para quem escrever a próxima query — e é candidato natural a um backfill numa migration
`ADD COLUMN`-only.

### 3.5 — A correção B4 (não filtrar por câmera) não tem teste de regressão

**Medido:** `grep -rn "is_active\|_snapshot_labeled_frames" services/api/tests/` → **nenhuma ocorrência**
em teste do export. As menções a `camera` em
`services/api/tests/unit/infrastructure/test_versioning_v2.py:244-292` são todas de `_group_key`
(agrupamento do split), **não** do filtro de pool.

A ausência do filtro de câmera está protegida **só por comentário**
(`versioning_v2.py:82-93`). Já regrediu uma vez (commit `0e3d83ea`, citado no próprio comentário).
Exposição hoje: as **72 caixas** da §2a — e crescendo, porque 11 das 29 câmeras do RVB estão
`is_active=false`.

**Correção mínima:** um teste que afirme que o SQL de `_snapshot_labeled_frames` **não** contém
`is_active`, no mesmo estilo dos guards estáticos já usados na casa:

```python
def test_snapshot_nao_filtra_por_camera_ativa(v2_mod):
    """B4: recorte já minerado e anotado não pode sumir porque a câmera arquivou."""
    sql = inspect.getsource(v2_mod._snapshot_labeled_frames)
    assert "is_active" not in sql
    assert "JOIN cameras" not in sql and "join cameras" not in sql.lower()
```

### 3.6 — `Sem Capacete` perdida por curadoria (1 caixa)

`versioning_v2.py:116`. A única anotação `Sem Capacete` do RVB está num frame marcado
`curation_status='excluida'`. **Não é bug** — é decisão humana de curadoria. Registrado só para o funil
fechar.

---

## 4. Destino das classes de AUSÊNCIA

O escopo mudou: serão treinadas **duas variantes sobre a MESMA base e o MESMO holdout**.

- **Variante A** — 5 classes de presença (`Protetor auditivo`, `mascara`, `Botas`, `Óculos`, `Luvas`),
  ausência **derivada**.
- **Variante B** — presença **+ ausência como classes do detector**.

O funil da §1 serve às duas: é a mesma consulta, o mesmo pool, os mesmos filtros. A diferença é só quais
`class_name` entram no mapa de categorias.

### 4.1 Quanto cada variante recebe

| | classes | caixas anotadas | chega ao COCO | perdido por P4 |
|---|---:|---:|---:|---:|
| **A · só presença** | 5 | 5.827 | **5.187** | 604 |
| **B · presença + ausência** | 10 | 7.483 | **6.337** | 1.098 |
| *só o incremento de ausência (B − A)* | 5 | **1.656** | **1.150** | **494** |

*(1.656 = as 5 classes "Sem X" com volume. Contando também `Sem botas` e `Sem Capacete`, 1 caixa cada,
o acervo de ausência é 1.658 — as duas são perdidas por P2 e P1 respectivamente e não chegam ao COCO.)*

**A variante B ganha 1.150 caixas de ausência hoje — e perderia 494 a mais para `_e_rotulo_de_frame` se
nada mudar.** É a diferença entre `Sem mascara` treinar com 134 exemplos ou com 292.

### 4.2 Os três usos, por classe "Sem X"

Definições medidas, não estimadas:

- **(i) classificador de recorte** — anotação sobre frame que é recorte (`training_frames.width < 1000`).
  É o material que responde "este recorte de pessoa está com/sem X". Inclui as caixas `[0,0,1,1]`, que
  para ESTE uso são o dado certo, não lixo.
- **(ii) cenas-negativas p/ validar a derivação de ausência** — frames distintos com pelo menos uma
  caixa de ausência. É contra eles que a derivação da variante A é conferida.
- **(iii) holdout** — frames distintos com ausência confirmada; a coluna `só ausência` é a fração
  utilizável sem contaminar o holdout com rótulo de presença do mesmo frame.

| classe "Sem X" | caixas | frames distintos | (i) em recorte (caixas / frames) | (ii) cenas-negativas (frames) | (iii) holdout: frames | câmeras distintas | veredito frame-cheio `[0,0,1,1]` | caixa localizada |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sem protetor de ouvido | 532 | 527 | 503 / 498 | 527 | 527 | 20 | 27 | 505 |
| Sem Luvas | 361 | 303 | 361 / 303 | 303 | 303 | 14 | **183** | 178 |
| Sem mascara | 292 | 286 | 292 / 286 | 286 | 286 | 14 | **158** | 134 |
| Uso incorreto de mascara | 250 | 247 | 236 / 234 | 247 | 247 | 11 | 31 | 219 |
| Sem Óculos | 209 | 205 | 209 / 205 | 205 | 205 | 18 | **95** | 114 |
| Sem botas | 1 | 1 | 1 / 1 | 1 | 1 | 1 | 0 | 1 |
| Sem Capacete | 0 | 0 | — (sua única caixa está em frame `excluida`) | 0 | 0 | — | 0 | 0 |
| **total** | **1.645** | **1.569** | **1.602 / 1.527** | **1.569** | **1.569** | — | **494** | **1.151** |

Confere: 494 (veredito frame-cheio) + 1.151 (caixa localizada) = 1.645. Do 1.151, `Sem botas` (1) ainda cai
em P2 (classe arquivada) — por isso a ausência que chega ao COCO é **1.150**, não 1.151. E 1.645 é o
acervo de ausência **pós-curadoria**; o bruto é 1.658, e as 13 de diferença saem todas de P1 (curadoria):
`Sem protetor` 4, `Uso incorreto` 3, `Sem Luvas` 2, `Sem mascara` 2, `Sem Óculos` 1, `Sem Capacete` 1.

**Partição dos frames do acervo** (`bool_or` por `frame_id` sobre o pool pós-curadoria):

| | frames |
|---|---:|
| só ausência | **716** |
| mistos (presença + ausência no mesmo frame) | **545** |
| só presença | **4.141** |

Os **716 frames de só-ausência** são o holdout limpo: nenhuma caixa de presença neles, então usá-los
para medir a derivação da variante A não vaza rótulo. Os **545 mistos** são os que exigem cuidado — o
mesmo frame ensina presença de um EPI e ausência de outro; eles **não** podem ir para o holdout da
variante A sem contaminá-lo.

### 4.3 A consequência prática para as duas variantes

`_e_rotulo_de_frame` (§3.1) é o mesmo filtro que:

- **tira 494 caixas da variante B** (o detector de ausência treina com 70% do que existe), e
- **é exatamente o material do uso (i)** — as 494 caixas `[0,0,1,1]` são vereditos de classificação
  sobre recorte, que é o formato de 100% das classes de ausência (§2c).

Ou seja: **o mesmo dado que o export descarta é o dado que o classificador de recorte precisa.** Não é
uma perda a recuperar para o detector; é um roteamento que hoje não existe. A ADR-0065/0067 já diz que
nada se joga fora — o código honra a metade "não apaga a linha" (`versioning_v2.py:270-271`) e não honra
a metade "manda para o outro uso".

<details><summary>Queries da §4 (reprodutíveis)</summary>

```sql
-- 4.2
WITH b AS (SELECT a.class_name, a.frame_id, a.width aw, a.height ah,
                  tf.width fw, tf.camera_id
   FROM public.frame_annotations a JOIN public.training_frames tf ON tf.id=a.frame_id
  WHERE tf.tenant_id='63c219d8-fbef-4f3c-a7c9-058c742482e2' AND tf.module_code='epi'
    AND tf.is_annotated AND tf.curation_status<>'excluida')
SELECT class_name, count(*) caixas, count(DISTINCT frame_id) frames,
  count(*) FILTER (WHERE fw<1000) em_recorte,
  count(DISTINCT frame_id) FILTER (WHERE fw<1000) frames_recorte,
  count(*) FILTER (WHERE aw*ah>=0.95) veredito_frame_cheio,
  count(*) FILTER (WHERE NOT(aw*ah>=0.95)) caixa_localizada,
  count(DISTINCT camera_id) cameras
FROM b WHERE class_name LIKE 'Sem %' OR class_name LIKE 'Uso incorreto%'
GROUP BY class_name ORDER BY caixas DESC;

-- partição de frames
WITH b AS (SELECT a.class_name, a.frame_id
   FROM public.frame_annotations a JOIN public.training_frames tf ON tf.id=a.frame_id
  WHERE tf.tenant_id='63c219d8-fbef-4f3c-a7c9-058c742482e2' AND tf.module_code='epi'
    AND tf.is_annotated AND tf.curation_status<>'excluida'),
p AS (SELECT frame_id,
        bool_or(class_name LIKE 'Sem %' OR class_name LIKE 'Uso incorreto%') tem_aus,
        bool_or(NOT(class_name LIKE 'Sem %' OR class_name LIKE 'Uso incorreto%')) tem_pres
      FROM b GROUP BY 1)
SELECT count(*) FILTER (WHERE tem_aus AND NOT tem_pres) so_ausencia,
       count(*) FILTER (WHERE tem_aus AND tem_pres) mistos,
       count(*) FILTER (WHERE NOT tem_aus AND tem_pres) so_presenca FROM p;
```
</details>

---

## 5. A divergência com a tela do dono

Os números lidos na tela **não saem deste banco com nenhuma combinação de filtros do export**. Registrado
sem arredondar:

| classe | tela do dono | `class_distribution` mais próxima | COCO medido hoje (braço produção) | treino simulado |
|---|---:|---|---:|---:|
| Protetor auditivo | **1.363** | `v16-volume` = 1.330 · `v12-so-humano` = 1.274 · `v15-so-humano` = 1.027 | 2.829 | 2.160 |
| Sem Luvas | **206** | `v10-freeze` = 253 · `v9-limpo` = 245 · `v12-tudo` = 361 | 178 | 85 |
| Sem mascara | **153** | `v9-limpo` = 184 · `v8-propositor` = 179 | 134 | 104 |
| Óculos + Sem Óculos | **~450** | `v12-tudo` = 612+205 = 817 | 511+114 = 625 | 490 |

### 5.1 O que ficou PROVADO

**Não existe tela "anotadas × no treino".** Varrido `apps/frontend/src` inteiro por `Cobertura`, `COCO`,
`treino`, `anotadas`, `in_training`, `training_count`, `class_distribution` e todos os `<th>`: **nenhum
componente** desenha essas duas colunas juntas. E, no backend, **nada no repo conta caixas por classe
restrito ao split `train`** — `splits["train"]` só é usado para contar FRAMES
(`versioning_v2.py:891`, `:904`, `:963`). Nenhuma rota conta anotações por `dataset_version`, e nenhuma
lê o `_annotations.coco.json` do R2 para contar categorias (quem baixa o COCO —
`model_evaluation.py:314`, `inference.py:765`, `training.py:603-611` — só extrai **nomes**, nunca conta).

**Logo a comparação foi montada à mão pelo dono, cruzando DUAS telas diferentes do mesmo Estúdio**:

| lado | tela | `arquivo:linha` | SQL | filtros |
|---|---|---|---|---|
| **"anotadas"** (3.087 / 363 / 294 / 635 / 209) | Estúdio → **Classes** | `apps/frontend/src/app/estudio/Classes.tsx:182` (`usage_count`, fetch em `:66`) → `modules/routes.py:50-73` → `module_service.py:201` | `annotation_repository.py:172-179` | **NENHUM além de `tenant_id`** |
| **"no treino"** (1.363 / 206 / 153 / ~450) | Estúdio → **Cobertura** | `apps/frontend/src/app/estudio/Cobertura.tsx:41` → `CoverageMatrix.tsx:75` → `training/routes.py:368-371` → `coverage_service.py:78-98` | `annotation_repository.py:219-231` + `:259-268` | módulo, `is_annotated`, `curation_status`, `archived_at`, procedência |

**O lado "anotadas" bate exatamente com a minha medição bruta** (§1, coluna `anotado`) — porque o
`usage_count` não filtra nada. ✅ Confirmado.

**O lado "no treino" está lendo uma tela com o bug da §3.2.** A coluna que a tela desenha por classe é
`images` = `COUNT(DISTINCT a.frame_id)` (`CoverageMatrix.tsx:183`: `{cls.images}/{t.images_per_class} img`)
— **frames, não caixas**. Ou seja, o dono comparou **caixas de um lado com frames do outro**, e o lado
dos frames ainda vinha com classes fundidas.

Isso explica a peça mais estranha do relato dele: **"Óculos 635 + Sem Óculos 209 → ~450 no conjunto"**.
Caixas somam exato; um total *aproximado* só aparece quando se unem **frames distintos**. E, de fato,
`Óculos` nem aparece com esse nome na tela — está somado dentro da linha `mascara` (§3.2).

### 5.2 O que continua SEM ATRIBUIÇÃO

Rodei o SQL exato do Cobertura contra o DEV e **os números não reproduzem 1.363 / 206 / 153**:

| linha da tela | boxes | humana | **images** | dono leu |
|---|---:|---:|---:|---:|
| `Protetor auditivo` (= Protetor + Luvas) | 3.379 | 1.300 | **3.138** | 1.363 |
| `Sem protetor de ouvido` (= + Sem Óculos) | 741 | 741 | **702** | — |
| `Sem mascara` | 292 | 292 | **286** | 153 |
| `Sem Luvas` | *classe não aparece* | — | — | 206 |

Três restrições duras, medidas:

1. Nenhuma das 23 `dataset_versions` do RVB tem `Protetor auditivo = 1363`.
2. `Sem Luvas = 206` **não pode** vir do Cobertura de hoje: a classe **não existe** naquela tela (§3.2).
3. `Sem mascara = 153` é **menor** que qualquer corte atual (292 boxes, 286 images, 134 pós-P4).

**Coincidência anotada, não afirmada como causa:** `Sem Óculos` tem exatamente **206** frames distintos
com `source='manual'`. Dado que a tela funde `Sem Óculos` dentro de `Sem protetor de ouvido`, é
plausível que o dono tenha lido linhas deslocadas — mas **não confirmei**, e não vou apresentar
coincidência como medida.

**Conclusão honesta:** a divergência tem **causa estrutural identificada** (duas telas incompatíveis,
uma delas com classes fundidas, comparando caixa contra frame) e **valores exatos não reproduzidos**.
O mais provável é que os números tenham sido lidos antes de alguma das correções recentes; confirmar
exigiria o estado da tela no dia da leitura, que não existe mais. **Corrigir a §3.2 elimina a
possibilidade de a leitura voltar a acontecer** — que é o que importa daqui para frente.

---

## 6. NÃO MEDIDO

| o quê | por quê |
|---|---|
| **Os valores exatos 1.363 / 206 / 153.** | As telas foram **identificadas** (§5.1) e o SQL delas foi **rodado** (§5.2), mas os números não reproduzem. `Sem Luvas = 206` é impossível na tela atual — a classe não aparece lá. O estado da tela no dia da leitura não é recuperável. Ver §5.2: a causa estrutural está provada, os três valores não. |
| **Conteúdo real dos artefatos COCO no R2.** | Precisa de credencial R2. Todos os números de COCO desta sessão vêm de simulação do código validada contra `dataset_versions.class_distribution`, não da leitura do `_annotations.coco.json`. A validação bate com delta ≤4, mas **não é o mesmo que abrir o arquivo**. |
| **Números de treino por classe estáveis entre versões.** | O split de produção é o instável (`estavel=False`, `datasets/routes.py:152-161` não passa `split_seed`). A coluna "treino" da §1 vale para a semente `'rvb-epi:v17'` e **muda a cada versão**. Para as duas variantes saírem do mesmo holdout, o dispatch **precisa** passar `split_seed` — hoje não passa. |
| **Se `_e_rotulo_de_frame` deve ou não ser relaxado para recorte.** | É decisão de produto (treinar detector com caixa full-crop sobre recorte de pessoa), não achado técnico. Medido só o custo: 1.098 caixas, 494 delas de ausência. |
| **Frames de outros tenants / outros módulos.** | Fora de escopo: toda query filtrou `tf.tenant_id = <rvb>` e `tf.module_code='epi'`. |
| ~~Se existe teste de regressão guardando a ausência do filtro de câmera (B4).~~ | **MEDIDO** — não existe. Ver §3.4. |
