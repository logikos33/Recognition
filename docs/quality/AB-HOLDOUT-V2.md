# A/B das três taxonomias no holdout congelado — resultado

**Veredito: NÃO CONCLUSIVO, e a causa está medida.** Nenhuma variante sustenta
acusação na régua da ADR-0067, e o motivo não é empate: é falta de gabarito.
Este documento entrega os números para que a decisão seja do dono com o dado na
mão, não um vencedor inventado.

## Como foi medido

- **Holdout único**, idêntico nas três variantes por construção
  (`dataset-v2/split_membership.json`) — 248 imagens, 8.303 s de treino atrás de
  cada modelo. Guarda de vazamento holdout×treino: **0 colisão de nome, 0 de
  conteúdo**, 248/248 conferidas por sha256.
- **Limiar único 0,30** para todas as variantes (a varredura de 0,15 a 0,50 está
  no relatório bruto, para a escolha ficar explícita e não por-variante).
- **Estágio 1 (pessoa):** `yolox_nano.onnx`, **o arquivo servido**, conferido
  bit-a-bit contra o do Jetson — sha256 `c789161ed43c8269…`. (Eu havia baixado o
  YOLOX-nano oficial da Megvii como equivalente; o hash provou serem **o mesmo
  arquivo**, então não há divergência entre público e servido a declarar.)
  Entrada 416×416, a do grafo servido.
- **Baseline v10-ft** (`b3ae42b6`) rodado no MESMO holdout, mesmo limiar.

## O que o holdout tem de gabarito de ausência — o número que decide tudo

| classe de acusação | caixas no holdout inteiro (248 img) | caixas só em frame cheio (204 img) |
|---|---:|---:|
| Sem protetor de ouvido | **36** | **30** |
| Uso incorreto de mascara | 14 | 14 |
| Sem Óculos | 3 | 0 |
| Sem Luvas | **0** | **0** |
| Sem mascara | **0** | **0** |

Com `_N_MINIMO` = 30 acusações, **uma única classe** tem material para uma
medida: *Sem protetor de ouvido*. Três das cinco têm gabarito ZERO ou quase.

⚠️ **Correção de uma premissa que estava em circulação:** o holdout NÃO é
majoritariamente recorte. São **204 frames cheios de 248 (82%)**. Por isso as
duas tabelas pedidas (holdout inteiro × só cheios) dão praticamente o mesmo
resultado — o descasamento de domínio entre elas é pequeno, ao contrário do que
se supunha. O problema não é o domínio: é a **quantidade de gabarito**.

## A única classe mensurável — *Sem protetor de ouvido*, limiar 0,30

**Holdout inteiro (n = 36 reais)**

| variante | TP | FP | FN | precisão | recall | abstenção | acusações |
|---|---:|---:|---:|---:|---:|---:|---:|
| A · presença derivada | 35 | 205 | 1 | **14,6%** | 97,2% | 8 (3,2%) | 240 |
| B · classe de ausência | 7 | 24 | 29 | **22,6%** | 19,4% | 0 | 31 |
| C · sobreposição geométrica | 31 | 168 | 5 | **15,6%** | 86,1% | 49 (19,8%) | 199 |
| **baseline v10-ft** | 5 | 3 | 31 | **62,5%** | 13,9% | 0 | 8 |

**Só frames cheios (n = 30 reais)** — o domínio em que o modelo é de fato servido

| variante | TP | FP | FN | precisão | recall | abstenção | acusações |
|---|---:|---:|---:|---:|---:|---:|---:|
| A · presença derivada | 29 | 169 | 1 | 14,6% | 96,7% | 6 (2,9%) | 198 |
| B · classe de ausência | 5 | 21 | 25 | 19,2% | 16,7% | 0 | 26 |
| C · sobreposição geométrica | 26 | 144 | 4 | 15,3% | 86,7% | 34 (16,7%) | 170 |

As duas tabelas contam a mesma história — como esperado, já que 82% do holdout
já é frame cheio.

**Nenhuma das três novas passa da barra de 50% de precisão da ADR-0067.** O
único número acima da barra é o do baseline (62,5%), e ele vem de **8 acusações**
— abaixo do n mínimo, então também não é medida, é indício.

## O achado que vale mais que o veredito ausente

**A variante A acusa quase tudo.** Em *todas* as classes ela emite ~240
acusações sobre 248 imagens, com precisão entre 0% e 14,6%:

| classe | acusações da A | reais | precisão |
|---|---:|---:|---:|
| Sem Luvas | 240 | 0 | 0,0% |
| Sem mascara | 240 | 0 | 0,0% |
| Sem Óculos | 240 | 3 | 1,2% |
| Sem protetor de ouvido | 240 | 36 | 14,6% |

Isto é a **quantificação direta do que a ADR-0067 proíbe**: derivar violação do
silêncio do detector de presença transforma "não detectei" em "não está lá", e o
resultado é um sistema que acusa 97% dos quadros. A ADR já proibia por
princípio; agora há número.

**A variante C abstém-se onde deveria falar.** 89-97% de abstenção em quase toda
classe, e **100% em *Uso incorreto de mascara*** — a parte do corpo âncora
(`regiao_boca_nariz`, `regiao_olhos`, `mao`) quase nunca é detectada. A absteção
da C é o comportamento correto segundo a ADR-0067 (não falar sem evidência
positiva), mas com essa taxa ela quase não fala.

**A variante B é a única que erra pouco quando fala** — é a única que chega a
50% de precisão em alguma célula (*Uso incorreto*, n=6) — mas o recall dela é
baixo (19,4%): fala pouco e perde 29 de 36.

## Conclusão honesta

1. **O A/B não pode ser decidido com este holdout.** Não por empate — por falta
   de gabarito de ausência. Três das cinco classes de acusação têm ZERO ou 3
   caixas. Isso já estava previsto em `montar_dataset_v2.py` e a medição
   confirma, agora com os modelos treinados na mão.
2. **O que desbloqueia é colheita, não treino.** Enquanto *Sem Luvas* e *Sem
   mascara* tiverem 0 caixas no holdout, nenhum treino resolve — a prova não
   existe. A colheita de frames cheios anotados é a dependência real.
3. **Nada aqui autoriza trocar o modelo servido.** O baseline v10-ft segue sendo
   o único com precisão acima da barra na única classe mensurável, ainda que com
   n insuficiente.

Relatórios brutos (com varreduras de limiar e de IoMin): `ab_holdout_completo.md`,
`ab_holdout_cheios.md`, `ab_baseline_v10ft.md`.

## ⚠️ Réguas que NÃO se comparam

O `map50` do `val` de cada variante (A 0,764 · B 0,481 · C 0,677) **não ordena as
taxonomias** e não se compara com o 0,550 do baseline: conjuntos diferentes,
5 × 10 × 10 × 11 classes, distribuições diferentes. mAP com menos classes infla
sozinho. A única régua comum é a deste documento.
