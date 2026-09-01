# ADR-0068 — "Sem o EPI" e "usar errado" são fatos diferentes

- **Status:** Aceita
- **Data:** 2026-08-31
- **Decisor:** Vitor Emanuel (revisão do front novo, 31/08)
- **Contexto imediato:** ADR-0065 define polaridade (presença × ausência);
  ADR-0067 define de onde uma violação pode nascer. Faltava dizer o que cada
  classe de máscara **afirma sobre o mundo** — e o acervo estava aprendendo com
  a fronteira borrada.

---

## Decisão

Três fatos distintos, três classes, uma definição cada. A definição é normativa:
vale para o catálogo, para quem anota, para o treino e para a microcopy da tela.

| classe | o que afirma | como se reconhece |
|---|---|---|
| `mascara` | **há máscara, no lugar certo** | cobre boca **e** nariz |
| `Sem mascara` | **não há máscara no rosto** | nenhuma máscara visível na pessoa |
| `Uso incorreto de mascara` | **há máscara, fora de posição** | no queixo, no pescoço, ou com o nariz de fora |

**A fronteira que importa:** `Sem mascara` exige a **ausência do objeto**. Se a
máscara está no quadro — pendurada no queixo, no pescoço, abaixo do nariz — o
fato é `Uso incorreto`, nunca `Sem mascara`. Uma pessoa com a máscara no queixo
**tem** máscara; dizer que ela está "sem máscara" é uma afirmação falsa sobre o
mundo, e o modelo que aprende isso passa a errar as duas classes.

O mesmo molde vale para qualquer EPI com uso posicional (óculos na testa,
protetor auricular pendurado): **ausência do objeto** ≠ **objeto fora de
posição**. Ausência é `Sem <epi>`; fora de posição é `Uso incorreto de <epi>`.

**`não visível` continua sendo abstenção** (ADR-0067) e não vira nenhuma das
três. Pessoa de costas não tem veredito de máscara.

---

## Por que isto virou ADR agora

Na revisão de 31/08 o Vitor mandou dois prints. O de `Uso incorreto de mascara`
estava **correto** — o sistema acertou o fato e a etiqueta. O problema não era
esse caso: era não existir, escrito em lugar nenhum, a regra que o separa de
`Sem mascara`. Sem a regra escrita, a fronteira é opinião de quem anota naquele
dia, e o acervo fica com duas classes que se contradizem.

### O que a medição diz sobre as duas (31/08, vereditos reais em produção)

| classe | caminho | julgados | acertos | precisão | régua ADR-0067 |
|---|---|---:|---:|---:|---|
| `Sem mascara` | classificador de recorte | 33 | 21 | **63,6%** | ✅ passa |
| `Uso incorreto de mascara` | classe de ausência do detector | 10 | 2 | **20,0%** | ⛔ reprova (n=10) |

Isto **inverte** o que a ADR-0067 registrou em 25/08 a partir do dataset, e a
inversão é a razão de a fronteira precisar de definição escrita:

- `Sem mascara` valia **0,0%** pelo caminho 1 (n=6). Pelo caminho 2 vai a
  **63,6%**. O classificador de recorte, que a ADR-0067 propôs justamente para
  isso, funciona.
- `Uso incorreto de mascara` passava com **61,9%** no dataset e caiu para
  **20,0%** em campo. Uma classe que depende de posição do objeto é
  exatamente a que mais sofre com fronteira mal definida — e é a que despencou.

Não afirmamos que a fronteira borrada **causou** a queda: o `n` de 10 não
sustenta essa conclusão, e há outras explicações (campo virgem é mais difícil
que dataset curado). A definição entra porque é barata e porque sem ela não há
como nem investigar.

---

## Consequências

### Exigido
- O catálogo do tenant carrega a definição junto do nome — quem anota lê a
  regra na hora de anotar, não num documento que ninguém abre.
- A tela que mostra o evento diz o fato em língua de gente: "está sem máscara"
  × "está com a máscara fora de posição". ⛔ Nunca o nome cru da classe.
- Anotação que marque `Sem mascara` com máscara visível no quadro é **erro de
  anotação** e entra na revisão, não no treino.

### Proibido
- ⛔ Tratar `Uso incorreto` como um grau menor de `Sem mascara`. Não é uma
  escala: são fatos distintos, e viram ações distintas do supervisor.
- ⛔ Colapsar as duas em "máscara irregular" para simplificar a tela. O
  supervisor age diferente em cada caso, e o modelo precisa da separação.

### O que isto NÃO decide
- Se `Uso incorreto de mascara` continua alertando — isso é a régua da
  ADR-0067, medida por `scripts/ops/calibracao_classes.py`, e hoje ela reprova.
- O `n` mínimo para reavaliar a classe. Sai da medição.

---

## Relacionadas

- **ADR-0065** — presença é conformidade, ausência é violação.
- **ADR-0067** — violação nasce de julgamento positivo de ausência (a régua).
- `scripts/ops/calibracao_classes.py` — a régua, reexecutável, com o `n` visível.
- `infra/migrations/125_yolo_classes_is_violation.sql` — polaridade por linha.
