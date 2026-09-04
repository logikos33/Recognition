# Roteiro da sentada — gabarito v3 (as três classes de cabeça)

Gerado por `scripts/ops/fila_gabarito_v2.py --fila --perfil cabeca`.
Não editar à mão.

## Por que esta fila existe

As três classes abaixo continuam **não conclusivas** — o gabarito tem
ZERO `sim` nelas. Isso mediu a AMOSTRA, não a fábrica:

- elas foram perguntadas em **51 dos 246** quadros da sentada anterior
  (20,7%), porque moram atrás do acordeão *Mais 3 classes*;
- e esses 51 são justamente os de pessoa **menor** — mediana 322 px,
  contra 536 px nos quadros que renderam `sim`. Abaixo de 350 px de
  pessoa, NENHUMA classe rendeu `sim` na sentada anterior (0 em 53),
  nem as duas que estavam em foco.

Nesta rodada as três estão **à vista** (foco) e `Sem Luvas`/`Sem mascara`
foram para trás do acordeão. E a fila só traz quadro com pessoa de
**≥ 350 px**, ordenado por duas medidas e não por
palpite: quanto aquela câmera RENDE destas três (contado nos 2.705
recortes já anotados) **vezes** quanto dela você CONSEGUIU julgar na
sentada anterior (as duas colunas da tabela abaixo).

## Como usar

Abra **`/novo/estudio/gabarito`**. Não há link por câmera nem número de
card: os **200 quadros** desta fila ocupam as primeiras
posições (`priority_rank` 1..200) e os 246 já
julgados foram empurrados para trás.

⚠️ O cabeçalho deve dizer **`1 de 446`**. Se abrir num número
diferente, o aparelho guardou a posição da sentada anterior — toque `←`
até chegar em 1, ou abra numa aba anônima.

Três perguntas por quadro, e o atalho **não há pessoa** responde as
cinco de uma vez. Não desenhe caixa: o gabarito é resposta por imagem.

## Composição da fila

| câmera | momentos | repetições | tem uma das 3 | ele consegue julgar |
|---|---:|---:|---:|---:|
| Entrada Preparação | 60 | 0 | 61.7% | 61.5% |
| Entrada Usinagem Madeira 2 | 40 | 0 | 15.4% | 52.4% |
| Espaço de convivência | 25 | 0 | 86.2% | 14.6% |
| Corredor Lateral usinagem Madeira | 23 | 0 | 10.6% | 96.2% |
| Entrada Usinagem Madeira 01 | 15 | 0 | 21.8% | 50.0% |
| Entrada Expedição | 13 | 0 | 65.3% | 50.0% |
| Manutenção | 9 | 0 | 22.2% | 47.9% |
| Sala de Colagem | 7 | 0 | 22.8% | 47.9% |
| Corredor Segurança do trabalho | 4 | 0 | 63.4% | 47.9% |
| Qualidade 06 | 4 | 0 | 45.8% | 47.9% |
| **total** | **200** | **0** | | |

São **200 momentos distintos** (rajada de 0,5 s conta como um)
mais 0 repetições de rajada, que ficam no fim
e podem ser puladas sem perder nada.

## Quanto isto deve render — e o que pode dar errado

343 pessoas julgáveis em
200 quadros (média 1.72 por quadro). Do rendimento contado por câmera:

| classe | quadros que devem CONTER | que ele deve conseguir JULGAR |
|---|---:|---:|
| Sem protetor de ouvido | 74 | **35** |
| Uso incorreto de mascara | 26 | **16** |
| Sem Óculos | 29 | **13** |
| *≥1 das três* | *104* | |

A coluna da direita é a que vira `sim`, e segue **otimista**: o desconto
de legibilidade foi medido nas suas respostas de `Sem Luvas`/`Sem mascara`
— a mão e o rosto inteiro, que se veem de mais ângulos do que a orelha.
Se na hora o `não sei` vier bem mais do que isto, o problema deixa de ser
fila e passa a ser **enquadramento de câmera** — e aí a saída é
lente/posição, não anotação.

O piso do que desbloqueia é **1 `sim` por classe**: já tira as três do
não-conclusivo. A mais magra da fila é *Sem Óculos*, com **13** — ainda uma ordem de grandeza acima do
piso, mas é ela que se perde primeiro se a legibilidade real for pior
do que a medida.
