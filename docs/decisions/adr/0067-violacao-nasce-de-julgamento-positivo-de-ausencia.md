# ADR-0067 — Violação nasce de julgamento POSITIVO de ausência

- **Status:** Aceita
- **Data:** 2026-08-25
- **Decisor:** Vitor Emanuel
- **Contexto imediato:** ADR-0065 (presença é conformidade, ausência é
  violação) diz *o que* cada polaridade significa. Esta diz *de onde* uma
  violação pode nascer.

---

## Decisão

**Violação NUNCA nasce do silêncio do detector de presença.**

Não-detecção ≠ ausência. Uma violação exige **um** de dois caminhos positivos:

1. **Classe de AUSÊNCIA do detector**, e só enquanto essa classe sustentar a
   régua — precisão ≥ 50% em campo virgem.
2. **Classificador de recorte com abstenção**: pessoa (âncora) → recorte →
   veredito `{com | sem | não visível}`, e a violação só nasce quando o veredito
   é `sem`, **com confiança ≥ o limiar da classe**, **sustentado por N
   segundos/frames**, e **na zona onde aquele EPI é exigido**.

**`não visível` é abstenção, jamais violação.** Pessoa de costas não é culpada.

**Presença alimenta conformidade** — telemetria, nunca alerta.

---

## Contexto: os números que forçaram esta decisão

### Por que negação pura acusaria metade dos conformes

Medição do A/B do #536, campo virgem de 289 frames e 403 caixas, verdade 100%
humana, modelo `v15-tudo` no melhor limiar (0,30):

| classe (presença) | recall |
|---|---:|
| Protetor auditivo | 68,9% |
| mascara | 76,9% |
| Óculos | 63,6% |
| Botas | 44,4% |
| Luvas | 41,2% |

Se "não detectei protetor auditivo" virasse "está sem protetor auditivo", o
sistema acusaria **31% dos que estão usando** — e, em `Luvas`, **59%**. Num
turno de 28 câmeras isso não é um alerta ruim: é um produto que o operador
desliga na primeira semana.

O recall agregado do melhor braço é **0,57**. A negação pura tem, por
construção, `1 − recall` de falso positivo. Não há limiar que conserte isso,
porque o erro não está na confiança da detecção — está em **inferir um fato a
partir da ausência de evidência**.

### Por que o caminho 1 existe, mas só para algumas classes

Duas classes de ausência sustentam a régua hoje (mesma medição, `v15-tudo`):

| classe de ausência | precisão | n proposto |
|---|---:|---:|
| **Sem protetor de ouvido** | 40,0% | 30 |
| **Uso incorreto de mascara** | 61,9% | 42 |
| Sem Óculos | 66,7% | 3 |
| Sem Luvas | 25,0% | 4 |
| Sem mascara | 0,0% | 6 |

`Uso incorreto de mascara` passa a régua com folga. `Sem protetor de ouvido`
está em 40% e **ainda não passa** — fica fora até passar. `Sem Óculos` tem
66,7% sobre **3 propostas**: n insuficiente para dizer qualquer coisa, e
tratá-lo como aprovado seria confundir sorte com evidência.

### Por que o caminho 2 precisa existir

O propositor **não desenha uma única caixa de ausência**. Medido comparando os
dois exports do mesmo tenant:

| classe | `só-humano` | `tudo` (humano + proposta) |
|---|---:|---:|
| Protetor auditivo | 1027 | 2827 |
| **Sem protetor de ouvido** | **505** | **505** |
| **Sem Luvas** | **178** | **178** |
| **Sem mascara** | **134** | **134** |

Presença chega a 2,75×. Ausência: **empate exato, até o último dígito**. O
volante que gira sozinho gira só para presença. Sem um segundo caminho, as
classes de ausência dependem para sempre de anotação humana desenhada caixa a
caixa — e a #537 mostra que esse ritmo não fecha.

### Por que recorte, e não frame inteiro

O estágio 1 já existe e já foi medido: YOLOX-nano com ladrilhamento 2×2 leva o
recall de pessoa de 52% para **90%** (40 frames reais da RVB). E os frames que
o edge sobe para o pool **já são recortes de pessoa** — `crop_person()` roda
antes do upload, com margem de 25% em X e 8% em Y.

O acervo de classificação já existe também: **1.095 vereditos**, todos
`manual`, gravados pela aba Classificar.

---

## Consequências

### O que fica proibido

- ⛔ Derivar violação de "a classe de presença não apareceu". Nenhum caminho,
  nenhuma exceção, nem "só para capacete", nem "só quando a confiança da
  pessoa é alta".
- ⛔ Tratar `não visível` como violação, ou omiti-lo do veredito para
  "simplificar" — a abstenção é informação, e some se não tiver nome.
- ⛔ Promover classe de ausência que não sustenta a régua. `Sem mascara` a 0%
  de precisão não vira alerta porque "faz sentido".

### O que fica exigido

- **Régua publicada por classe** antes de qualquer promoção: precisão, recall e
  **taxa de abstenção**, em campo virgem, com o `n` visível. Precisão sem `n` não
  é medida.
- **Persistência temporal** configurável: um veredito `sem` num único frame não
  é violação. O número de segundos/frames é por classe e fica no cadastro.
- **Zona**: violação só nasce onde o EPI é exigido — escopo por câmera cruzado
  com a matriz de requisitos (#535).
- **Evidência completa**: frame inteiro + caixa da pessoa + veredito + confiança.
  Sem a caixa, o revisor não sabe de quem o sistema está falando.

### O que isto custa

Duas inferências por frame em vez de uma (detector de pessoa + classificador de
recorte). Medido no Orin: o estágio 1 já roda hoje, e o classificador é uma
cabeça leve sobre embedding — o custo marginal é pequeno, mas **não é zero** e
entra no orçamento das 28 câmeras.

E custa **latência de decisão**: com persistência de N frames, a violação nasce
N frames depois do instante. É deliberado. Um alerta 3 segundos mais tarde e
correto vale mais que um alerta instantâneo e errado.

### O que isto NÃO decide

- O valor de N por classe — sai da medição, não desta ADR.
- Qual arquitetura de classificador. Só a restrição de licença é decidida:
  **zero AGPL no caminho servido**.
- Se o classificador roda no edge ou na nuvem. As duas opções respeitam esta
  ADR.

---

## Alternativas consideradas

**Negação pura com limiar alto de presença.** "Se não detectei protetor
auditivo COM confiança alta, é ausência." Rejeitada: aumentar o limiar de
presença REDUZ o recall, então acusa mais conformes, não menos. A alternativa
piora exatamente o número que a motiva.

**Só classes de ausência, sem classificador.** Rejeitada: o propositor não
desenha caixa de ausência (medido acima), então a classe de ausência só cresce
com anotação humana, e três das cinco não sustentam a régua hoje.

**Só classificador, sem classes de ausência.** Rejeitada: `Uso incorreto de
mascara` já passa a régua a 61,9% e funciona hoje. Desligar o que funciona para
esperar o que ainda não existe é troca ruim.

---

## Relacionadas

- **ADR-0065** — presença é conformidade, ausência é violação (o *que*).
- **ADR-0066** — a caixa diz quem a desenhou (proveniência).
- **#537** — campanha de ausência: as metas que só a anotação humana move.
- **#535** — matriz de requisitos do Paulo: qual EPI é exigido onde.
- **#519** — escopo por câmera: o elo que já existe na nuvem.
