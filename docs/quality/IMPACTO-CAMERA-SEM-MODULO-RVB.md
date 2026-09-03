# Impacto medido: câmera sem vínculo de módulo (tenant RVB, módulo EPI)

**Data da medição:** 2026-09-02 (relógio do servidor: 2026-09-03 00:09 UTC)
**Banco:** DEV (`hayabusa.proxy.rlwy.net`, base `railway`)
**Tenant:** RVB — `63c219d8-fbef-4f3c-a7c9-058c742482e2`
**Escopo:** `public.training_frames` com `module_code='epi'`

> Este documento **mede**. Ele não classifica nada como erro e não decide nada.
> Câmera de Qualidade servindo EPI pode ser legítima — uma delas se chama
> literalmente "Qualidade 01 EPI". **Quem define o vínculo é o dono, pela UI.**

---

## 0. A verdade do schema — onde a associação pode viver

Antes de qualquer número, a armadilha da tenancy híbrida, medida:

| Fato | Valor | Como foi medido |
|---|---|---|
| `rvb.cameras` existe | sim | `pg_class` |
| `rvb.cameras` tem linhas | **0** | `SELECT count(*) FROM rvb.cameras` |
| `public.cameras` do RVB | **29** | `WHERE tenant_id = <rvb>` |
| Frames de EPI do RVB | **12.854** | `training_frames` |
| …com `camera_id` casando em `public.cameras` | **12.854 (100%)** | subquery `IN` |
| …com `camera_id` casando em `rvb.cameras` | **0** | subquery `IN` |
| …com `camera_id` NULL | **0** | — |

E a FK é dura, não convenção:

```sql
SELECT c.conname, n.nspname||'.'||cl.relname AS alvo
  FROM pg_constraint c
  JOIN pg_class cl ON cl.oid = c.confrelid
  JOIN pg_namespace n ON n.oid = cl.relnamespace
 WHERE c.conrelid = 'public.training_frames'::regclass
   AND c.conname = 'training_frames_camera_id_fkey';
-- training_frames_camera_id_fkey | public.cameras
```

**Conclusão do schema:** `rvb.cameras` é vestígio vazio. A câmera do RVB vive em
`public.cameras` (padrão `public.*` + `tenant_id`, ADR-0004/0016), e o frame já
aponta para lá por FK. Uma associação câmera↔módulo tem de viver no mesmo lado —
`public.*` com `tenant_id`. Pendurá-la em `{tenant_schema}.cameras` casaria com
zero linhas.

### E já existe um campo de módulo na câmera — vazio de informação

`public.cameras` tem `module_code` **e** `active_module` (ambos `varchar(50)`,
default `'epi'`). Medido nas 29 câmeras do RVB:

| Campo | Valor | Câmeras |
|---|---|---|
| `module_code` | `'epi'` | **29 de 29** |
| `active_module` | `'epi'` | **29 de 29** |
| linha em `public.quality_camera_config` | nenhuma | **0 de 29** |
| `tenant_modules` habilitados | só `epi` | 1 linha |

Ou seja: os campos existem, são **um só valor por câmera** (não muitos-para-muitos),
**nunca foram preenchidos** e — o que decide — **nenhuma query do pool de treino
os lê** (ver §2). Hoje, o único sinal de que uma câmera é de outro módulo é o
**nome**.

---

## 1. Confirmação dos números do dono (com uma divergência)

### 1.1 Câmeras "Qualidade *" — **CONFERE, exato**

| Câmera | frames EPI | anotados |
|---|---:|---:|
| Qualidade 06 | 1.035 | 579 |
| Qualidade 05 | 1.000 | 598 |
| Qualidade 04 | 79 | 55 |
| Qualidade 01 EPI | 78 | 52 |
| Qualidade 02 | 65 | 49 |
| Qualidade 03 | 50 | 41 |
| **Subtotal** | **2.307** | **1.374** |

Bate dígito a dígito com a evidência do dono.

### 1.2 Estacionamento / portaria / pátio — **DIVERGE: são 7 câmeras, 350 frames**

O contexto listou 6 câmeras / 300 frames. São **7 / 350**. Faltou
**`Estacionamento 01` (50 frames / 0 anotados)**.

| Câmera | frames EPI | anotados |
|---|---:|---:|
| Entrada 02 | 50 | 0 |
| Entrada 03 | 50 | 0 |
| Entrada estacionamento | 50 | 0 |
| Estacionamento 01 | 50 | 0 |
| Estacionamento Motos | 50 | 0 |
| Guarita | 50 | 0 |
| Pátios Fundos | 50 | 0 |
| **Subtotal** | **350** | **0** |

O "0 anotados" continua **medido, não estimado**: nenhuma dessas 350 linhas tem
`is_annotated = true`, e nenhuma tem caixa em `frame_annotations`.

### 1.3 Fechamento do universo

| Grupo (critério: nome da câmera) | câmeras | frames | anotados |
|---|---:|---:|---:|
| A. nome contém "Qualidade" | 6 | 2.307 | 1.374 |
| B. estacionamento / guarita / pátio / "Entrada 0[23]" | 7 | 350 | 0 |
| C. produção e circulação (EPI plausível) | 15 | 10.197 | 4.083 |
| **Total** | **28** | **12.854** | **5.457** |

2.307 + 350 + 10.197 = 12.854 ✓ · 1.374 + 0 + 4.083 = 5.457 ✓

A 29ª câmera (**Porta Pallets**) não aparece: tem **0** frames de EPI.

---

## 2. O predicado real do export — lido no código, não presumido

`services/api/app/infrastructure/queue/tasks/versioning_v2.py`,
`_snapshot_labeled_frames` (frames) e `_fetch_annotations` (caixas):

```sql
WHERE tf.tenant_id = %s
  AND tf.module_code = %s
  AND tf.is_annotated = TRUE
  AND tf.curation_status != 'excluida'
  AND tf.dataset_role = 'pool'
```

caixas, adicionalmente:

```sql
  AND (a.class_id < 100000 OR (c.id IS NOT NULL AND c.archived_at IS NULL))
  AND (a.source = 'manual' OR a.reviewed_by IS NOT NULL)   -- gate de procedência
```

e, em memória, `_e_rotulo_de_frame` derruba a caixa cujo `width * height >= 0.95`
(rótulo de classificação, não de localização).

> **⛔ NÃO EXISTE FILTRO DE CÂMERA EM LUGAR NENHUM DESSE CAMINHO.**
> O próprio docstring de `_snapshot_labeled_frames` diz que nem `is_active` da
> câmera é olhado, por decisão explícita (task B4). Módulo da câmera não é
> consultado porque **não há de onde consultar** (§0).

### Validação do predicado — ele reproduz um build real

Reconstruí o predicado em SQL e comparei com o `frame_count` gravado da versão
`v17a-presenca` (build de hoje, 13:50 UTC):

| Medida | Valor |
|---|---:|
| Pool de hoje (`is_annotated ∧ ≠excluida ∧ role=pool`) | 5.409 |
| …que tinham alguma caixa no banco | 5.406 |
| …que sobraram com ≥1 caixa após procedência + classe + rótulo-de-frame | 4.984 |
| **Frames que o export levaria hoje** | **4.987** |
| `dataset_versions.frame_count` de `v17a-presenca` | **4.983** |
| **Resíduo** | **4** |

O resíduo de 4 **está explicado, não arredondado**: são 4 frames cuja primeira
caixa nasceu **depois** do build, todos da câmera *Entrada galpão alugado*,
`source='pre_annotation'` aceita, gravados em 2026-09-03 00:00:46–00:00:53 UTC.

```sql
SELECT c.name, fa.class_name, fa.source, fa.created_at, fa.frame_id
  FROM frame_annotations fa
  JOIN training_frames tf ON tf.id = fa.frame_id
  JOIN cameras c ON c.id = tf.camera_id
 WHERE tf.tenant_id = '63c219d8-…' AND tf.module_code='epi'
   AND fa.created_at > '2026-09-02 13:50';
-- 4 linhas, todas "Entrada galpão alugado"
```

4.987 − 4 = **4.983 = frame_count de v17a**. O predicado reconstruído é o
predicado real.

---

## 3. Tabela por câmera — frames, anotados, caixas, e o que treinou

`caixas_no_último_treino` = caixas elegíveis criadas antes de
**`v17b-ausencia`** (`93e699ce…`, build 2026-09-02 13:59:40 UTC), a versão que
gerou o modelo mais recente.

| Câmera | frames EPI | anotados | caixas | caixas elegíveis hoje | caixas no último treino |
|---|---:|---:|---:|---:|---:|
| Entrada Expedição | 2.638 | 543 | 829 | 570 | 570 |
| Entrada Usinagem Madeira 2 | 1.599 | 831 | 1.136 | 1.091 | 1.091 |
| Entrada Preparação | 1.044 | 365 | 491 | 430 | 430 |
| **Qualidade 06** | **1.035** | **579** | **660** | **587** | **587** |
| Corredor Lateral usinagem Madeira | 1.017 | 617 | 851 | 743 | 743 |
| Entrada Usinagem Madeira 01 | 1.015 | 522 | 875 | 635 | 635 |
| Corredor Segurança do trabalho | 1.009 | 526 | 655 | 631 | 631 |
| **Qualidade 05** | **1.000** | **598** | **697** | **640** | **640** |
| Sala de Colagem | 525 | 304 | 423 | 332 | 332 |
| Entrada WC Usinagem Papelão | 346 | 135 | 250 | 105 | 105 |
| Espaço de convivência | 339 | 67 | 74 | 74 | 74 |
| Montagem Artefatos Madeira | 324 | 72 | 122 | 122 | 122 |
| Entrada Expedição 02 | 94 | 28 | 34 | 34 | 34 |
| **Qualidade 04** | **79** | **55** | **87** | **87** | **87** |
| **Qualidade 01 EPI** | **78** | **52** | **66** | **66** | **66** |
| Manutenção | 72 | 36 | 58 | 58 | 58 |
| Galpão Alugado Saida | 65 | 27 | 59 | 21 | 21 |
| **Qualidade 02** | **65** | **49** | **67** | **67** | **67** |
| Galpão Alugado Entrada | 60 | 5 | 12 | 3 | 3 |
| Entrada 02 | 50 | 0 | 0 | 0 | 0 |
| Entrada 03 | 50 | 0 | 0 | 0 | 0 |
| Entrada estacionamento | 50 | 0 | 0 | 0 | 0 |
| Entrada galpão alugado | 50 | 5 | 5 | 5 | 1 |
| Estacionamento 01 | 50 | 0 | 0 | 0 | 0 |
| Estacionamento Motos | 50 | 0 | 0 | 0 | 0 |
| Guarita | 50 | 0 | 0 | 0 | 0 |
| Pátios Fundos | 50 | 0 | 0 | 0 | 0 |
| **Qualidade 03** | **50** | **41** | **42** | **42** | **42** |
| *(Porta Pallets)* | 0 | 0 | 0 | 0 | 0 |

**Totais:** 12.854 frames · 5.457 anotados · 7.493 caixas ·
**6.343 elegíveis hoje** · **6.339 no último treino** (diferença = as 4 caixas
de 00:00 UTC citadas em §2).

Por grupo:

| Grupo | câmeras | caixas | elegíveis hoje | no último treino |
|---|---:|---:|---:|---:|
| A. nome contém "Qualidade" | 6 | 1.619 | **1.489** | **1.489** |
| B. estacionamento / portaria / pátio | 7 | 0 | 0 | 0 |
| C. produção e circulação | 15 | 5.874 | 4.854 | 4.850 |

1.489 + 4.850 = **6.339** = o total reconstruído do build de `v17b`. Fecha.

> **Nota sobre "caixas" vs "caixas elegíveis":** a diferença (7.493 → 6.343) é
> quase toda rótulo-de-frame (`w·h ≥ 0,95`, a aba Classificar) e pré-anotação
> não revisada. Não é filtro de câmera.

---

## 4. A pergunta que decide a limpeza

> **Alguma anotação de câmera de outro módulo já treinou um modelo?**

### **SIM — para as 6 câmeras "Qualidade *". 1.489 caixas, em 11 modelos.**

Reconstrução por carimbo de tempo (predicado validado em §2), só de versões
que têm ≥1 modelo treinado:

| dataset_version | build | modelos | caixas totais | **caixas de câmera "Qualidade *"** | modelo(s) |
|---|---|---:|---:|---:|---|
| v3-treino1 | 14/08 | 1 | 566 | **49** | Logikos EPI Parcial (7 classes) · 14/08 16h59 |
| v5-relabel | 18/08 | 2 | 566 | **49** | …origem desconhecida · 14c65776 · f31f5381 |
| v8-propositor | 20/08 | 1 | 2.154 | **275** | Logikos EPI Estendido (13 classes) · 20/08 18h14 |
| v9-limpo | 20/08 | 1 | 2.198 | **275** | Logikos EPI Completo · 20/08 21h11 |
| v10b-freeze | 21/08 | 2 | 4.177 | **701** | Logikos EPI Completo (v10-base) e (v10-ft) · 21/08 09h29 |
| v11-freeze | 24/08 | 1 | 6.046 | **1.370** | Logikos EPI Parcial (11 classes) · 24/08 19h06 |
| v15-tudo | 25/08 | 1 | 6.330 | **1.489** | Logikos EPI Parcial (11 classes) · 25/08 00h20 |
| v15-so-humano | 25/08 | 1 | 6.330¹ | **1.489**¹ | Logikos EPI Parcial (11 classes) · 25/08 00h21 |
| v16-volume | 25/08 | 1 | 6.332¹ | **1.489**¹ | Logikos EPI Parcial (10 classes) · 25/08 03h45 |
| v17a-presenca | 02/09 | 1 | 6.339² | **1.489**² | Logikos EPI 5 classes · 02/09 17h22 |
| v17c-partes | 02/09 | 1 | 6.339² | **1.489**² | Logikos EPI 10 classes · 02/09 21h49 |
| v17b-ausencia | 02/09 | 1 | 6.339² | **1.489**² | Logikos EPI 10 classes · 02/09 22h17 |

¹ provavelmente braço `somente_humano=True` (só `source='manual'`) — o flag não é
gravado no banco; o indício é `frame_count = 2.362` contra 4.977 do braço padrão
do mesmo dia. A coluna acima usa o braço padrão. **No braço só-humano as câmeras
"Qualidade *" contribuem 470 caixas** (Q05 220 · Q06 99 · Q04 69 · Q02 57 ·
Q01-EPI 22 · Q03 3) — esse número é medido. Em nenhum dos dois braços o número é
zero, que é o que a pergunta decide.

² as variantes v17 remapeiam classes (5/10 classes), então o total de caixas do
COCO não é comparável 1:1 com o `class_distribution` gravado. O número de caixas
**de origem "Qualidade *"** não depende do remapeamento e continua válido.

**Modelo ativo hoje:** `8b3bd146…` — *Logikos EPI Parcial (10 classes) · 25/08
03h45*, treinado de `v16-volume` (`is_active = true`, único ativo do tenant).
Caixas de câmera "Qualidade *" nele: **470 no braço só-humano, 1.489 no braço
padrão**. Qual dos dois: **NÃO MEDIDO** — o flag `somente_humano` **não é
gravado** em `dataset_versions` (`augmentations` e `metadata_key` estão NULL nas
26 versões). O indício é que `v16-volume.frame_count = 2.362`, idêntico a
`v15-so-humano` e `v14-so-humano`, e o braço padrão do mesmo dia dá 4.977 — mas
isso é **inferência**, não leitura.

### **NÃO — para as 7 câmeras de estacionamento/portaria/pátio.**

**0 caixas.** As 350 imagens foram coletadas, mas nunca anotadas. **Nenhum
modelo foi treinado com elas.** Isso é medido, não estimado: nenhuma linha em
`frame_annotations` referencia frame dessas câmeras.

### ⚠️ NÃO MEDIDO — a membresia exata de cada versão

A amarração `caixa → dataset_version` **não existe no banco**:

```
ERROR:  column "split_membership" does not exist
```

A `migration 131_dataset_versions_split_membership.sql` está **nesta branch mas
não aplicada no DEV**, e nenhuma versão anterior a ela gravaria membresia de
qualquer forma. O COCO exportado está no R2 (`coco_r2_key` preenchido em todas
as 26 versões) mas **não há credencial de R2 nesta máquina** para abri-lo.

Portanto a tabela de §4 é **RECONSTRUÇÃO por carimbo de tempo**, não leitura de
membresia. O que a sustenta:

1. O predicado reconstruído reproduz o `frame_count` de um build real com
   resíduo 4, e os 4 estão nominalmente identificados (§2).
2. Os totais de caixa reconstruídos (6.339) fecham com a soma por grupo.
3. Nenhum frame do tenant teve `curation_updated_at` alterado depois do último
   build (`0` linhas), e **nenhum** frame anotado está marcado `holdout` — os
   150 `dataset_role='holdout'` do tenant são todos frames **não anotados**.
   Ou seja: o estado que o predicado lê não mudou desde os builds.

O que ela **não** prova: em qual *split* (train/val/test) cada caixa caiu. Se o
dono precisar disso, o caminho é aplicar a migration 131 e usar builds novos —
o passado é irrecuperável, como a própria migration documenta.

---

## 5. Câmeras candidatas por módulo — **SUGESTÃO, o dono confirma na UI**

**Critério único e explícito: o NOME da câmera.** Não há nenhum outro dado no
banco que diga o módulo (§0: `module_code`/`active_module` valem `'epi'` para as
29, `quality_camera_config` está vazia). Este é um chute de leitura de nome, não
uma medição.

### Candidatas a **Qualidade** — critério: `name LIKE 'Qualidade%'`

`Qualidade 01 EPI` · `Qualidade 02` · `Qualidade 03` · `Qualidade 04` ·
`Qualidade 05` · `Qualidade 06`

> ⚠️ **`Qualidade 01 EPI` tem "EPI" no próprio nome.** É o caso que o dono já
> antecipou: uma câmera pode servir dois módulos. Aqui o critério de nome se
> contradiz sozinho — só o dono resolve.

### Candidatas a **Contagem / carga-descarga** — critério: nome com "estacionamento", "guarita", "pátio", ou "Entrada 0[23]"

`Entrada estacionamento` · `Estacionamento 01` · `Estacionamento Motos` ·
`Guarita` · `Pátios Fundos` · `Entrada 02` · `Entrada 03`

> ⚠️ **`Entrada 02` e `Entrada 03` entraram neste grupo só porque a evidência do
> dono as agrupou aí.** O nome sozinho não diz estacionamento. Podem ser entradas
> de produção — nesse caso são EPI.
> ⚠️ Todas as 7 estão com `is_active = false` em `public.cameras`.

### Candidatas a **EPI** — critério: as demais

`Corredor Lateral usinagem Madeira` · `Corredor Segurança do trabalho` ·
`Entrada Expedição` · `Entrada Expedição 02` · `Entrada Preparação` ·
`Entrada Usinagem Madeira 01` · `Entrada Usinagem Madeira 2` ·
`Entrada WC Usinagem Papelão` · `Entrada galpão alugado` ·
`Espaço de convivência` · `Galpão Alugado Entrada` · `Galpão Alugado Saida` ·
`Manutenção` · `Montagem Artefatos Madeira` · `Porta Pallets` ·
`Sala de Colagem`

---

## 6. Onde a coleta entra (para quem for implementar o filtro)

Só duas linhas gravam `training_frames`, ambas via
`FrameRepository.create` (`services/api/app/infrastructure/database/repositories/frame_repository.py:65,101`).
Chamadores:

- `services/api/app/infrastructure/queue/tasks/nvr_extraction.py:134` — mineração NVR (nuvem)
- `services/api/app/infrastructure/queue/tasks/extraction.py:141` — extração de vídeo
- `services/api/app/api/v1/videos/routes.py:606,749` — upload

Nenhum deles consulta módulo da câmera. O filtro de coleta é na **nuvem**, nesse
caminho — não no box/edge.

---

## Apêndice — queries

### A. Confirmação por câmera (§1, §3)

```sql
WITH f AS (
  SELECT tf.id, tf.camera_id, tf.is_annotated
    FROM public.training_frames tf
   WHERE tf.tenant_id = '63c219d8-fbef-4f3c-a7c9-058c742482e2'
     AND tf.module_code = 'epi'
), cx AS (
  SELECT fa.id, fa.source, fa.reviewed_by, fa.created_at, tf.camera_id,
         (fa.class_id < 100000
          OR (yc.id IS NOT NULL AND yc.archived_at IS NULL))          AS classe_viva,
         (tf.is_annotated AND tf.curation_status <> 'excluida'
          AND tf.dataset_role = 'pool')                                AS frame_no_pool,
         (fa.width * fa.height >= 0.95)                                AS rotulo_de_frame
    FROM public.frame_annotations fa
    JOIN public.training_frames tf ON tf.id = fa.frame_id
    LEFT JOIN public.yolo_classes yc
      ON fa.class_id >= 100000 AND yc.id = fa.class_id - 100000
     AND yc.tenant_id = '63c219d8-fbef-4f3c-a7c9-058c742482e2'
   WHERE tf.tenant_id = '63c219d8-fbef-4f3c-a7c9-058c742482e2'
     AND tf.module_code = 'epi'
)
SELECT c.name AS camera,
       count(DISTINCT f.id)                                   AS frames_epi,
       count(DISTINCT f.id) FILTER (WHERE f.is_annotated)     AS anotados,
       COALESCE(b.caixas, 0)                                  AS caixas,
       COALESCE(b.elegiveis, 0)                               AS caixas_elegiveis_hoje,
       COALESCE(b.no_v17b, 0)                                 AS caixas_no_ultimo_treino
  FROM f
  JOIN public.cameras c ON c.id = f.camera_id
  LEFT JOIN (
    SELECT camera_id,
           count(*) AS caixas,
           count(*) FILTER (WHERE frame_no_pool AND classe_viva AND NOT rotulo_de_frame
                              AND (source = 'manual' OR reviewed_by IS NOT NULL)) AS elegiveis,
           count(*) FILTER (WHERE frame_no_pool AND classe_viva AND NOT rotulo_de_frame
                              AND (source = 'manual' OR reviewed_by IS NOT NULL)
                              AND created_at < '2026-09-02 13:59:40')             AS no_v17b
      FROM cx GROUP BY camera_id
  ) b ON b.camera_id = f.camera_id
 GROUP BY c.name, b.caixas, b.elegiveis, b.no_v17b
 ORDER BY frames_epi DESC, camera;
```

### B. Reconstrução caixa → versão → modelo (§4)

```sql
WITH versoes AS (
  SELECT dv.id, dv.version, dv.created_at, count(tm.id) AS modelos,
         string_agg(tm.display_name, ' | ' ORDER BY tm.created_at) AS nomes
    FROM public.dataset_versions dv
    JOIN public.trained_models tm ON tm.dataset_version_id = dv.id
   WHERE dv.tenant_id = '63c219d8-fbef-4f3c-a7c9-058c742482e2'
   GROUP BY dv.id, dv.version, dv.created_at
), caixas AS (
  SELECT fa.id, fa.created_at, c.name AS camera
    FROM public.frame_annotations fa
    JOIN public.training_frames tf ON tf.id = fa.frame_id
    JOIN public.cameras c ON c.id = tf.camera_id
    LEFT JOIN public.yolo_classes yc
      ON fa.class_id >= 100000 AND yc.id = fa.class_id - 100000
     AND yc.tenant_id = '63c219d8-fbef-4f3c-a7c9-058c742482e2'
   WHERE tf.tenant_id = '63c219d8-fbef-4f3c-a7c9-058c742482e2'
     AND tf.module_code = 'epi' AND tf.is_annotated
     AND tf.curation_status <> 'excluida' AND tf.dataset_role = 'pool'
     AND (fa.class_id < 100000 OR (yc.id IS NOT NULL AND yc.archived_at IS NULL))
     AND (fa.source = 'manual' OR fa.reviewed_by IS NOT NULL)
     AND NOT (fa.width * fa.height >= 0.95)
)
SELECT v.version, v.created_at::date AS build, v.modelos,
       count(cx.id) FILTER (WHERE cx.created_at < v.created_at) AS caixas_total,
       count(cx.id) FILTER (WHERE cx.created_at < v.created_at
                              AND cx.camera LIKE 'Qualidade%')  AS caixas_qualidade,
       v.nomes
  FROM versoes v LEFT JOIN caixas cx ON TRUE
 GROUP BY v.version, v.created_at, v.modelos, v.nomes
 ORDER BY v.created_at;
```

### C. Validação do predicado contra um build real (§2)

```sql
WITH pool AS (
  SELECT tf.id FROM public.training_frames tf
   WHERE tf.tenant_id = '63c219d8-fbef-4f3c-a7c9-058c742482e2'
     AND tf.module_code = 'epi' AND tf.is_annotated
     AND tf.curation_status <> 'excluida' AND tf.dataset_role = 'pool'),
elig AS (
  SELECT fa.frame_id FROM public.frame_annotations fa
    JOIN pool p ON p.id = fa.frame_id
    LEFT JOIN public.yolo_classes yc
      ON fa.class_id >= 100000 AND yc.id = fa.class_id - 100000
     AND yc.tenant_id = '63c219d8-fbef-4f3c-a7c9-058c742482e2'
   WHERE (fa.class_id < 100000 OR (yc.id IS NOT NULL AND yc.archived_at IS NULL))
     AND (fa.source = 'manual' OR fa.reviewed_by IS NOT NULL)
     AND NOT (fa.width * fa.height >= 0.95)
  GROUP BY fa.frame_id),
tinham AS (SELECT DISTINCT fa.frame_id FROM public.frame_annotations fa
             JOIN pool p ON p.id = fa.frame_id)
SELECT (SELECT count(*) FROM pool)   AS pool,
       (SELECT count(*) FROM tinham) AS tinham_caixa,
       (SELECT count(*) FROM elig)   AS sobraram_com_caixa,
       (SELECT count(*) FROM pool)
         - ((SELECT count(*) FROM tinham) - (SELECT count(*) FROM elig)) AS frames_no_export;
-- 5409 | 5406 | 4984 | 4987   vs   dataset_versions.frame_count(v17a-presenca) = 4983
```

### D. Estado do schema (§0)

```sql
SELECT count(*) FROM rvb.cameras;                                        -- 0
SELECT count(*) FROM public.cameras
 WHERE tenant_id = '63c219d8-fbef-4f3c-a7c9-058c742482e2';               -- 29

SELECT count(*) AS total,
       count(*) FILTER (WHERE camera_id IS NULL)                          AS sem_camera,
       count(*) FILTER (WHERE camera_id IN (SELECT id FROM public.cameras)) AS casa_public,
       count(*) FILTER (WHERE camera_id IN (SELECT id FROM rvb.cameras))    AS casa_rvb
  FROM public.training_frames
 WHERE tenant_id = '63c219d8-fbef-4f3c-a7c9-058c742482e2'
   AND module_code = 'epi';
-- 12854 | 0 | 12854 | 0

SELECT module_code, active_module, count(*) FROM public.cameras
 WHERE tenant_id = '63c219d8-fbef-4f3c-a7c9-058c742482e2'
 GROUP BY 1, 2;
-- epi | epi | 29
```
