# ADR-0071 — O catálogo global não decide polaridade por todo mundo

- **Status:** Aceita
- **Data:** 2026-09-01
- **Decisor:** Vitor Emanuel
- **Contexto imediato:** ADR-0067 (violação nasce de julgamento positivo de ausência, com régua de
  precisão ≥ 50%) e a descoberta, na rodada de correção UX #2, de que a régua **não alcançava** as
  classes do catálogo global.

---

## Decisão

`public.module_classes.no_glasses.is_violation` passa de `TRUE` para **`NULL`**.

`NULL` aqui não é "esquecemos": é **"o catálogo não decide; o tenant decide"**. É o estado correto
para uma classe cuja polaridade depende de medição em campo — que é justamente o que a ADR-0067
exige e o que o catálogo global, por construção, não pode saber.

---

## O problema que isto resolve

A polaridade servida ao produto é a **união** de três conjuntos
(`AlertRepository._nomes_por_polaridade`): catálogo global por `class_name`, catálogo global por
`display_name`, e classes custom do tenant. **União não tem subtração.**

Consequência medida em 01/09, no tenant RVB: a régua da ADR-0067 reprovou `Sem Óculos` com
**30,4% de precisão em 23 julgamentos humanos** — acusa quem cumpre em 7 de cada 10 avisos. O
rebaixamento foi aplicado no catálogo **do tenant** (`yolo_classes.is_violation = NULL`) e **não
teve efeito**: `module_classes.no_glasses` tem `display_name = 'Sem Óculos'` com
`is_violation = TRUE`, e o TRUE global vence a união.

O sintoma que o cliente veria: os 23 eventos caíam **dentro** do filtro "Violações" enquanto o selo
da linha — que lê a polaridade do tenant — os pintava de cinza "não definida". **Tela
contradizendo tela**, e a tela errada era a que acusa.

### O efeito da decisão, medido antes e depois

| | violações | precisão das violações | em observação |
|---|---:|---:|---:|
| antes | 89 | 48,8% | 32 |
| depois | **66** | **66,7%** | 55 |

---

## Por que `NULL` no catálogo global, e não as alternativas

**Por que não deixar como estava.** Deixaria a contradição visível na tela na frente do cliente —
o filtro dizendo "violação" e o selo dizendo "não definida". Pior que o ajuste.

**Por que não corrigir só no tenant.** Já foi feito, e não funciona: a união não subtrai. Marcar
`Sem Óculos` como *conformidade* no tenant seria pior ainda — colocaria a classe no conjunto de
presença e faria "estar sem óculos" contar como conformidade. Trocaria uma afirmação falsa por
outra.

**Por que não fazer o tenant sobrepor o global agora.** É a correção de raiz e está registrada
abaixo como trabalho seguinte. Mudar a semântica da união é mudança de comportamento em toda leitura
de alerta, e não se faz isso na véspera de um embarque.

### O argumento que decidiu, e ele não é de prazo

O catálogo global afirmando "sem óculos = violação **para todo mundo**" é exatamente a asserção
global que a ADR-0067 nega: **polaridade é decisão por tenant, ancorada na precisão medida naquela
fábrica**. Um mesmo detector pode sustentar a régua num cliente e reprovar em outro — iluminação,
ângulo, EPI diferente. `NULL` é mais honesto que `TRUE` porque diz a verdade sobre o que o catálogo
global sabe: nada sobre a precisão em campo.

O raio de impacto foi **medido antes de decidir**, e é zero fora do RVB: nenhum outro tenant tem
alerta dessa classe (os demais são `admin`, `default`, `dev`, `e2e-fase-a-validation`). Mas o raio
zero foi o que tornou a decisão **barata**, não o que a tornou **certa**.

---

## Consequências

### Exigido
- Classe do catálogo global cuja polaridade dependa de medição em campo nasce **`NULL`**, não
  `TRUE`. `TRUE` no global só para o que é violação por definição em qualquer cliente.
- Toda promoção/rebaixamento continua saindo de `scripts/ops/calibracao_classes.py`, com o `n`
  visível (ADR-0067: precisão sem `n` não é medida).

### Proibido
- ⛔ Usar o catálogo global para contornar a régua da ADR-0067 — nem para promover, nem para
  rebaixar sem medição.
- ⛔ Marcar classe de ausência como conformidade no tenant para "tirá-la das violações": ela entra
  no conjunto de presença e passa a contar como conformidade, que é afirmação falsa.

### Sobrevivência a deploy
A migration 009 insere `module_classes` com `ON CONFLICT (module_code, class_name) DO NOTHING` —
**não sobrescreve** linha existente. Conferido antes de aplicar, precisamente porque a migration 127
mostrou (ADR-0069) que migration que re-roda a cada boot desfaz correção manual em silêncio.

### O que fica pendente
- **Tenant sobrepõe global** (a raiz): hoje a polaridade é união pura, sem precedência. O certo é a
  decisão do tenant vencer a do catálogo, porque a régua é por tenant. Rodada própria, com calma,
  **depois do embarque** — muda a semântica de toda leitura de alerta.
- Enquanto isso, rebaixar classe do catálogo global continua sendo ato de plataforma, não de tenant.

---

## Relacionadas
- **ADR-0065** — presença é conformidade, ausência é violação.
- **ADR-0067** — a régua de precisão, e o motivo de ela ser por tenant.
- **ADR-0069** — migration que apaga decisão humana a cada boot (a armadilha conferida aqui).
- `scripts/ops/calibracao_classes.py` · `scripts/ops/aplicar_calibracao_rvb.py`.
