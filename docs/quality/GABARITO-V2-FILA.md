# A fila do gabarito v2 — quais 150 quadros, em que ordem, e por quê

**O que isto resolve.** O A/B das três variantes saiu não conclusivo
(`AB-HOLDOUT-V2.md`): o holdout tem **0 caixa de `Sem Luvas` e 0 de
`Sem mascara`**, e só uma classe das cinco tinha material para medir. O que
desbloqueia não é treino, é **gabarito**. Foram colhidos 440 quadros cheios
1920×1080 do gravador do RVB (7 câmeras, 01/09 07h → 02/09 16h20, fábrica em
operação). Este documento decide **quais ~150 o dono anota e em que ordem**, para
render o máximo por minuto da hora mais cara do projeto.

Artefatos:

| arquivo | o quê |
|---|---|
| `evidence/gabarito-v2/fila-gabarito-150.csv` | a lista. `frame_id` na 1ª coluna, na ordem de anotação, com score, critério e câmera |
| `evidence/gabarito-v2/pessoas-yolox-nano.jsonl` | as 1.359 caixas de PESSOA medidas nos 440 quadros (a matéria-prima do score) |
| `evidence/gabarito-v2/ROTEIRO-DA-SENTADA.md` | o atalho operacional: link por câmera + quais cards clicar |
| `scripts/ops/fila_gabarito_v2.py` | `--calibrar` · `--pessoas` · `--fila` · `--autoteste` |

---

## ⛔ Nenhum contendor propôs caixa aqui — e a entrega é LIMPA

A restrição foi cumprida na letra. Nem para pré-preencher, **nem para ordenar**:
nenhuma variante A (`6ca25ee9`), B (`1deadfb0`), C (`b9243540`), nem o baseline
v10-ft (`b3ae42b6`), nem o servido (`46a30ed9`) tocou neste arquivo. Existe um
JSONL do servido rodado sobre estes MESMOS 440 quadros
(`evidence/baseline-campo-v2/deteccoes-46a30ed9.jsonl`) e ele foi
**deliberadamente não lido** — usá-lo até para ordenar já enviesaria a fila para
onde o réu olha.

O único modelo usado é o detector de **PESSOA** — `yolox_nano_SERVIDO.onnx`,
COCO, classe `person`, cópia bit-a-bit do que roda no Jetson. Ele **não é
contendor**: não conhece nenhuma classe de EPI e não pode propor uma. Serve só
para selecionar e ordenar.

**Decisão sobre pré-preenchimento: ENTREGA LIMPA, sem nenhuma caixa.** O caminho
alternativo (Gemini, que também não é contendor) foi verificado e **não existe
credencial** no projeto: `railway variables -s API-V3 -e Desenvolvimento --kv`
não tem nenhuma chave `GEMINI|GOOGLE|VERTEX|OPENAI|ANTHROPIC`, e o ambiente local
também não. Inventar credencial não era opção, e limpo é a opção segura de
qualquer forma: caixa na tela puxa a confirmação do anotador, e a medida vira
concordância em vez de verdade.

---

## O critério, declarado

### Gate (a) — o quadro é anotável?

Exige **≥1 pessoa com ≥200 px de altura** no quadro original. Quadro sem pessoa
enquadrada não pode conter ausência de EPI: é minuto perdido.

O piso de 200 px não é chute — é o que se vê. Recortando pessoas reais em
resolução nativa a 200 / 260 / 330 / 420 / 550 / 700 px de altura: **a partir de
~330 px a mão nua e o rosto descoberto são inequívocos**; em 200-260 px a mão
tem ~20 px e o julgamento fica no limite. Por isso 200 px é usado como **piso do
que é possível**, e a altura entra de novo no score como qualidade — os quadros
de 200 px afundam sozinhos para o fim da fila em vez de serem cortados fora.

### Ordem (b) — probabilidade de conter ausência real

`score = 0,55 × visibilidade + 0,25 × densidade + 0,20 × contexto`

- **Visibilidade (0,55)** — altura em px da pessoa mais bem enquadrada, saturando
  em 420 px (mão ≈ 1/10 da altura → ~42 px, leitura confortável). Caixa colada na
  borda superior paga metade: cabeça cortada é rosto que não se julga.
- **Densidade (0,25)** — `1 − 0,55ⁿ` sobre as pessoas anotáveis. Mais gente, mais
  chance de alguém estar sem; e o minuto do dono rende mais caixas por quadro
  aberto.
- **Contexto (0,20)** — **PRIOR DECLARADO, não medida.** Refeitório/convivência é
  onde máscara e luva SAEM (comer, beber, fumar) = 1,0; porta de entrada é onde
  ainda não se colocou = 0,6; resto = 0,3. Fora das janelas de troca de turno e
  refeição (07-09, 11-14, 16-18) paga 0,7 do valor. Peso pequeno de propósito, e a
  **cota de 30% por câmera** impede que um prior errado sequestre o holdout.

### O que foi TENTADO e descartado por não se sustentar no dado

**Razão de aspecto** (h/w) para separar "corpo inteiro" de "costas em close".
Medida e descartada: a mediana é ~2,0-2,2 em **todas** as faixas de altura
(200-300, 300-420, 420-600, 600-900 px). Não discrimina nada. Não entrou.

---

## O achado que muda o tamanho da sentada

**Os 440 quadros não são 440 momentos. São 90.**

A mediana do intervalo entre quadros consecutivos da mesma câmera é **0,5 s** — a
colheita veio em rajadas. Agrupando por câmera + intervalo ≤ 2 s:

| conjunto | quadros | momentos distintos |
|---|---:|---:|
| todos os 440 | 440 | 140 |
| só os que passam o gate (≥1 pessoa ≥200 px) | 340 | **90** |

Dois quadros da mesma rajada são quase o mesmo pixel: o segundo custa um minuto
inteiro do dono e quase não acrescenta informação. Por isso a fila entrega
**primeiro um representante de cada um dos 90 momentos** (posições 1-90) e só
depois um segundo quadro das melhores rajadas (posições 91-150, marcadas
`dup_rajada=sim`).

> **A consequência prática, e ela importa:** as posições **1 a 90 são a sentada**.
> A partir da 91 ele está anotando o mesmo instante meio segundo depois. Se o
> orçamento é 30-60 min, 90 quadros a 20-40 s cada fecham exatamente a janela — e
> ele pode parar na 90 sabendo que não deixou nada distinto para trás.
>
> Isto também é um alerta para o A/B: 150 quadros dessa colheita **não são 150
> amostras independentes**. O `_N_MINIMO` = 30 da ADR-0067 tem de ser contado em
> momentos, não em quadros, senão o n vem inflado por quase-duplicatas.

---

## Medições (item 5)

Tudo abaixo é contado. Comando: `python3 scripts/ops/fila_gabarito_v2.py --fila`.

### Quantos dos 440 têm pessoa

| | quadros | % |
|---|---:|---:|
| medidos | 440 | 100% |
| com **qualquer** pessoa detectada | **397** | 90,2% |
| com pessoa **≥200 px** (gate) | **340** | 77,3% |
| com pessoa, mas todas < 200 px | 57 | 13,0% |
| **sem nenhuma pessoa** | **43** | 9,8% |

1.359 caixas de pessoa no total. Alturas: p25 = 141 px, mediana = 214 px,
p75 = 331 px, p90 = 435 px, máx = 867 px.

### Distribuição do score (os 340 aptos)

| min | p25 | mediana | p75 | máx |
|---:|---:|---:|---:|---:|
| 0,330 | 0,682 | 0,783 | 0,844 | 0,996 |

Nos 90 momentos que abrem a fila: mediana 0,783, e a altura mediana da melhor
pessoa é **427 px** — acima do limiar de legibilidade observado.

### Quadros por câmera na fila de 150

| câmera | na fila | dos quais momentos distintos |
|---|---:|---:|
| Entrada Usinagem Madeira 2 | 42 | 21 |
| Espaço de convivência | 41 | 24 |
| Entrada WC Usinagem Papelão | 29 | 16 |
| Entrada Expedição | 15 | 9 |
| Entrada Preparação | 9 | 9 |
| Entrada Expedição 02 | 7 | 7 |
| Entrada Usinagem Madeira 01 | 7 | 4 |

Nenhuma câmera passa de 28% da fila (cota = 30%). Total de pessoas anotáveis:
**186 nos 90 momentos**, 322 nos 150 quadros.

### Estimativa honesta de quantos contêm ausência REAL

Auditoria visual minha de **15 posições amostradas da fila final**
(1, 7, 13, …, 85), olhando o recorte da maior pessoa em resolução nativa:

| o dono consegue marcar… | em quantas das 15 | extrapolado para os 90 momentos |
|---|---:|---:|
| `Sem Luvas` (mão nua legível) | **10** | ~60 momentos |
| `Sem mascara` (rosto descoberto legível) | **7** | ~42 momentos |
| nada útil (costas/escuro/pequeno) | 4 | ~24 momentos |

**A estimativa NÃO é baixa** — e a notícia boa é maior que isso: nas áreas
colhidas **praticamente ninguém usa luva**, então `Sem Luvas` deve render bem
acima do `_N_MINIMO` = 30. Máscara aparece nos dois estados (há gente
mascarada em quadro), o que dá material para `mascara` e para `Sem mascara` no
mesmo lote.

⚠️ As três ressalvas que ele deve saber **antes** de sentar, não no minuto 40:

1. **Isto é a minha leitura de 15 recortes, não o veredito dele.** A taxa cai
   conforme desce a fila — por construção.
2. **Altura não enxerga orientação.** O sinal mais forte do score é o tamanho da
   pessoa, e uma pessoa grande **de costas** (ex.: posição 49, 787 px) pontua alto
   e vale pouco: nem mão nem rosto. Não há como corrigir isso sem outro modelo, e
   outro modelo seria contendor ou nova dependência. Fica declarado.
3. **Domínio.** Boa parte do material é área de convivência e portaria, não linha
   de produção. `Sem Luvas` no refeitório é *a classe presente na imagem*, mas
   não é necessariamente *violação de política*. O holdout mede detecção, não
   política — e a cota de 30% impede que o refeitório domine.

---

## O atalho da sentada (item 4)

**O Estúdio não aceita ordem arbitrária nem lista de ids — conferido, não
suposto.** A galeria monta o filtro em `TrainingGallery.tsx:244-255` (`page`,
`page_size`, `curation_status`, `is_annotated`, `pending_review`, `camera_ids`,
`source`) e o Estúdio anda pelo array que ela entregou
(`Dados.tsx:141` → `AnnotationStudio frames/initialIndex`). A ordem é sempre
`created_at DESC, id DESC` (`FrameRepository.list_frames_paginated`, `ordem_sql`)
ou `incerteza`. **Não existe hoje** parâmetro de ordem custom nem de lista de
`frame_id`. Nenhuma feature nova foi inventada.

**O que existe hoje e resolve.** Estes 440 quadros são os **mais novos do
acervo** — conferido: nas últimas 12 h há exatamente 440 linhas, todas
`source='nvr'`, todas `curation_status='active'`, todas `width>=1280`, nada se
intercala. Logo eles ocupam **o prefixo** da galeria, e a posição de cada card é
determinística e calculável. Ela está na coluna `posicao_na_galeria` do CSV, e
foi **conferida contra o banco: 41/41 na câmera de convivência, zero
divergência**.

Então o atalho é:

1. Abrir `/novo/estudio/dados?camera=<CAMERA_ID>&status=nao_anotado`
   (o link já aplica o filtro; `Origem = Câmera/NVR` é opcional — nessas 7
   câmeras **todo** quadro não anotado já é `nvr`, medido: 2.283 de 2.283).
2. A galeria mostra 60 cards por página. Ir à página indicada e **clicar no
   card** — o Estúdio abre naquele índice, e o contador `N de 60` do cabeçalho
   confirma que é o card certo. `→` anda para o próximo.
3. `ROTEIRO-DA-SENTADA.md` lista, por câmera e por página, exatamente quais cards
   clicar — as câmeras já em ordem de rendimento por minuto.

⚠️ Anotar uma câmera de uma vez só: ao sair e voltar, o quadro já anotado sai do
filtro *Não anotadas* e a numeração dos cards anda para trás.

---

## Notas de método

**Detector de pessoa: duas grades, e o porquê é medido.** O `PersonDetector` do
edge usa ladrilhamento 2×2, calibrado para o substream 704×480. Aqui o quadro é
1920×1080 e 2×2 **não serve**: acusou pessoa em 40/40 quadros da amostra,
inclusive num pátio comprovadamente vazio. Medido em 40 quadros (`--calibrar`):

| grade | quadros c/ pessoa | pessoas | pessoas ≥200 px |
|---|---:|---:|---:|
| 1×1 | 26 | 33 | 26 |
| 2×2 | 40 ← falso | 74 | 49 |
| 3×3 | 33 | 93 | 60 |

E o ladrilho **recorta quem é alto**: a maior caixa da grade 3×3 mede exatamente
432 px, que é a altura do ladrilho, não da pessoa. Como a altura é o sinal que
ordena a fila, medir errado ordenaria errado. Solução: **união de 1×1 e 3×3**,
fundidas por contenção (≥70% da caixa menor dentro da maior — não IoU, porque um
fragmento tem IoU baixo com a pessoa inteira e sobreviveria ao NMS).

**Uma armadilha de fuso, encontrada e corrigida.** `captured_at` vem com
`tzinfo=UTC`, mas o valor é o **relógio de parede da fábrica** — conferido contra
o relógio queimado na imagem: o quadro cujo `captured_at` é
`2026-09-01T07:00:00+00:00` tem `01/09/2026 07:00:00` impresso no canto. Aplicar
o UTC-3 óbvio jogaria o almoço nas 15 h e transformaria a colheita
(07:00→16:20) numa madrugada de 04:00→13:20 numa fábrica que está operando. O
deslocamento é zero — e isso é medido, não suposto.

**Autoteste.** `--autoteste` cobre fusão de grades, gate, saturação da
visibilidade, densidade, prior de contexto, agrupamento em rajada, os dois passes
da fila e a cota por câmera. Sem rede, sem banco.
