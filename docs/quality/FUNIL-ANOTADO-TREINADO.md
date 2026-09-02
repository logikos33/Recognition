# Funil anotado → exportado → treinado, por classe (RVB)

**Data da medição:** 2026-09-02
**Tenant:** RVB Isolantes (`63c219d8-fbef-4f3c-a7c9-058c742482e2`, schema `rvb`), módulo `epi`
**Escopo:** SOMENTE medição, contra o banco DEV (read-only) e o R2 real. Nenhum código foi alterado.

---

## 0. A pergunta

O Vitor viu **3.087 "Protetor auditivo" na tela** (aba Classes do Estúdio) e o COCO de treino
tinha **1.363** no split `train`. Este documento reconcilia, por classe, cada etapa entre os dois
números e nomeia cada perda.

**Resumo em uma linha:** as duas primeiras etapas (banco → elegível) batem quase 1:1 e têm
mecanismo nomeado para cada caixa perdida. O salto grande (elegível de hoje ≈2.800–3.100 →
exportado 1.909) **não é filtro** — é o export ser uma FOTO congelada de 21/08 e o banco ter
seguido crescendo depois, sem tabela de auditoria para provar linha a linha quanto. Isso é
declarado como não medido, não inventado como se fosse um filtro.

---

## 1. O que a tela conta (achado)

**Medição:** a aba **Classes** do Estúdio (`apps/frontend/src/app/estudio/Classes.tsx:512,543`,
rótulo "caixas") é alimentada por `GET /modules/<code>/classes` →
`ModuleService.get_classes` (`services/api/app/domain/services/module_service.py:160-216`) → para
classes do tenant, `usage_count` vem de
`AnnotationRepository.get_usage_counts_by_tenant`
(`services/api/app/infrastructure/database/repositories/annotation_repository.py:161-180`):

```sql
SELECT fa.class_id, COUNT(*) FROM frame_annotations fa
JOIN training_frames tf ON tf.id = fa.frame_id
WHERE tf.tenant_id = %s
GROUP BY fa.class_id
```

Reproduzida linha por linha no banco DEV para `class_id=100004` (namespace
`class_namespace.TENANT_CLASS_ID_OFFSET(100000) + yolo_classes.id(4)` = "Protetor auditivo",
classe custom do tenant, **não** está no catálogo global `module_classes`): **n=3.087**, batendo
exato com o número que o Vitor viu.

**A tela conta CAIXA (não frame, não imagem)**, escopada só por `tenant_id` — **sem** filtro de
`is_annotated`, `curation_status`, classe arquivada ou proveniência (source manual vs IA não
revisada). É literalmente `COUNT(*)` bruto da tabela `frame_annotations` para aquele tenant+classe.
Não há vazamento de outro módulo: medido (`perda_module`, seção 2) — **n=0** caixas de
"Protetor auditivo" fora de `module_code='epi'`.

Existe uma SEGUNDA rota de contagem (`AnnotationRepository.get_classes_with_counts`, linha
182-209, usada por `TenantClassService` fora do anotador) que faz `JOIN a.class_id = c.id` **sem**
decodificar o offset de namespace — para uma classe custom essa contagem dá um número errado
(compara `class_id` namespaced com `c.id` cru). Não é a tela que o Vitor olhou (não bate com
3.087), mas é uma dívida separada: duas rotas de "quantas caixas tem essa classe" que **não**
concordam entre si. Registrado aqui, não corrigido (fora do contrato desta medição).

---

## 2. Etapa 1 → 2: Anotado (banco) → Elegível ao export

**Builder vivo:** `services/api/app/infrastructure/queue/tasks/versioning_v2.py`. Filtros
aplicados por `_snapshot_labeled_frames` (linhas 105-121) + `_fetch_annotations`
(linhas 170-190) + `_sem_rotulos_de_frame` (linhas 216-277), na ordem em que descartam caixa:

| # | Filtro | Linha | Mecanismo | Perda medida (Protetor auditivo) | Perda medida (todas as 11 classes ativas) |
|---|---|---|---|---|---|
| 1 | `tf.module_code = 'epi'` | `versioning_v2.py:114,182` | só frames do módulo EPI entram | **0** | **0** |
| 2 | `tf.is_annotated = TRUE` | `versioning_v2.py:115,183` | frame ainda não marcado como anotado | **0** | **0** |
| 3 | `tf.curation_status != 'excluida'` | `versioning_v2.py:116,184` | frame descartado na curadoria humana | **11** | **50** |
| 4 | classe custom arquivada (`yolo_classes.archived_at`) | `versioning_v2.py:157-159,185-186` | classe "aposentada" (ex.: duplicata) some do treino sem apagar a caixa | **0** (Protetor auditivo não está arquivada) | **2** (1 de "incluir blur", 1 de "Sem botas" — ambas arquivadas, confirmado em `yolo_classes`) |
| 5 | gate de procedência: `source='manual' OR reviewed_by IS NOT NULL` | `versioning_v2.py:206-209` (D-39, migration 095) | pré-anotação de IA **não revisada** por humano nunca vira treino | **0** — toda caixa de Protetor auditivo hoje é manual ou já revisada | **0** em todas as 11 classes |
| 6 | `_e_rotulo_de_frame` (bbox cobre ≥95% do frame) | `versioning_v2.py:213,254-277` | veredito da aba Classificar grava `[0,0,1,1]` (classificação, não localização) — não é alvo de detecção | **247** | **1.098** |
| 7 | dimensão do frame irresolvível (R2+PIL) | `versioning_v2.py:553-584` | frame sem `width`/`height` nem no banco nem no R2 | **0** (medido: 0 de 5.405 frames do pool sem dimensão) | **0** |

**Anotado (banco) "Protetor auditivo" = 3.087**
**Elegível hoje, pipeline completo do builder atual = 2.829** (perda total 258 = 11 curadoria + 247
rótulo-de-frame)

Somando as 14 classes que aparecem no banco (10 ativas + Capacete + as 3 órfãs residuais —
`Sem botas`/`Sem Capacete`/`incluir blur`, ver tabela 6), os totais batem exatamente com as
consultas agregadas (`WHERE tf.tenant_id=... AND tf.module_code='epi' AND ...`, sem `GROUP BY`):
Anotado banco = **7.489** → elegível (pós gate de procedência, pré rótulo-de-frame) = **7.437**
(perda 52 = 50 curadoria + 2 classe arquivada) → elegível localização (pós rótulo-de-frame) =
**6.339** (perda 1.098). Os três totais batem caixa a caixa com a soma por classe da tabela 6 —
nenhuma perda ficou sem classe.

---

## 3. Etapa 3: Exportado — COCO real do dataset servido

Artefato: `dataset-exports/63c219d8-.../96a88fef-.../v10b-freeze` (build 2026-08-21 12:04,
`dataset_versions.id=42023066-fa2e-4ccd-b1a9-06652773dbcf`). **Reconferido** baixando os 3
`_annotations.coco.json` reais do R2 (não só o `class_distribution` do banco) e contando
`category_id` por anotação:

| Classe | train | val | test | **total exportado** | class_distribution (banco) |
|---|--:|--:|--:|--:|--:|
| Protetor auditivo | 1.363 | 496 | 50 | **1.909** | 1.909 ✅ |
| mascara | 532 | 255 | 36 | 823 | 823 ✅ |
| Óculos | 354 | 34 | 45 | 433 | 433 ✅ |
| Botas | 353 | 43 | 49 | 445 | 445 ✅ |
| Sem Luvas | 206 | 19 | 28 | 253 | 253 ✅ |
| Sem protetor de ouvido | 198 | 47 | 2 | 247 | 247 ✅ |
| Uso incorreto de mascara | 162 | 32 | 0 | 194 | 194 ✅ |
| Sem mascara | 153 | 42 | 25 | 220 | 220 ✅ |
| Luvas | 104 | 10 | 70 | 184 | 184 ✅ |
| Sem Óculos | 96 | 16 | 2 | 114 | 114 ✅ |
| Capacete | 2 | 0 | 0 | 2 | 2 ✅ |
| Sem botas | 1 | 0 | 0 | 1 | (arquivada — não aparece) |
| **imagens** | 2.486 | 826 | 179 | 3.491 | frame_count=3.491 ✅ |
| **caixas** | **3.524** | **994** | **307** | **4.825** | — |

O COCO real bate **exatamente** com o `class_distribution` jsonb gravado em
`dataset_versions` (as duas fontes concordam — não houve necessidade de reconciliar divergência
entre banco e R2). 13 categorias no `train` (12 nomeadas + 1 âncora `recognition` id:0,
`versioning_v2.py:843` — obrigatória pro RF-DETR, sem ela os índices de classe deslocam de 1,
`versioning_v2.py:831-842`).

### Achado: o dataset servido pode não ser este

`trained_models` com `is_active=TRUE` para o tenant RVB hoje aponta para
`dataset_version_id=c36f6096-...` (**v16-volume**, criado 2026-08-25 07:54, um dos braços do A/B
de volume do #536), **não** v10b-freeze — cujos dois `trained_models` (Job 3091cfc9, Job ce4e1969)
estão `is_active=FALSE`. Se "modelo servido" para dimensionar o V2 precisa ser o que está
`is_active=TRUE` hoje, é v16-volume, não v10b-freeze — a tabela acima usa v10b-freeze porque foi
o dataset nomeado no contrato e os números batem com os já medidos (1.363/496/50), mas a
identidade do "modelo em produção" **não medi de novo aqui** (fora do escopo desta rodada) e
diverge do que consta em `trained_models.is_active`. **DECLARO, não conserto.**

---

## 4. Etapa 2 → 3: a perda que não tem filtro (achado principal)

| Classe | Elegível hoje (pré rótulo) | Exportado (soma splits) | Perda | % |
|---|--:|--:|--:|--:|
| Protetor auditivo | 3.076 | 1.909 | 1.167 | 38% |
| Sem protetor de ouvido | 532 | 247 | 285 | 54% |
| Botas | 819 | 445 | 374 | 46% |
| Sem Óculos | 209 | 114 | 95 | 45% |
| Luvas | 303 | 184 | 119 | 39% |
| Óculos | 631 | 433 | 198 | 31% |
| Sem Luvas | 361 | 253 | 108 | 30% |
| Sem mascara | 292 | 220 | 72 | 25% |
| Uso incorreto de mascara | 250 | 194 | 56 | 22% |
| mascara | 962 | 823 | 139 | 14% |
| Capacete | 2 | 2 | 0 | 0% |
| **total (11 classes)** | **7.437** | **4.825** | **2.612** | **35%** |

**Todas as 11 classes perdem no MESMO sentido** (elegível hoje > exportado) **e em faixa
parecida (14%–54%)** — não é um filtro que bate desproporcionalmente numa classe só (o padrão de
um filtro real, como o rótulo-de-frame acima, varia muito mais entre classes: 8%–68% do elegível
bruto). Isso é a assinatura de **crescimento do acervo depois do freeze**, não de um filtro:

- `_e_rotulo_de_frame` (o único filtro novo no período) **não existia** quando v10b-freeze foi
  construído — `git log` mostra o commit que o introduziu (`28b97525`, "a caixa [0,0,1,1] da aba
  Classificar não é alvo de localização") datado **2026-08-24 23:00**, três dias **depois** do
  build de v10b-freeze (2026-08-21 12:04). Aplicar esse filtro a dados de hoje e comparar com um
  export que nunca o teve teria o sinal ERRADO (reduziria o elegível, não explicaria um elegível
  MAIOR que o exportado) — por isso a tabela acima usa "elegível pré rótulo" (7.437), a base que
  o código de 21/08 realmente via.
- `limite_frames`/`_limita_frames` (corte determinístico de frames) também **não existia** em
  21/08 — mesmo `git log`, introduzido em `0e14c14d`/`b9d27443` (2026-08-24/25). Não pode ter sido
  usado para cortar v10b-freeze.
- O pool de frames elegíveis (`is_annotated=TRUE`, `curation_status!='excluida'`, módulo `epi`)
  **hoje** tem **5.405** frames; v10b-freeze exportou **3.491**. A diferença (1.914 frames, 35%)
  é consistente em magnitude com a perda de caixas por classe acima (14%-54%) — mais anotação
  humana aconteceu nos ~12 dias entre o freeze (21/08) e esta medição (02/09).

**Não medido / não reconciliável linha a linha:** `frame_annotations` não tem tabela de
auditoria/histórico — uma caixa criada antes do freeze mas **reclassificada depois** (mudança de
`class_id`) fica indistinguível, pelo `created_at`, de uma caixa nova. Tentei uma reconstrução por
`created_at <= '2026-08-21 12:04:47'` e o resultado **contradisse** os próprios dados (elegível
"até o freeze" = 1.771, menor que o exportado real = 1.909 — impossível se fosse um subconjunto
válido), confirmando que reclassificação pós-freeze existe e que essa reconstrução não é
confiável. **A direção do achado (banco cresceu, export é anterior) está provada; o tamanho exato
atribuível só a "caixa nova" vs. "caixa reclassificada" não está — declarado como não medido, não
como zero.**

---

## 5. Etapa 4: Treinado — soma dos 3 splits, ou só train?

**Resposta:** só **`train`**. O modelo (RF-DETR/YOLOX) atualiza peso por gradiente somente com o
split `train`; `val` e `test` são *held-out* — usados só pra medir métrica
(`_diagnosticar_split`, `versioning_v2.py:499-550`, fala explicitamente em "avaliação" pra
test/val, nunca em treino). "Treinado" de **Protetor auditivo = 1.363**, não 1.909 — a soma dos
3 splits é o **exportado**, não o que o modelo viu atualizar peso.

---

## 6. Tabela consolidada (n visível em cada célula)

| Classe | Anotado (banco/tela) | Elegível pré-rótulo hoje | Elegível pós-rótulo hoje | Exportado total (train+val+test) | **Treinado (só train)** |
|---|--:|--:|--:|--:|--:|
| Protetor auditivo | 3.087 | 3.076 | 2.829 | 1.909 | **1.363** |
| mascara | 972 | 962 | 888 | 823 | **532** |
| Botas | 829 | 819 | 704 | 445 | **353** |
| Óculos | 635 | 631 | 511 | 433 | **354** |
| Sem protetor de ouvido | 536 | 532 | 505 | 247 | **198** |
| Sem Luvas | 363 | 361 | 178 | 253 | **206** |
| Luvas | 304 | 303 | 255 | 184 | **104** |
| Sem mascara | 294 | 292 | 134 | 220 | **153** |
| Uso incorreto de mascara | 253 | 250 | 219 | 194 | **162** |
| Sem Óculos | 210 | 209 | 114 | 114 | **96** |
| Capacete (catálogo, fora da taxonomia RVB de 6 classes) | 3 | 2 | 2 | 2 | **2** |
| Sem botas (classe arquivada) | 1 | 0 | 0 | 1 (legado) | **1** |
| Sem Capacete (catálogo, orfão) | 1 | 0 | 0 | 0 | 0 |
| incluir blur (classe arquivada) | 1 | 0 | 0 | 0 | 0 |
| **TOTAL (14 classes — 10 ativas + Capacete + 3 órfãs residuais)** | **7.489** | **7.437** | **6.339** | **4.825** | **3.524** |

`Sem Luvas`/`Sem mascara` têm proporção de rótulo-de-frame muito maior que as outras (183/361 =
51% e 158/292 = 54%, contra 8%-27% nas demais) — o veredito da aba Classificar concentra nessas
duas classes mais que nas outras; vale investigar por quê antes de dimensionar o V2 nelas
especificamente (não investigado aqui — fora do contrato).

---

## 7. Para o dimensionamento do V2

1. **Banco → elegível bate 100%, com mecanismo por caixa.** Não há "vazamento" nessa parte do
   funil — cada caixa perdida tem um filtro nomeado e uma linha de código.
2. **Elegível → exportado NÃO é comparável diretamente** entre uma foto congelada (v10b-freeze,
   21/08) e o estado do banco hoje (02/09) — são datas diferentes por construção
   (`dataset_version` é imutável, `versioning_v2.py:705-715`). Para dimensionar o V2, use o
   **elegível de HOJE** (coluna "Elegível pós-rótulo hoje" — é o que um export novo, com o código
   atual, devolveria), não o export antigo.
3. **"Treinado" é o `train`, não a soma dos 3 splits** — 1.363 para Protetor auditivo, não 1.909
   e muito menos 3.087.
4. **O modelo realmente `is_active=TRUE` hoje é outro `dataset_version` (v16-volume), não
   v10b-freeze** — confirme com o Vitor qual dataset é de fato "o servido" antes de usar esta
   tabela como baseline de capacidade do V2.
