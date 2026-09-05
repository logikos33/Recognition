# A/B de AUSÊNCIA — A · presença derivada × B · classe de ausência × C · sobreposição geométrica

- **holdout:** `<scratchpad>/ab/holdout/_annotations.coco.json` — 246 imagens no COCO, **246 avaliadas em TODAS as variantes**
- **modelo A (presença):** `<scratchpad>/ab/modelos/A_6ca25ee9.onnx` — dicionário: ['recognition', 'Botas', 'Luvas', 'Protetor auditivo', 'mascara', 'Óculos']
- **modelo B (presença+ausência):** `<scratchpad>/ab/modelos/V21_multiescala.onnx` — dicionário: ['recognition', 'Botas', 'Luvas', 'Protetor auditivo', 'Sem Luvas', 'Sem botas', 'Sem mascara', 'Sem protetor de ouvido', 'Sem Óculos', 'Uso incorreto de mascara', 'mascara', 'Óculos']
- **modelo C (parte do corpo + EPI):** `<scratchpad>/ab/modelos/C_b9243540.onnx` — dicionário: ['recognition', 'botas', 'luva', 'mao', 'mascara', 'mascara_incorreta', 'oculos', 'orelha', 'pessoa', 'protetor_auricular', 'regiao_boca_nariz', 'regiao_olhos', 'rosto']
- **critério de sobreposição da C:** IoMin (interseção ÷ área da caixa MENOR) ≥ **0.50**. Escolhido porque a relação de tamanho inverte de par para par — a luva é menor que a mão, o abafador é maior que a orelha — e IoU puro nunca cruza um limiar honesto quando uma caixa está contida na outra.
- **pares âncora→EPI da C:** `mao`→`('luva',)` ⇒ Sem Luvas; `regiao_boca_nariz`→`('mascara', 'mascara_incorreta')` ⇒ Sem mascara; `regiao_olhos`→`('oculos',)` ⇒ Sem Óculos; `orelha`→`('protetor_auricular',)` ⇒ Sem protetor de ouvido
- **estágio 1 (pessoa):** `/Users/vitoremanuel/Logikos-mutirao/modelos-servidos/yolox_nano_SERVIDO.onnx` — classe `person`, limiar 0.25, margem de recorte 25%×8% (a mesma do edge)
- **referência `V20B`:** `<scratchpad>/ab/modelos/B_1deadfb0.onnx` — dicionário: ['recognition', 'Botas', 'Luvas', 'Protetor auditivo', 'Sem Luvas', 'Sem botas', 'Sem mascara', 'Sem protetor de ouvido', 'Sem Óculos', 'Uso incorreto de mascara', 'mascara', 'Óculos'] — **fora do ranking**, entra só como régua do que o cliente já tem
- **referência `BASELINE`:** `<scratchpad>/ab/modelos/BASE_b3ae42b6.onnx` — dicionário: ['recognition', 'Capacete', 'Luvas', 'Sem Luvas', 'Óculos', 'Sem Óculos', 'Protetor auditivo', 'mascara', 'Sem protetor de ouvido', 'Sem mascara', 'Botas', 'Uso incorreto de mascara', 'Sem botas'] — **fora do ranking**, entra só como régua do que o cliente já tem
- **referência `SERVIDO`:** `<scratchpad>/ab/modelos/SERVIDO_46a30ed9.onnx` — dicionário: ['recognition', 'Capacete', 'Luvas', 'Sem Luvas', 'Óculos', 'Sem Óculos', 'Protetor auditivo', 'mascara', 'Sem protetor de ouvido', 'Sem mascara', 'Botas', 'Uso incorreto de mascara', 'Sem botas'] — **fora do ranking**, entra só como régua do que o cliente já tem
- **limiar aplicado:** 0.30 — **o MESMO para todas as variantes**
- **backend:** rfdetr_onnx

## Guarda de vazamento holdout×treino

Passou: 0 colisão de nome, 0 colisão de conteúdo. 246/246 imagens do holdout conferidas também por sha256; 0 imagens de treino hasheadas.

## Procedência do gabarito

Fonte: `public.holdout_verdicts` (migration 135), tenant `63c219d8-fbef-4f3c-a7c9-058c742482e2`, módulo `epi` — **644 julgamentos** sobre 246 imagens. Não é anotação de treino e não tem geometria: é a resposta por imagem×classe.

**`nao_sei` NÃO virou `nao`.** Ele sai do numerador E do denominador da classe — a imagem simplesmente não é avaliada ali. Convertê-lo em `nao` contaria como falso positivo toda acusação que talvez estivesse certa, que é inventar gabarito. A coluna `fora` abaixo é o preço declarado disso.

| classe | sim (n de reais) | nao | nao_sei | nunca julgada | **fora do denominador** | avaliadas |
|---|---:|---:|---:|---:|---:|---:|
| Sem Luvas | 69 | 53 | 124 | 0 | 124 | 122 |
| Sem mascara | 47 | 66 | 132 | 1 | 133 | 113 |
| Sem Óculos | 0 | 49 | 2 | 195 | 197 | 49 |
| Sem protetor de ouvido | 0 | 49 | 2 | 195 | 197 | 49 |
| Uso incorreto de mascara | 0 | 49 | 2 | 195 | 197 | 49 |

Resolução do `class_id`: **os dois namespaces resolvidos no banco** — `class_id < 100000` → `module_classes.class_id` (catálogo global), `>= 100000` → `yolo_classes.id` do tenant. Ler o namespace errado não daria erro: `5` no catálogo é **Sem Luvas**, e `5` no espaço do tenant é `Protetor auricular` — uma classe de PRESENÇA, arquivada. O de-para sai da query, nunca de tabela digitada no script.

## Como ler a coluna abstenção

Abstenção é a imagem em que a variante **não tinha como falar** — a A quando o estágio 1 não achou pessoa, a C quando a parte do corpo âncora não foi detectada (inclusive quando o EPI apareceu e a parte não: falha do detector de parte). Ela **não entra em TP nem em FP**, porque não houve acusação para julgar. Continua contando FN quando a ausência era real — não pegar por cegueira também é não pegar — e `FN por abstenção` separa o quanto da perda é 'não viu' em vez de 'viu e julgou errado'. A variante B não tem abstenção: o silêncio dela é indistinguível de inocentar.

## Por classe de ausência (limiar 0.30)

### Sem Luvas

| variante | TP | FP | FN | precisão | recall | abstenção | n |
|---|---:|---:|---:|---:|---:|---:|---|
| A · presença derivada | 68 | 39 | 1 | 63.6% | 98.6% | 15 (12.3%) | 107 acus. / 69 reais |
| B · classe de ausência | 2 | 2 | 67 | 50.0% | 2.9% | 0 (0.0%) | 4 acus. / 69 reais |
| C · sobreposição geométrica | 0 | 4 | 69 | 0.0% | 0.0% | 118 (96.7%) | 4 acus. / 69 reais |
| V20B | 0 | 0 | 69 | — | 0.0% | 0 (0.0%) | 0 acus. / 69 reais |
| BASELINE | 0 | 0 | 69 | — | 0.0% | 0 (0.0%) | 0 acus. / 69 reais |
| SERVIDO | 0 | 0 | 69 | — | 0.0% | 0 (0.0%) | 0 acus. / 69 reais |

- **controle nulo (acusar SEMPRE):** precisão 56.6% (69 reais em 122 avaliadas), recall 100%. É o piso: quem não superar isto não acrescentou informação nenhuma à decisão, por mais que passe na régua de 50%.
- ⛔ **A: acusou 100% do que julgou (107/107).** Esta precisão É a prevalência da violação entre os quadros que ela julgou — aritmeticamente, não por semelhança. A variante não distinguiu nada; o número é do gabarito, não do modelo.
- A: **sustenta acusação** (precisão 63.6% ≥ 50%, n=107 ≥ 30).
  - 1 de 1 FN vieram de ABSTENÇÃO (não viu a âncora), não de julgamento errado.
- ⚠️ **B: precisão 50.0% não supera o controle nulo (56.6%).**
- B: **n insuficiente** (n=4 < 30) — precisão sem n não é medida (ADR-0067).
- ⛔ **C: acusou 100% do que julgou (4/4).** Esta precisão É a prevalência da violação entre os quadros que ela julgou — aritmeticamente, não por semelhança. A variante não distinguiu nada; o número é do gabarito, não do modelo.
- C: **n insuficiente** (n=4 < 30) — precisão sem n não é medida (ADR-0067).
  - 69 de 69 FN vieram de ABSTENÇÃO (não viu a âncora), não de julgamento errado.
- V20B: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- BASELINE: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- SERVIDO: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- **veredito:** A vence — única que sustenta a régua

### Sem mascara

| variante | TP | FP | FN | precisão | recall | abstenção | n |
|---|---:|---:|---:|---:|---:|---:|---|
| A · presença derivada | 46 | 52 | 1 | 46.9% | 97.9% | 15 (13.3%) | 98 acus. / 47 reais |
| B · classe de ausência | 0 | 0 | 47 | — | 0.0% | 0 (0.0%) | 0 acus. / 47 reais |
| C · sobreposição geométrica | 4 | 11 | 43 | 26.7% | 8.5% | 98 (86.7%) | 15 acus. / 47 reais |
| V20B | 3 | 0 | 44 | 100.0% | 6.4% | 0 (0.0%) | 3 acus. / 47 reais |
| BASELINE | 7 | 0 | 40 | 100.0% | 14.9% | 0 (0.0%) | 7 acus. / 47 reais |
| SERVIDO | 0 | 0 | 47 | — | 0.0% | 0 (0.0%) | 0 acus. / 47 reais |

- **controle nulo (acusar SEMPRE):** precisão 41.6% (47 reais em 113 avaliadas), recall 100%. É o piso: quem não superar isto não acrescentou informação nenhuma à decisão, por mais que passe na régua de 50%.
- ⛔ **A: acusou 100% do que julgou (98/98).** Esta precisão É a prevalência da violação entre os quadros que ela julgou — aritmeticamente, não por semelhança. A variante não distinguiu nada; o número é do gabarito, não do modelo.
- A: **NÃO sustenta acusação** — precisão 46.9% < 50% (ADR-0067).
  - 1 de 1 FN vieram de ABSTENÇÃO (não viu a âncora), não de julgamento errado.
- B: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- ⛔ **C: acusou 100% do que julgou (15/15).** Esta precisão É a prevalência da violação entre os quadros que ela julgou — aritmeticamente, não por semelhança. A variante não distinguiu nada; o número é do gabarito, não do modelo.
- C: **n insuficiente** (n=15 < 30) — precisão sem n não é medida (ADR-0067).
  - 43 de 43 FN vieram de ABSTENÇÃO (não viu a âncora), não de julgamento errado.
- V20B: **n insuficiente** (n=3 < 30) — precisão sem n não é medida (ADR-0067).
- BASELINE: **n insuficiente** (n=7 < 30) — precisão sem n não é medida (ADR-0067).
- SERVIDO: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- **veredito:** sem veredito — nenhuma sustenta a régua

### Sem Óculos

| variante | TP | FP | FN | precisão | recall | abstenção | n |
|---|---:|---:|---:|---:|---:|---:|---|
| A · presença derivada | 0 | 35 | 0 | 0.0% | — | 14 (28.6%) | 35 acus. / 0 reais |
| B · classe de ausência | 0 | 0 | 0 | — | — | 0 (0.0%) | 0 acus. / 0 reais |
| C · sobreposição geométrica | 0 | 0 | 0 | — | — | 49 (100.0%) | 0 acus. / 0 reais |
| V20B | 0 | 0 | 0 | — | — | 0 (0.0%) | 0 acus. / 0 reais |
| BASELINE | 0 | 0 | 0 | — | — | 0 (0.0%) | 0 acus. / 0 reais |
| SERVIDO | 0 | 0 | 0 | — | — | 0 (0.0%) | 0 acus. / 0 reais |

- ⛔ **NÃO CONCLUSIVA — o gabarito não tem nenhum `sim` para esta classe.** Sem um positivo real não há recall para medir, e a precisão só pode dar 0%: toda acusação cai contra um denominador de zero verdades. Isso mede o gabarito, não o modelo. Nenhum veredito é emitido aqui — e a ausência dele é o resultado.

- ⛔ **A: acusou 100% do que julgou (35/35).** Esta precisão É a prevalência da violação entre os quadros que ela julgou — aritmeticamente, não por semelhança. A variante não distinguiu nada; o número é do gabarito, não do modelo.
- A: **NÃO sustenta acusação** — precisão 0.0% < 50% (ADR-0067).
- B: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- C: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- V20B: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- BASELINE: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- SERVIDO: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- **veredito:** sem veredito — nenhuma sustenta a régua

### Sem protetor de ouvido

| variante | TP | FP | FN | precisão | recall | abstenção | n |
|---|---:|---:|---:|---:|---:|---:|---|
| A · presença derivada | 0 | 35 | 0 | 0.0% | — | 14 (28.6%) | 35 acus. / 0 reais |
| B · classe de ausência | 0 | 3 | 0 | 0.0% | — | 0 (0.0%) | 3 acus. / 0 reais |
| C · sobreposição geométrica | 0 | 22 | 0 | 0.0% | — | 27 (55.1%) | 22 acus. / 0 reais |
| V20B | 0 | 1 | 0 | 0.0% | — | 0 (0.0%) | 1 acus. / 0 reais |
| BASELINE | 0 | 0 | 0 | — | — | 0 (0.0%) | 0 acus. / 0 reais |
| SERVIDO | 0 | 0 | 0 | — | — | 0 (0.0%) | 0 acus. / 0 reais |

- ⛔ **NÃO CONCLUSIVA — o gabarito não tem nenhum `sim` para esta classe.** Sem um positivo real não há recall para medir, e a precisão só pode dar 0%: toda acusação cai contra um denominador de zero verdades. Isso mede o gabarito, não o modelo. Nenhum veredito é emitido aqui — e a ausência dele é o resultado.

- ⛔ **A: acusou 100% do que julgou (35/35).** Esta precisão É a prevalência da violação entre os quadros que ela julgou — aritmeticamente, não por semelhança. A variante não distinguiu nada; o número é do gabarito, não do modelo.
- A: **NÃO sustenta acusação** — precisão 0.0% < 50% (ADR-0067).
- ⚠️ **B: precisão 0.0% não supera o controle nulo (0.0%).**
- B: **n insuficiente** (n=3 < 30) — precisão sem n não é medida (ADR-0067).
- ⛔ **C: acusou 100% do que julgou (22/22).** Esta precisão É a prevalência da violação entre os quadros que ela julgou — aritmeticamente, não por semelhança. A variante não distinguiu nada; o número é do gabarito, não do modelo.
- C: **n insuficiente** (n=22 < 30) — precisão sem n não é medida (ADR-0067).
- ⚠️ **V20B: precisão 0.0% não supera o controle nulo (0.0%).**
- V20B: **n insuficiente** (n=1 < 30) — precisão sem n não é medida (ADR-0067).
- BASELINE: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- SERVIDO: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- **veredito:** sem veredito — nenhuma sustenta a régua

### Uso incorreto de mascara

| variante | TP | FP | FN | precisão | recall | abstenção | n |
|---|---:|---:|---:|---:|---:|---:|---|
| A · presença derivada | 0 | 0 | 0 | — | — | 49 (100.0%) | 0 acus. / 0 reais |
| B · classe de ausência | 0 | 0 | 0 | — | — | 0 (0.0%) | 0 acus. / 0 reais |
| C · sobreposição geométrica | 0 | 0 | 0 | — | — | 49 (100.0%) | 0 acus. / 0 reais |
| V20B | 0 | 0 | 0 | — | — | 0 (0.0%) | 0 acus. / 0 reais |
| BASELINE | 0 | 0 | 0 | — | — | 0 (0.0%) | 0 acus. / 0 reais |
| SERVIDO | 0 | 0 | 0 | — | — | 0 (0.0%) | 0 acus. / 0 reais |

- ⛔ **NÃO CONCLUSIVA — o gabarito não tem nenhum `sim` para esta classe.** Sem um positivo real não há recall para medir, e a precisão só pode dar 0%: toda acusação cai contra um denominador de zero verdades. Isso mede o gabarito, não o modelo. Nenhum veredito é emitido aqui — e a ausência dele é o resultado.

- A: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- B: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- C: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- V20B: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- BASELINE: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- SERVIDO: **n insuficiente** (n=0 < 30) — precisão sem n não é medida (ADR-0067).
- **veredito:** sem veredito — n insuficiente (A=0, B=0, C=0)

## Varredura de limiares de confiança (todas as variantes)

A regra de justiça é limiar ÚNICO. A varredura está aqui para a escolha ficar explícita — não para cada variante escolher o seu.

| limiar | classe | A precisão/recall (n) | B precisão/recall (n) | C precisão/recall (n) | V20B precisão/recall (n) | BASELINE precisão/recall (n) | SERVIDO precisão/recall (n) |
|---:|---|---|---|---|---|---|---|
| 0.15 | Sem Luvas | 63.6% / 98.6% (107) | 45.5% / 7.2% (11) | 12.5% / 1.4% (8) | — / 0.0% (0) | 100.0% / 7.2% (5) | 100.0% / 8.7% (6) |
| 0.15 | Sem mascara | 46.9% / 97.9% (98) | 100.0% / 14.9% (7) | 40.7% / 23.4% (27) | 91.7% / 23.4% (12) | 100.0% / 40.4% (19) | 100.0% / 19.1% (9) |
| 0.15 | Sem Óculos | 0.0% / — (35) | — / — (0) | — / — (0) | — / — (0) | 0.0% / — (1) | — / — (0) |
| 0.15 | Sem protetor de ouvido | 0.0% / — (35) | 0.0% / — (5) | 0.0% / — (41) | 0.0% / — (7) | 0.0% / — (2) | — / — (0) |
| 0.15 | Uso incorreto de mascara | — / — (0) | 0.0% / — (1) | — / — (0) | 0.0% / — (7) | 0.0% / — (14) | 0.0% / — (12) |
| 0.20 | Sem Luvas | 63.6% / 98.6% (107) | 40.0% / 2.9% (5) | 0.0% / 0.0% (7) | — / 0.0% (0) | 100.0% / 5.8% (4) | 100.0% / 1.4% (1) |
| 0.20 | Sem mascara | 46.9% / 97.9% (98) | 100.0% / 4.3% (2) | 36.4% / 17.0% (22) | 100.0% / 14.9% (7) | 100.0% / 29.8% (14) | 100.0% / 6.4% (3) |
| 0.20 | Sem Óculos | 0.0% / — (35) | — / — (0) | — / — (0) | — / — (0) | 0.0% / — (1) | — / — (0) |
| 0.20 | Sem protetor de ouvido | 0.0% / — (35) | 0.0% / — (4) | 0.0% / — (37) | 0.0% / — (3) | — / — (0) | — / — (0) |
| 0.20 | Uso incorreto de mascara | — / — (0) | — / — (0) | — / — (0) | 0.0% / — (2) | 0.0% / — (6) | 0.0% / — (5) |
| 0.25 | Sem Luvas | 63.6% / 98.6% (107) | 50.0% / 2.9% (4) | 0.0% / 0.0% (5) | — / 0.0% (0) | — / 0.0% (0) | — / 0.0% (0) |
| 0.25 | Sem mascara | 46.9% / 97.9% (98) | 100.0% / 4.3% (2) | 26.3% / 10.6% (19) | 100.0% / 6.4% (3) | 100.0% / 21.3% (10) | 100.0% / 4.3% (2) |
| 0.25 | Sem Óculos | 0.0% / — (35) | — / — (0) | — / — (0) | — / — (0) | — / — (0) | — / — (0) |
| 0.25 | Sem protetor de ouvido | 0.0% / — (35) | 0.0% / — (3) | 0.0% / — (28) | 0.0% / — (1) | — / — (0) | — / — (0) |
| 0.25 | Uso incorreto de mascara | — / — (0) | — / — (0) | — / — (0) | 0.0% / — (1) | 0.0% / — (1) | 0.0% / — (2) |
| 0.30 | Sem Luvas | 63.6% / 98.6% (107) | 50.0% / 2.9% (4) | 0.0% / 0.0% (4) | — / 0.0% (0) | — / 0.0% (0) | — / 0.0% (0) |
| 0.30 | Sem mascara | 46.9% / 97.9% (98) | — / 0.0% (0) | 26.7% / 8.5% (15) | 100.0% / 6.4% (3) | 100.0% / 14.9% (7) | — / 0.0% (0) |
| 0.30 | Sem Óculos | 0.0% / — (35) | — / — (0) | — / — (0) | — / — (0) | — / — (0) | — / — (0) |
| 0.30 | Sem protetor de ouvido | 0.0% / — (35) | 0.0% / — (3) | 0.0% / — (22) | 0.0% / — (1) | — / — (0) | — / — (0) |
| 0.30 | Uso incorreto de mascara | — / — (0) | — / — (0) | — / — (0) | — / — (0) | — / — (0) | — / — (0) |
| 0.35 | Sem Luvas | 63.6% / 98.6% (107) | 50.0% / 2.9% (4) | 0.0% / 0.0% (4) | — / 0.0% (0) | — / 0.0% (0) | — / 0.0% (0) |
| 0.35 | Sem mascara | 46.9% / 97.9% (98) | — / 0.0% (0) | 25.0% / 6.4% (12) | 100.0% / 2.1% (1) | — / 0.0% (0) | — / 0.0% (0) |
| 0.35 | Sem Óculos | 0.0% / — (35) | — / — (0) | — / — (0) | — / — (0) | — / — (0) | — / — (0) |
| 0.35 | Sem protetor de ouvido | 0.0% / — (35) | 0.0% / — (2) | 0.0% / — (14) | — / — (0) | — / — (0) | — / — (0) |
| 0.35 | Uso incorreto de mascara | — / — (0) | — / — (0) | — / — (0) | — / — (0) | — / — (0) | — / — (0) |
| 0.40 | Sem Luvas | 63.6% / 98.6% (107) | 0.0% / 0.0% (2) | 0.0% / 0.0% (2) | — / 0.0% (0) | — / 0.0% (0) | — / 0.0% (0) |
| 0.40 | Sem mascara | 46.9% / 97.9% (98) | — / 0.0% (0) | 30.0% / 6.4% (10) | — / 0.0% (0) | — / 0.0% (0) | — / 0.0% (0) |
| 0.40 | Sem Óculos | 0.0% / — (35) | — / — (0) | — / — (0) | — / — (0) | — / — (0) | — / — (0) |
| 0.40 | Sem protetor de ouvido | 0.0% / — (35) | 0.0% / — (1) | 0.0% / — (5) | — / — (0) | — / — (0) | — / — (0) |
| 0.40 | Uso incorreto de mascara | — / — (0) | — / — (0) | — / — (0) | — / — (0) | — / — (0) | — / — (0) |
| 0.50 | Sem Luvas | 63.6% / 98.6% (107) | 0.0% / 0.0% (1) | 0.0% / 0.0% (2) | — / 0.0% (0) | — / 0.0% (0) | — / 0.0% (0) |
| 0.50 | Sem mascara | 46.9% / 97.9% (98) | — / 0.0% (0) | 25.0% / 4.3% (8) | — / 0.0% (0) | — / 0.0% (0) | — / 0.0% (0) |
| 0.50 | Sem Óculos | 0.0% / — (35) | — / — (0) | — / — (0) | — / — (0) | — / — (0) | — / — (0) |
| 0.50 | Sem protetor de ouvido | 0.0% / — (35) | — / — (0) | 0.0% / — (1) | — / — (0) | — / — (0) | — / — (0) |
| 0.50 | Uso incorreto de mascara | — / — (0) | — / — (0) | — / — (0) | — / — (0) | — / — (0) | — / — (0) |

## Varredura do limiar de SOBREPOSIÇÃO da variante C (confiança fixa em 0.30)

O critério geométrico é um segundo botão, e um botão escolhido em silêncio é um número escondido. Aqui está a sensibilidade dele.

| IoMin | classe | TP | FP | FN | precisão | recall |
|---:|---|---:|---:|---:|---:|---:|
| 0.10 | Sem Luvas | 0 | 4 | 69 | 0.0% | 0.0% |
| 0.10 | Sem mascara | 4 | 11 | 43 | 26.7% | 8.5% |
| 0.10 | Sem Óculos | 0 | 0 | 0 | — | — |
| 0.10 | Sem protetor de ouvido | 0 | 22 | 0 | 0.0% | — |
| 0.25 | Sem Luvas | 0 | 4 | 69 | 0.0% | 0.0% |
| 0.25 | Sem mascara | 4 | 11 | 43 | 26.7% | 8.5% |
| 0.25 | Sem Óculos | 0 | 0 | 0 | — | — |
| 0.25 | Sem protetor de ouvido | 0 | 22 | 0 | 0.0% | — |
| 0.50 | Sem Luvas | 0 | 4 | 69 | 0.0% | 0.0% |
| 0.50 | Sem mascara | 4 | 11 | 43 | 26.7% | 8.5% |
| 0.50 | Sem Óculos | 0 | 0 | 0 | — | — |
| 0.50 | Sem protetor de ouvido | 0 | 22 | 0 | 0.0% | — |
| 0.75 | Sem Luvas | 0 | 4 | 69 | 0.0% | 0.0% |
| 0.75 | Sem mascara | 4 | 11 | 43 | 26.7% | 8.5% |
| 0.75 | Sem Óculos | 0 | 0 | 0 | — | — |
| 0.75 | Sem protetor de ouvido | 0 | 22 | 0 | 0.0% | — |
| 0.90 | Sem Luvas | 0 | 4 | 69 | 0.0% | 0.0% |
| 0.90 | Sem mascara | 4 | 11 | 43 | 26.7% | 8.5% |
| 0.90 | Sem Óculos | 0 | 0 | 0 | — | — |
| 0.90 | Sem protetor de ouvido | 0 | 22 | 0 | 0.0% | — |

## Veredito geral

**A vence (A=1, B=0, C=0)**

Empate técnico (< 5% de diferença em precisão e recall) conta como empate, e empate vence a mais simples, na ordem declarada A < B < C: A reusa o estágio 1 já servido; B só acrescenta classes ao que já se anota; C exige uma taxonomia nova de partes do corpo.

## ⚠️ Aviso das réguas — o que NÃO pode ser comparado

**Não compare o mAP do `val` de uma variante com o da outra.** A é medida sobre 5 classes, B sobre 10, C sobre 10 de outra taxonomia — e mAP é média POR CLASSE: tirar classes difíceis do dicionário sobe o número sem que o detector melhore em nada. Um ranking feito assim premiaria a variante com menos classes. **Só este holdout compara**, porque é a mesma prova, as mesmas imagens e o mesmo gabarito para as três.

## O que este relatório NÃO mediu

- **Geometria da acusação.** A comparação é por decisão (imagem × classe), não por caixa. Uma imagem com três pessoas conta TP mesmo se a variante acusou a pessoa errada. Vale inclusive para a C, que casa PARES corretamente mas é pontuada por imagem.
- **Botas.** Não existe classe `Sem Botas` no gabarito; sem gabarito não há o que julgar, então ela ficou fora — não é omissão, é falta de verdade. A C detecta botas e mesmo assim não é pontuada nelas.
- **`Uso incorreto de mascara` por A e por C.** Nenhuma das duas tem mecanismo: silêncio não distingue 'sem máscara' de 'máscara no queixo', e máscara sobreposta ao rosto também não. As duas se ABSTÊM — que é diferente de errar.
- **Persistência temporal e zona.** A ADR-0067 exige as duas antes de qualquer acusação virar alerta. Aqui cada frame é julgado sozinho.
- **A caixa espúria minúscula da C.** Um falso EPI de poucos pixels dentro da âncora pontua IoMin 1,0 e silencia a acusação. Erra para o lado de não acusar; um piso de área resolveria, se a medição mostrar que acontece.
- **Custo e latência.** A e C custam mais que B por frame; isso não entra na conta.
- **O efeito do NMS por limiar.** A inferência rodou uma vez a 0.05 e a varredura decidiu em cima dela; caixa suprimida na coleta não reaparece num limiar mais alto. Vale igual para todas, mas não é o mesmo que reinferir.
- **O que o anotador não desenhou.** Imagem sem anotação `Sem X` é tratada como 'não havia ausência'. Ausência real e não anotada aparece como FP da variante.
- **A viabilidade da conversão das anotações para a taxonomia C.** Isso é medido fora daqui; se a conversão não se sustentar, a C não é usada — e nada nesta régua muda por causa disso.
- **0 imagem(ns)** que falharam na leitura — fora do universo de TODAS as variantes.
- **A legitimidade da variante A em produção.** A ADR-0067 já a proíbe. Este número mede o preço dela, não a autoriza.
- **Acurácia sob quantização.** Isto roda em FP32 no `onnxruntime` — o MESMO runtime e a MESMA precisão do caminho servido hoje (`onnx_rfdetr.py`, providers CUDA/CPU, sem TensorRT), então o número é o do produto atual. Ele NÃO é transferível para um edge INT8/TensorRT: a quantização pode mexer alguns pontos percentuais, e ordem decidida por 2 pp não sobrevive a isso. Promover ao edge quantizado exige remedir no artefato real.
