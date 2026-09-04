# A/B das três variantes com o GABARITO REAL — o VEREDITO

> ## NENHUMA das três variantes serve.
>
> E o que o cliente já tem hoje (`46a30ed9`) **bate as três** nas duas únicas
> classes com gabarito. O problema medido não é a taxonomia — é o **limiar**:
> em produção (0,5) o modelo servido não acusa **uma única vez** em 246 quadros
> que contêm 116 violações reais.
>
> ⛔ Nenhum deployment foi trocado, ativado ou desativado. A decisão é do dono.

Fecha o A/B que [`AB-HOLDOUT-V2.md`](./AB-HOLDOUT-V2.md) deixou em aberto por
falta de gabarito. Em **2026-09-03, das 22:46 às 22:59**, o dono julgou 246
quadros na fila de triagem e a medição destravou.

- **Tenant:** `63c219d8-fbef-4f3c-a7c9-058c742482e2` (RVB) · **módulo** `epi`
- **Relatórios brutos** (tabelas completas, varreduras de confiança e de IoMin):
  - `evidence/ab-veredito/relatorio-limiar-030.md` — limiar 0,30
  - `evidence/ab-veredito/relatorio-limiar-005.md` — limiar 0,05
- **Ferramenta:** `scripts/ops/ab_ausencia.py` (55 testes), ligada nesta rodada à
  tabela `public.holdout_verdicts`.

---

## 1. O gabarito — de onde veio, e conferido

Fonte: **`public.holdout_verdicts`** (migration 135) — resposta por
imagem×classe, sem geometria, numa tabela que nenhuma query de export de treino
conhece. **644 julgamentos**, 246 quadros distintos, **1 avaliador**, 13 minutos.

```sql
SELECT COALESCE(mc.display_name, mc.class_name, yc.name) AS classe,
       hv.class_id,
       CASE WHEN hv.class_id < 100000 THEN 'catalogo(module_classes)'
                                      ELSE 'tenant(yolo_classes)' END AS namespace,
       count(*) FILTER (WHERE hv.verdict='sim')     AS sim,
       count(*) FILTER (WHERE hv.verdict='nao')     AS nao,
       count(*) FILTER (WHERE hv.verdict='nao_sei') AS nao_sei,
       count(*)                                     AS total
  FROM public.holdout_verdicts hv
  LEFT JOIN public.module_classes mc
         ON hv.class_id < 100000 AND mc.class_id = hv.class_id AND mc.module_code='epi'
  LEFT JOIN public.yolo_classes yc
         ON hv.class_id >= 100000 AND yc.id = hv.class_id - 100000
 WHERE hv.tenant_id='63c219d8-fbef-4f3c-a7c9-058c742482e2'
 GROUP BY 1,2,3 ORDER BY 7 DESC;
```

| classe | class_id | namespace | sim | nao | nao_sei | total |
|---|---:|---|---:|---:|---:|---:|
| Sem Luvas | 5 | catálogo (`module_classes`) | **69** | 53 | 124 | 246 |
| Sem mascara | 100009 | tenant (`yolo_classes`) | **47** | 66 | 132 | 245 |
| Sem Óculos | 7 | catálogo (`module_classes`) | 0 | 49 | 2 | 51 |
| Sem protetor de ouvido | 100007 | tenant (`yolo_classes`) | 0 | 49 | 2 | 51 |
| Uso incorreto de mascara | 100011 | tenant (`yolo_classes`) | 0 | 49 | 2 | 51 |

Bate exatamente com a contagem do dono. **246+245+51+51+51 = 644.** Sem resíduo.

### Os dois namespaces de `class_id` — tratados

`holdout_verdicts.class_id` vive em dois espaços de inteiros: `< 100000` é
`module_classes.class_id` (catálogo global); `>= 100000` é `yolo_classes.id` do
tenant somado a `TENANT_CLASS_ID_OFFSET` (`app/domain/services/class_namespace.py`).

Ler o namespace errado **não daria erro** — daria gabarito trocado com cara de medida:

| class_id | lido como catálogo (**correto**) | lido como tenant (errado) |
|---:|---|---|
| 5 | **Sem Luvas** (69 `sim`) | `Protetor auricular` — classe de **presença**, arquivada em 2026-08-10 |
| 7 | **Sem Óculos** (0 `sim`) | `Sem protetor de ouvido` — duplicaria uma classe e sumiria com outra |

O de-para é resolvido **na query**, pelo mesmo critério de
`ModuleService.get_classes` (`display_name` do catálogo, `name` do tenant).

### `nao_sei` NÃO virou `nao` — e o custo declarado

`nao_sei` sai do **numerador e do denominador** da classe. Convertê-lo em `nao`
contaria como falso positivo toda acusação que talvez estivesse certa — seria
inventar gabarito.

| classe | sim | nao | nao_sei | nunca julgada | **fora do denominador** | **avaliadas** |
|---|---:|---:|---:|---:|---:|---:|
| Sem Luvas | 69 | 53 | 124 | 0 | **124** | **122** |
| Sem mascara | 47 | 66 | 132 | 1 | **133** | **113** |
| Sem Óculos | 0 | 49 | 2 | 195 | **197** | **49** |
| Sem protetor de ouvido | 0 | 49 | 2 | 195 | **197** | **49** |
| Uso incorreto de mascara | 0 | 49 | 2 | 195 | **197** | **49** |

**262 julgamentos `nao_sei` ficaram fora do denominador** (141 quadros distintos).
Mais 976 pares imagem×classe que ninguém julgou.

### O negativo do gabarito é quase todo corredor vazio

| classe | sim | `nao` por **`sem_pessoa`** | `nao` **com pessoa** |
|---|---:|---:|---:|
| Sem Luvas | 69 | 49 | **4** |
| Sem mascara | 47 | 49 | **17** |
| Sem Óculos | 0 | 49 | 0 |
| Sem protetor de ouvido | 0 | 49 | 0 |
| Uso incorreto de mascara | 0 | 49 | 0 |

**245 dos 266 `nao` vieram do atalho "não há pessoa"** — 49 corredores vazios, um
toque, `nao` para as cinco classes. Isso mede alucinação em quadro vazio (real e
útil), mas **não** mede o falso positivo difícil: acusar quem **está** usando o
EPI. Para esse, o gabarito tem 4 quadros em *Sem Luvas* e 17 em *Sem mascara*.

---

## 2. Como a prova foi montada

- **Holdout:** os 246 quadros com veredito, todos com
  `training_frames.dataset_role='holdout'` (migration 133), baixados do R2 pelo
  `r2_key` — a imagem exata que foi julgada.
- **Guarda de vazamento holdout×treino:** **0 colisão de nome, 0 de conteúdo**,
  246/246 conferidas por sha256, contra os 12 COCOs (`train`/`val`/`test`) de
  `v17a-presenca`, `v17b-ausencia`, `v17c-partes` **e** `v10b-freeze`. Inclusive
  o `v10b-freeze`, de 2026-08-21, que **antecede** a trava de holdout: mesmo ele
  não contém nenhum dos 246. **Baseline e servido estão limpos.**
- **Limiar ÚNICO** para todas as variantes em cada rodada (0,30 e 0,05).
- **Estágio 1 (variante A):** `yolox_nano_SERVIDO.onnx`, cópia bit-a-bit do
  Jetson (`c789161ed43c8269…`), entrada **416×416**, margem de recorte 25%×8% —
  a mesma de `person_detector.py::crop_person`.
- **Dicionário de cada modelo** lido do COCO do seu próprio dataset de treino, na
  ordem de `category_id` (o índice que o ONNX emite), conferido contra a última
  dimensão do tensor `labels` do grafo: `[1,300,6]` para A, `[1,300,12]` para B,
  `[1,300,13]` para C/baseline/servido.

| papel | modelo | dataset_version | dicionário |
|---|---|---|---|
| A · presença derivada | `6ca25ee9` | `v17a-presenca` | 5 classes de presença |
| B · classe de ausência | `1deadfb0` | `v17b-ausencia` | 11 classes |
| C · parte-do-corpo | `b9243540` | `v17c-partes` | 12 classes |
| baseline v10-ft | `b3ae42b6` | `v10b-freeze` | 12 classes |
| **SERVIDO hoje** | `46a30ed9` | `v10b-freeze` | 12 classes |

`46a30ed9` está **`active` em 14 câmeras** do RVB (`public.model_deployments`),
todas em `mode: shadow` com alertas desligados.

---

## 3. A TABELA DO VEREDITO

### 3.1 Limiar 0,30 (o default da ferramenta, do #536/ADR-0067)

**Sem Luvas** — n real = **69**, avaliadas = 122 · *controle nulo ("acusar sempre") = **56,6%***

| variante | TP | FP | FN | precisão | recall | abstenção | n acusações |
|---|---:|---:|---:|---:|---:|---:|---:|
| A · presença derivada | 68 | 39 | 1 | 63,6% | 98,6% | 15 (12,3%) | 107 |
| B · classe de ausência | 0 | 0 | 69 | — | 0,0% | 0 | **0** |
| C · parte-do-corpo | 0 | 4 | 69 | 0,0% | 0,0% | 118 (96,7%) | 4 |
| baseline `b3ae42b6` | 0 | 0 | 69 | — | 0,0% | 0 | **0** |
| **SERVIDO `46a30ed9`** | 0 | 0 | 69 | — | 0,0% | 0 | **0** |

**Sem mascara** — n real = **47**, avaliadas = 113 · *controle nulo = **41,6%***

| variante | TP | FP | FN | precisão | recall | abstenção | n acusações |
|---|---:|---:|---:|---:|---:|---:|---:|
| A · presença derivada | 46 | 52 | 1 | 46,9% | 97,9% | 15 (13,3%) | 98 |
| B · classe de ausência | 3 | 0 | 44 | 100,0% | 6,4% | 0 | 3 |
| C · parte-do-corpo | 4 | 11 | 43 | 26,7% | 8,5% | 98 (86,7%) | 15 |
| baseline `b3ae42b6` | 7 | 0 | 40 | 100,0% | 14,9% | 0 | 7 |
| **SERVIDO `46a30ed9`** | 0 | 0 | 47 | — | 0,0% | 0 | **0** |

**A 0,30 quase todo mundo é mudo.** A varredura (§5) mostra por quê: a confiança
destes RF-DETR neste holdout é baixa, e o sinal inteiro vive **abaixo de 0,15**.
Por isso a mesma medição foi refeita no piso de coleta.

### 3.2 Limiar 0,05 — onde os modelos de fato falam

**Sem Luvas** — n real = **69**, avaliadas = 122 · *controle nulo = **56,6%***

| variante | TP | FP | FN | precisão | recall | abstenção | n acusações |
|---|---:|---:|---:|---:|---:|---:|---:|
| A · presença derivada | 68 | 39 | 1 | 63,6% | 98,6% | 15 (12,3%) | 107 |
| B · classe de ausência | 14 | 5 | 55 | **73,7%** | 20,3% | 0 | 19 |
| C · parte-do-corpo | 40 | 21 | 29 | 65,6% | 58,0% | 61 (50,0%) | 61 |
| baseline `b3ae42b6` | 23 | 4 | 46 | **85,2%** | 33,3% | 0 | 27 |
| **SERVIDO `46a30ed9`** | **45** | 22 | 24 | **67,2%** | **65,2%** | 0 | **67** |

**Sem mascara** — n real = **47**, avaliadas = 113 · *controle nulo = **41,6%***

| variante | TP | FP | FN | precisão | recall | abstenção | n acusações |
|---|---:|---:|---:|---:|---:|---:|---:|
| A · presença derivada | 46 | 52 | 1 | 46,9% | 97,9% | 15 (13,3%) | 98 |
| B · classe de ausência | 22 | 6 | 25 | 78,6% | 46,8% | 0 | 28 |
| C · parte-do-corpo | 37 | 34 | 10 | 52,1% | 78,7% | 40 (35,4%) | 71 |
| baseline `b3ae42b6` | 34 | 15 | 13 | 69,4% | 72,3% | 0 | 49 |
| **SERVIDO `46a30ed9`** | **35** | **10** | 12 | **77,8%** | **74,5%** | 0 | **45** |

---

## 4. A régua da ADR-0067 — quem passa, e por que "passar" não basta

**A régua:** precisão ≥ **50%** e n ≥ **30** acusações (precisão sem n não é
medida — "Sem Óculos, 66,7% sobre 3" foi o caso que criou a regra).

| | @0,30 | @0,05 |
|---|---|---|
| **Sem Luvas** | só **A** (63,6%, n=107) | **A** (63,6%, n=107), **C** (65,6%, n=61), **SERVIDO** (67,2%, n=67) |
| **Sem mascara** | ninguém | **C** (52,1%, n=71), **baseline** (69,4%, n=49), **SERVIDO** (77,8%, n=45) |

**B nunca passa** — n máximo 19 e 28, sempre a um passo dos 30. O baseline passa
só em *Sem mascara* (n=49); em *Sem Luvas* fica em n=27.

### O controle nulo, e por que ele derruba a "vitória" da A

A ferramenta, aplicando a régua crua, imprime `A vence` a 0,30 e
`EMPATE entre A, C → vence a mais simples: A` a 0,05. **Esse veredito mecânico
está errado, e a aritmética prova.**

A variante A **acusou 100% do que julgou**, em todas as classes:

| classe | acusações de A | abstenções de A | soma | avaliadas |
|---|---:|---:|---:|---:|
| Sem Luvas | 107 | 15 | **122** | **122** |
| Sem mascara | 98 | 15 | **113** | **113** |
| Sem Óculos | 35 | 14 | **49** | **49** |
| Sem protetor de ouvido | 35 | 14 | **49** | **49** |

Em toda imagem em que o estágio 1 achou pessoa, a A acusou — sempre, todas as
classes. Logo a precisão dela **é**, por identidade aritmética e não por
semelhança, a prevalência da violação entre os quadros que julgou (68/107 =
63,6%). **A variante não distinguiu nada; o número é do gabarito.**

A régua de 50% da ADR-0067 **não protege sozinha**: num conjunto onde 57% dos
quadros têm a violação, "acuse sempre" passa sem olhar para a imagem. Por isso o
controle nulo virou linha obrigatória do relatório (`_controle_nulo`).

**C a 0,05 cai no mesmo diagnóstico em *Sem Luvas***: 61 acusações + 61
abstenções = 122 avaliadas. Ela também acusou tudo que julgou; a diferença é só o
que consegue ver. Em *Sem mascara* recusou 2 de 73 julgadas — praticamente nulo
também.

### A causa medida: o modelo da variante A é CEGO no recorte de pessoa

Medido em 40 imagens do holdout, **389 recortes de pessoa** produzidos pelo mesmo
`recortar()` do edge:

| onde o modelo `6ca25ee9` roda | detecções ≥ 0,05 | confiança máxima |
|---|---:|---|
| **no recorte de pessoa** (é como a variante A funciona) | **8** em 389 recortes | **0,062** |
| no frame cheio (mesmo modelo, mesmas 40 imagens) | 360 | Protetor auditivo **0,675** · Óculos **0,515** · Botas 0,305 · mascara 0,287 · Luvas 0,105 |

O modelo enxerga no frame cheio e **não enxerga nada** no recorte. A derivação da
A é "o objeto esperado não apareceu no recorte ⇒ acuse" — e o objeto **nunca**
aparece. É por isso que os números da A são **idênticos em 0,05, 0,07, 0,10,
0,15, 0,20, 0,30, 0,50 e 0,70**: não há detecção alguma para o limiar filtrar.

Causa provável é domínio (treino em frame cheio 1920×1080 → 560×560; recorte de
pessoa é outra escala e outra proporção). Não está provado **por que** — está
provado **que**, e isso basta para o veredito.

É a segunda demonstração numérica do que a **ADR-0067 já proíbe**: violação
derivada do silêncio do detector de presença. Na primeira rodada a A acusou 97%
dos quadros; nesta, **100% do que julgou**.

---

## 5. Varredura de limiar

Regra de justiça: limiar **único** para todas. A varredura existe porque o limiar
de produção não tem origem documentada — e a curva é o insumo para escolhê-lo.

**Sem Luvas** — precisão / recall (n de acusações) · *controle nulo 56,6%*

| limiar | A | B | C | baseline | SERVIDO |
|---:|---|---|---|---|---|
| 0,05 | 63,6% / 98,6% (107) | 73,7% / 20,3% (19) | 65,6% / 58,0% (61) | 85,2% / 33,3% (27) | **67,2% / 65,2% (67)** |
| 0,07 | 63,6% / 98,6% (107) | 66,7% / 11,6% (12) | 67,7% / 30,4% (31) | 93,8% / 21,7% (16) | **72,9% / 50,7% (48)** |
| 0,10 | 63,6% / 98,6% (107) | 50,0% / 2,9% (4) | 30,8% / 5,8% (13) | 91,7% / 15,9% (12) | **87,5% / 30,4% (24)** |
| 0,15 | 63,6% / 98,6% (107) | — / 0% (0) | 12,5% / 1,4% (8) | 100% / 7,2% (5) | 100% / 8,7% (6) |
| 0,20 | 63,6% / 98,6% (107) | — / 0% (0) | 0% / 0% (7) | 100% / 5,8% (4) | 100% / 1,4% (1) |
| **0,30** | 63,6% / 98,6% (107) | — / 0% (0) | 0% / 0% (4) | — / **0%** (0) | — / **0%** (0) |
| **0,50** ← produção | 63,6% / 98,6% (107) | — / 0% (0) | 0% / 0% (2) | — / **0%** (0) | — / **0%** (0) |
| **0,70** | 63,6% / 98,6% (107) | — / 0% (0) | 0% / 0% (1) | — / **0%** (0) | — / **0%** (0) |

**Sem mascara** — precisão / recall (n de acusações) · *controle nulo 41,6%*

| limiar | A | B | C | baseline | SERVIDO |
|---:|---|---|---|---|---|
| 0,05 | 46,9% / 97,9% (98) | 78,6% / 46,8% (28) | 52,1% / 78,7% (71) | 69,4% / 72,3% (49) | **77,8% / 74,5% (45)** |
| 0,07 | 46,9% / 97,9% (98) | 81,8% / 38,3% (22) | 50,9% / 59,6% (55) | 81,1% / 63,8% (37) | **89,7% / 55,3% (29)** |
| 0,10 | 46,9% / 97,9% (98) | 87,5% / 29,8% (16) | 51,3% / 42,6% (39) | 92,3% / 51,1% (26) | **90,5% / 40,4% (21)** |
| 0,15 | 46,9% / 97,9% (98) | 91,7% / 23,4% (12) | 40,7% / 23,4% (27) | 100% / 40,4% (19) | 100% / 19,1% (9) |
| 0,20 | 46,9% / 97,9% (98) | 100% / 14,9% (7) | 36,4% / 17,0% (22) | 100% / 29,8% (14) | 100% / 6,4% (3) |
| **0,30** | 46,9% / 97,9% (98) | 100% / 6,4% (3) | 26,7% / 8,5% (15) | 100% / 14,9% (7) | — / **0%** (0) |
| **0,50** ← produção | 46,9% / 97,9% (98) | — / 0% (0) | 25,0% / 4,3% (8) | — / **0%** (0) | — / **0%** (0) |
| **0,70** | 46,9% / 97,9% (98) | — / 0% (0) | — / 0% (0) | — / **0%** (0) | — / **0%** (0) |

**O que a curva diz.** Uma régua de limiar **não é neutra** entre "acusar por
classe" e "acusar por silêncio": subir o limiar faz a A acusar **mais** (menos
presença detectada ⇒ mais "faltando") e faz todas as outras acusarem **menos**.
Isso está declarado, e é o motivo de a comparação ter sido feita nos dois pontos.

**O limiar de produção é 0,5** (`DETECTION_CONFIDENCE_THRESHOLD`, default em
`services/inference/inference/config.py:17`, documentado em `AGENT.md`/`SDD.md`).
Nele, o modelo servido acusa **zero vez** neste holdout.

### O preço de baixar o limiar — alucinação nos 49 quadros vazios

Nas três classes sem gabarito positivo, as 49 imagens foram todas julgadas `nao`
(corredor vazio). **Qualquer acusação ali é falsa.** Contagem de acusações falsas:

| limiar | classe | A | B | C | baseline | **SERVIDO** |
|---:|---|---:|---:|---:|---:|---:|
| 0,05 | Sem Óculos | 35 | 6 | 3 | 3 | **6** |
| 0,05 | Sem protetor de ouvido | 35 | 23 | 46 | 8 | **8** |
| 0,05 | Uso incorreto de mascara | 0 | 33 | 0 | 30 | **29** |
| 0,10 | Sem Óculos | 35 | 0 | 1 | 1 | **0** |
| 0,10 | Sem protetor de ouvido | 35 | 12 | 49 | 5 | **1** |
| 0,10 | Uso incorreto de mascara | 0 | 16 | 0 | 23 | **22** |
| 0,15 | Sem protetor de ouvido | 35 | 7 | 41 | 2 | **0** |
| 0,15 | Uso incorreto de mascara | 0 | 7 | 0 | 14 | **12** |
| 0,30 | Sem protetor de ouvido | 35 | 1 | 22 | 0 | **0** |
| 0,30 | Uso incorreto de mascara | 0 | 0 | 0 | 0 | **0** |

O grosso da alucinação do servido está em **`Uso incorreto de mascara`** (29 em
49 quadros vazios a 0,05; 22 a 0,10; 12 a 0,15) — a classe que, além disso, tem
gabarito positivo **zero**.

---

## 6. Comparação com o BASELINE e com o SERVIDO

Balanço do modelo servido `46a30ed9` no holdout inteiro:

| limiar | acusações **certas** (Luvas+mascara) | acusações **erradas** (Luvas+mascara) | acusações falsas nos 49 vazios |
|---:|---:|---:|---:|
| 0,05 | **80** | 32 | 43 |
| 0,07 | 61 | 16 | 33 |
| 0,10 | **40** | **5** | 23 |
| 0,15 | 15 | 0 | 12 |
| 0,20 | 4 | 0 | 5 |
| **0,30** | **0** | 0 | 0 |
| **0,50** ← produção | **0** | 0 | 0 |

- **Nenhuma das três variantes novas supera o servido.** A 0,05, limiar único, o
  servido bate A, B e C em *Sem Luvas* (67,2%/65,2% × 65,6%/58,0% da C, com B em
  n=19) e em *Sem mascara* (77,8%/74,5% × 52,1%/78,7% da C).
- **Baseline × servido:** o baseline tem precisão mais alta em *Sem Luvas*
  (85,2% × 67,2% a 0,05) e o servido tem quase o dobro do recall (65,2% × 33,3%).
  Em *Sem mascara* o servido vence nos dois (77,8%/74,5% × 69,4%/72,3%). **Não há
  motivo medido para voltar ao baseline.**
- **O servido, no limiar de produção, é silencioso.** Zero acusação em 246
  quadros com 116 violações reais. Zero falso positivo também — mas detector que
  não fala não protege ninguém.

---

## 7. VEREDITO

> ### NENHUMA das três variantes passa da barra.
>
> Não é empate: a regra de desempate por simplicidade **não chega a ser
> acionada**, porque nenhuma candidata sustenta acusação de verdade.

1. **A · presença derivada — REPROVADA, e a mais perigosa.** É a única que passa
   a régua crua em *Sem Luvas* (63,6%, n=107), e a passagem é falsa: acusou
   **100% do que julgou** (107/107, 98/98, 35/35, 35/35), e sua precisão é a
   prevalência do gabarito, por identidade aritmética. Causa medida: o modelo de
   presença detecta **8 objetos em 389 recortes de pessoa** (conf. máx. 0,062)
   contra 360 no frame cheio. A ADR-0067 já a proibia; agora há o preço.
2. **B · classe de ausência — REPROVADA por n.** É a que erra menos quando fala
   (100% em *Sem mascara* a 0,20-0,30; 78,6% a 0,05), mas **nunca chega a n=30**:
   máximo de 19 acusações em *Sem Luvas* e 28 em *Sem mascara*. Fica a um passo —
   e um passo, pela ADR-0067, não é medida.
3. **C · parte-do-corpo — REPROVADA pelo controle nulo e pela abstenção.** Passa
   a régua crua a 0,05 nas duas classes, mas em *Sem Luvas* acusou 61 de 61
   julgadas (nulo de novo) e em *Sem mascara* recusou 2 de 73. Abstém-se em
   35-97% das imagens porque a âncora (`mao`, `regiao_boca_nariz`) quase nunca é
   detectada. Sua abstenção é o comportamento **certo** pela ADR-0067 — mas com
   essa taxa ela quase não é um produto.
4. **Três das cinco classes ficam NÃO CONCLUSIVAS.** *Sem Óculos*, *Sem protetor
   de ouvido* e *Uso incorreto de mascara* têm **zero `sim`** no gabarito. Sem um
   positivo real não há recall e a precisão só pode dar 0%: toda acusação cai
   contra um denominador de zero verdades. **Isso mede o gabarito, não o modelo —
   e nenhum veredito é emitido para elas.** O único sinal que carregam é a
   contagem de acusações falsas nos 49 quadros vazios (§5).
5. **O que o cliente já tem é melhor que as três.** O servido `46a30ed9` é o
   melhor desempenho da tabela inteira nas duas classes com gabarito.
6. **Nada autoriza trocar deployment.** `46a30ed9` segue `active` nas 14 câmeras,
   inalterado.

---

## 8. ⚠️ Réguas que NÃO se comparam

**Não compare o `map50` do `val` de uma variante com o da outra.** A é medida
sobre 5 classes, B sobre 10 e C sobre 10 de uma taxonomia diferente — e mAP é
média **por classe**: tirar classes difíceis do dicionário sobe o número sem que
o detector melhore em nada. Um ranking assim premiaria a variante com menos
classes. **Só este holdout compara**: mesma prova, mesmas 246 imagens, mesmo
gabarito para as três.

## 9. ⚠️ Este veredito vale para o caminho servido ATUAL (nuvem, FP32)

A medição rodou em **FP32, via `onnxruntime`, em CPU**. O caminho servido hoje
usa **o mesmo `onnxruntime` FP32** — `onnx_rfdetr.py:158`,
`providers=["CUDAExecutionProvider", "CPUExecutionProvider"]`, sem quantização e
sem TensorRT. **Portanto o número é o do produto de hoje**, e não uma
aproximação dele.

**Mas não é transferível para um edge quantizado.** Se o EPI for para o Jetson
com **INT8/TensorRT** (direção do `EDGE_DEPLOYMENT_PLAN.md`), a quantização pode
mexer na acurácia o bastante para **inverter uma comparação apertada** — e aqui
há várias: A×C em *Sem Luvas* (63,6% × 65,6%, 2 pp), servido×C (67,2% × 65,6%,
1,6 pp), B a um passo do n mínimo. Nenhuma dessas ordens sobrevive a uma mudança
de 2-3 pp. **Antes de qualquer promoção ao edge quantizado, esta medição precisa
ser refeita no artefato INT8 real**, não herdada daqui.

---

## 10. O que este relatório NÃO mediu

- **Falso positivo difícil.** 245 dos 266 `nao` vieram do atalho `sem_pessoa`.
  Está medido "o modelo alucina em quadro vazio?"; "o modelo acusa quem **está**
  usando o EPI?" tem 4 quadros de gabarito em *Sem Luvas* e 17 em *Sem mascara*.
- **Geometria da acusação.** A comparação é por decisão (imagem × classe). Imagem
  com três pessoas conta TP mesmo se a variante acusou a pessoa errada.
- **Persistência temporal e zona.** A ADR-0067 exige as duas antes de qualquer
  acusação virar alerta. Aqui cada quadro é julgado sozinho.
- **Por que o modelo A é cego no recorte.** Provado **que** é; a causa (domínio,
  escala, proporção) é hipótese não medida.
- **Concordância entre avaliadores.** Um avaliador só, 13 minutos, 644
  julgamentos. Não há segunda opinião para medir o ruído do gabarito.
- **Acurácia sob INT8/TensorRT.** Ver §9.
- **Custo e latência.** A e C custam mais que B por frame; não entra na conta.
- **Efeito do NMS por limiar.** A inferência rodou uma vez a 0,05 e a varredura
  decidiu em cima dela; caixa suprimida na coleta não reaparece num limiar mais
  alto. Vale igual para todas — mas não é o mesmo que reinferir.

---

## 11. Proposta ao dono (nada foi executado)

1. **O limiar, não a taxonomia.** É a alavanca de maior efeito e menor risco à
   mão. A curva do §5 dá as opções para `DETECTION_CONFIDENCE_THRESHOLD` (hoje
   0,5, onde o sistema é mudo):
   - **0,10** — 40 acusações certas, **5 erradas**, 23 alucinações em vazio
     (22 delas em *Uso incorreto de mascara*).
   - **0,15** — 15 certas, **0 erradas**, 12 alucinações (todas em *Uso incorreto*).
   - 0,05 — 80 certas, 32 erradas, 43 alucinações. Recall alto, ruído alto.
2. **Desligar `Uso incorreto de mascara` da acusação** até haver gabarito: ela
   tem zero `sim` e concentra quase toda a alucinação do servido.
3. **Julgar os `nao_sei` com pessoa.** 262 julgamentos (141 quadros) estão fora
   do denominador, e os `nao` **com pessoa** somam só 21 — é esse número, não o
   de `sim`, que trava a medida de falso positivo.
4. **Não treinar mais variante antes de decidir sobre a A.** Ela não tem problema
   de treino: tem problema de domínio de entrada, e nenhuma época a mais resolve.
5. **Gabarito para as três classes vazias**, ou tirá-las do escopo de acusação
   até existir prova. Hoje elas estão servidas sem nenhuma verdade contra a qual
   medir.

---

## 📱 Resumo (celular)

**Nenhuma das 3 variantes serve.** O modelo que já está no ar (`46a30ed9`) bate
as três.

- **Sem Luvas** (69 reais): servido 67% de precisão / 65% de recall. Melhor
  variante (C) 66% / 58%. A "vence" no papel, mas só porque **acusa todo mundo**
  (107 de 107 que julgou) — número do gabarito, não do modelo.
- **Sem mascara** (47 reais): servido 78% / 75%. Melhor variante (C) 52% / 79%.
- **Sem Óculos, Sem protetor, Uso incorreto: NÃO CONCLUSIVAS** — zero "sim" no
  gabarito. Sem verdade, não há veredito.

**O problema não é a taxonomia, é o limiar.** Em produção (0,5) o sistema **não
acusa nenhuma vez** em 246 quadros com 116 violações reais.

**A fazer:**
1. Baixar `DETECTION_CONFIDENCE_THRESHOLD` de 0,5 → **0,10 ou 0,15**
   (0,15: 15 acusações, 15 certas. 0,10: 40 certas, 5 erradas).
2. Desligar `Uso incorreto de mascara` — zero gabarito e é onde o modelo mais
   alucina.
3. Julgar os `nao_sei`: metade do holdout ficou fora da conta.
4. Não treinar variante nova. A variante A é **cega no recorte de pessoa**
   (8 detecções em 389 recortes) — é bug de pipeline, não falta de treino.

⚠️ Vale para o caminho de hoje (nuvem, FP32). Se for para o edge com
INT8/TensorRT, refazer a medição — as diferenças aqui são de 2 pp e não
sobrevivem à quantização.

⛔ **Nenhum deployment foi trocado.** A decisão é sua.
