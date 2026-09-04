# V2.1 multi-escala × o gabarito real — o VEREDITO

> ## O V2.1 **não** substitui o servido nas duas classes mensuráveis.
>
> Mas ele ganhou em algo que ninguém estava medindo, e o ganho é grande:
> **cortou a alucinação em corredor vazio em 77%** contra o próprio antecessor
> (62 → 14 acusações falsas) e em **67%** contra o modelo servido (43 → 14).
>
> ⛔ Nenhum deployment foi trocado, ativado ou desativado. `46a30ed9` segue
> `active` nas 14 câmeras. A decisão é do dono.

Fecha a pergunta que [`AB-HOLDOUT-V2-VEREDITO.md`](./AB-HOLDOUT-V2-VEREDITO.md)
deixou aberta: *o buraco entre 83px e 20px era o problema?* A resposta medida é
**em parte** — e a parte que ele consertou não é a que se esperava.

- **Tenant:** `63c219d8-fbef-4f3c-a7c9-058c742482e2` (RVB) · **módulo** `epi`
- **Job:** `a04d6633-c433-40ec-b366-8cff0a232056` · **modelo:** `2ea8eb62`
  (`Logikos EPI 10 classes · 04/09 06h29`, `is_active = false`)
- **Relatórios brutos:** `evidence/ab-v21/relatorio-limiar-{030,005}.md`
- **Curva:** `evidence/ab-v21/curva-validacao-v21.md`

---

## 1. O treino

| item | valor | onde foi medido |
|---|---|---|
| dataset | `v18-multiescala` (4.594 train / 1.157 val / 706 test) | `dataset_versions` |
| taxonomia | **idêntica à variante B** (12 categorias, mesma ordem) | COCO do v18 × `dicts.sh` |
| teto de épocas | **60** (era 100) | `disparar_treinos_v2.EPOCAS_TETO` |
| paciência | 15 | `remote_train.PATIENCE` (default, não sobrescrito) |
| batch | 4 × grad_accum 4, `BATCH_FIXO=1` | `metrics.hardware.batch_fixo = true` |
| GPU | RTX 4090 24 GiB, SECURE | `metrics.hardware` |
| pod | `n3s28etrc011lb` | `training_jobs.gpu_instance_ref` |
| épocas rodadas | **21** | `metrics.epochs_ran` |
| **mAP EMA best** | **0,2349** (pico na ép. 6) | `metrics.map_ema_best` |
| map50 | 0,431 | `metrics.map50` |
| wall | 11.423 s (inclui 51 min montando o zip) | `completed_at − started_at` |
| custo estimado | US$ 7,86 | `estimate_cost_usd` |
| **custo real** | **US$ 1,7223** | saldo 15,4985 → 13,7762 |

O `actual_usd` que a API de billing reportou foi **US$ 0,9707** — 44% abaixo do
que o saldo diz. O número honesto é o delta do saldo; o do billing é
best-effort e subestima. Não use o segundo.

### A curva — convergiu, e o teto de 60 nunca foi tocado

| ép | mAP EMA | | ép | mAP EMA | | ép | mAP EMA |
|---:|--------:|---|---:|--------:|---|---:|--------:|
| 1 | 0,1517 | | 8 | 0,2319 | | 15 | 0,2167 |
| 2 | 0,1906 | | 9 | 0,2307 | | 16 | 0,2143 |
| 3 | 0,2211 | | 10 | 0,2233 | | 17 | 0,2150 |
| 4 | 0,2312 | | 11 | 0,2232 | | 18 | 0,2161 |
| 5 | 0,2310 | | 12 | 0,2238 | | 19 | 0,2156 |
| **6** | **0,2349 ← PICO** | | 13 | 0,2261 | | 20 | 0,2175 |
| 7 | 0,2343 | | 14 | 0,2198 | | 21 | 0,2161 |

**Pico na ép. 6 + paciência 15 = ép. 21, que é onde parou.** As 15 épocas após o
pico ficaram **todas** abaixo dele — sobreajuste começando, não platô ambíguo.
Não foi relógio (o pod tinha 38.247 s de teto e usou ~8.400), não foi saldo, e
**não foi o teto de épocas**: parou na 21 de 60.

Isso valida a queda de 100 → 60 pelos fatos: pela quarta vez seguida o pico ficou
entre a ép. 5 e a 8, e pela quarta vez o run acabou antes da 24. Sessenta já é
2,9× a corrida mais longa observada.

⚠️ **Não compare este 0,2349 com o 0,4386 da variante A.** São `val` diferentes,
de datasets diferentes, com número de classes diferente — e mAP é média por
classe. A régua que compara é o holdout do dono, abaixo.

---

## 2. A TABELA DO VEREDITO — limiar 0,05

O limiar único é 0,05 porque é onde estes RF-DETR de fato falam neste holdout
(a 0,30 quase todos são mudos; a tabela completa está no relatório bruto).
`V20B` é o **mesmo modelo da variante B** do veredito anterior — mesma
taxonomia, mesma prova, só a escala do dataset mudou. É o antes/depois direto.

### Sem Luvas — n real = **69**, avaliadas 122 · *controle nulo = **56,6%***

| modelo | TP | FP | FN | precisão | recall | n |
|---|---:|---:|---:|---:|---:|---:|
| **V2.1 multi-escala** | 28 | 19 | 41 | **59,6%** | **40,6%** | **47** |
| V20B (antes) | 14 | 5 | 55 | 73,7% | 20,3% | 19 |
| baseline `b3ae42b6` | 23 | 4 | 46 | 85,2% | 33,3% | 27 |
| **SERVIDO `46a30ed9`** | 45 | 22 | 24 | **67,2%** | **65,2%** | 67 |
| A · presença derivada | 68 | 39 | 1 | 63,6% | 98,6% | 107 |
| C · parte-do-corpo | 40 | 21 | 29 | 65,6% | 58,0% | 61 |

**O V2.1 destravou a classe.** Pela primeira vez a taxonomia B chega a n ≥ 30
(19 → **47** acusações) e passa a régua da ADR-0067. O recall dobrou
(20,3% → 40,6%).

**E mesmo assim perde do servido nas duas pontas** (59,6%/40,6% × 67,2%/65,2%).
Pior: **59,6% supera o controle nulo por apenas 3,0 pontos** (56,6%). Num
conjunto onde 57% dos quadros têm a violação, "acuse sempre" tira 56,6% sem
olhar para a imagem. Três pontos acima disso é informação quase nenhuma.

### Sem mascara — n real = **47**, avaliadas 113 · *controle nulo = **41,6%***

| modelo | TP | FP | FN | precisão | recall | n |
|---|---:|---:|---:|---:|---:|---:|
| **V2.1 multi-escala** | 19 | **0** | 28 | **100,0%** | 40,4% | **19** |
| V20B (antes) | 22 | 6 | 25 | 78,6% | 46,8% | 28 |
| baseline `b3ae42b6` | 34 | 15 | 13 | 69,4% | 72,3% | 49 |
| **SERVIDO `46a30ed9`** | 35 | 10 | 12 | **77,8%** | **74,5%** | 45 |
| A · presença derivada | 46 | 52 | 1 | 46,9% | 97,9% | 98 |
| C · parte-do-corpo | 37 | 34 | 10 | 52,1% | 78,7% | 71 |

**19 acusações, ZERO erradas.** É o único modelo da tabela inteira que não errou
uma vez. Mas **n = 19 < 30**: pela ADR-0067 isso **não é medida**, e a regra
existe justamente porque "66,7% sobre 3" já enganou antes. Aqui o multi-escala
foi na direção contrária à de *Sem Luvas* — ficou mais **calado** (28 → 19) e
mais **certo** (78,6% → 100%).

### As três classes NÃO CONCLUSIVAS

*Sem Óculos*, *Sem protetor de ouvido* e *Uso incorreto de mascara* têm **zero
`sim`** no gabarito. Sem um positivo real não há recall, e a precisão só pode dar
0%. **Isso mede o gabarito, não o modelo — nenhum veredito é emitido para elas.**

---

## 3. O que o V2.1 ganhou de verdade: alucinação em corredor vazio

As 49 imagens de corredor vazio foram todas julgadas `nao` nas cinco classes.
**Toda acusação ali é falsa, por construção.** É a medida mais limpa de
alucinação que este gabarito oferece — e é onde o multi-escala aparece.

| classe (limiar 0,05) | **V2.1** | V20B | baseline | **SERVIDO** |
|---|---:|---:|---:|---:|
| Sem Óculos | **2** | 6 | 3 | 6 |
| Sem protetor de ouvido | **9** | 23 | 8 | 8 |
| Uso incorreto de mascara | **3** | 33 | 30 | **29** |
| **total de acusações falsas** | **14** | **62** | **41** | **43** |

- **−77% contra o próprio antecessor** (62 → 14).
- **−67% contra o modelo servido** (43 → 14).
- O caso mais gritante: `Uso incorreto de mascara`, que é a pior alucinação do
  servido (**29 dos 49 quadros vazios**) e não tem um único positivo no
  gabarito, cai para **3** no V2.1.

Somando com o FP zerado em *Sem mascara*, o desenho do V2.1 é claro: **ele fala
menos e erra muito menos quando fala.** O que ele não ganhou foi cobertura.

---

## 4. VEREDITO

1. **O V2.1 NÃO supera o servido nas duas classes mensuráveis.** Perde em
   precisão *e* recall em *Sem Luvas* (59,6%/40,6% × 67,2%/65,2%) e em recall em
   *Sem mascara* (40,4% × 74,5%). **Nada aqui autoriza trocar deployment.**
2. **O multi-escala funcionou parcialmente, e é mensurável.** Em *Sem Luvas* ele
   fez a taxonomia B cruzar a barreira de n = 30 pela primeira vez (19 → 47) e
   dobrou o recall. O buraco de escala era real; fechá-lo destravou a classe.
3. **O ganho grande está na alucinação, não na acusação.** −77% de acusação falsa
   em corredor vazio contra o antecessor, −67% contra o servido, e FP zero em
   *Sem mascara*. Nenhuma das duas rodadas anteriores mediu isso como objetivo;
   é o resultado mais forte desta.
4. **O controle nulo continua sendo o juiz que derruba.** Os 59,6% de *Sem Luvas*
   ficam 3,0 pontos acima de "acuse sempre" (56,6%). Passar a régua de 50% da
   ADR-0067 **não é o mesmo que acrescentar informação** — e sem o controle nulo
   na tabela essa distinção some.
5. **Três das cinco classes seguem não mensuráveis** por falta de `sim` no
   gabarito. Isso é dívida do gabarito, não do modelo.

### A próxima alavanca, pelo que os números mostram

O V2.1 tem **precisão sem cobertura**: 100% em *Sem mascara*, mas só 19
acusações; 59,6% em *Sem Luvas*, com 41 dos 69 casos reais passando batido. O
gargalo mudou de "erra quando fala" para "**não fala**".

Duas alavancas, na ordem em que os números as sustentam:

1. **Mais positivos reais das classes de ausência, não mais escala.** O
   multi-escala já entregou o que tinha para entregar — corrigiu a alucinação e
   destravou n em uma classe. `Sem Luvas` tem 860 caixas após o rebalanceamento
   (era 255); `Sem mascara` continua abaixo disso. Recall de 40% com precisão de
   100% é falta de exemplo, não falta de resolução.
2. **Ampliar o gabarito antes de mais um treino.** Três das cinco classes não
   têm veredito possível, e as duas que têm apoiam-se em 69 e 47 positivos. Cada
   rodada de treino custa ~US$ 1,72 e três horas; uma rodada de julgamento do
   dono custou 13 minutos e é o que decide se qualquer número acima significa
   alguma coisa. **A medida está mais barata que o treino, e está mais escassa.**

⚠️ Não recomendo subir o limiar de produção com base nesta tabela. A 0,30 o V2.1
faz 4 acusações em *Sem Luvas* e 0 em *Sem mascara* — o mesmo mutismo de todos
os outros. A escolha de limiar continua sendo uma decisão em aberto, com a curva
completa nos relatórios brutos.

## 5. ⚠️ Limites desta medição

Valem aqui, sem alteração, os mesmos avisos do veredito anterior: a inferência
rodou em **FP32 via `onnxruntime` em CPU** (o mesmo caminho servido hoje na
nuvem, não o TensorRT INT8 do edge); o `nao_sei` do gabarito ficou fora do
numerador **e** do denominador; e o negativo do gabarito é quase todo corredor
vazio — o falso positivo difícil (acusar quem *está* usando o EPI) tem só 4
quadros em *Sem Luvas* e 17 em *Sem mascara*.

**Guarda de vazamento:** 0 colisão de nome, 0 de conteúdo, 246/246 imagens
conferidas por sha256 contra **15 COCOs** — os 12 do veredito anterior **mais os
três splits do `v18-multiescala`**. O gabarito também foi reconferido fora do
dataset pelos quatro canais de `conferir_gabarito_fora.py` (`frame_id` 0 · pai do
recorte 0 · sha256 0 · `dataset_role` = `pool` em 3.585 ids) **antes** do
disparo.
