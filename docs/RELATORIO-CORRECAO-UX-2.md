# Relatório da rodada de correção UX #2 (31/08/2026)

> Origem: 2ª revisão do Vitor no front novo, 12 achados + adendo. Formato:
> **achado → causa medida → conserto → prova**. Cliente embarca **quarta 02/09**.
> Regra herdada da rodada #1 e mantida: nada de conserto sem medir a causa na fonte primeiro.

---

## A TESE DA RODADA: "o sistema afirma mais do que sabe"

A rodada #1 achou telas que diziam **vazio** com o dado existindo. Esta achou o contrário, e é
pior: telas que **afirmam com confiança** o que o sistema não sabe. Três formas do mesmo defeito:

| onde | o que a tela afirma | o que o sistema realmente sabe |
|---|---|---|
| Alerta de EPI | "violação" | a classe reprova a régua de precisão desde 25/08 |
| Selo de confiança | "100%" | acerta 58% das vezes nessa faixa |
| Dashboard | "29 câmeras online" | 19 cadastradas e ativas; **online ninguém mede** |

O elo é o mesmo da família `0,0%` e `needs_human` da rodada #1 — **zero é uma afirmação** —, agora
na direção oposta: **100% também é uma afirmação**. E é a mais cara, porque o operador confia nela.

---

## Bloco A · Credibilidade do modelo

### A1 · Falso positivo acusando quem cumpre

**Causa medida — a decisão já existia e o código nunca a cumpriu.** A `ADR-0067` (Aceita,
25/08, decisor Vitor) fixa a régua: classe de ausência só gera violação enquanto sustentar
**precisão ≥ 50% em campo virgem**. E já nomeava o réu, textualmente:

> "`Sem protetor de ouvido` está em 40% e **ainda não passa** — fica fora até passar."

Não era, portanto, um limiar a recalibrar: era uma ADR aceita, não aplicada. Medição de 31/08
sobre os **vereditos humanos reais do Vitor em produção** (não sobre dataset):

| caminho | classe | julgados | acertos | precisão | régua |
|---|---|---:|---:|---:|---|
| 2 · classificador de recorte | Sem Luvas | 33 | 23 | **69,7%** | ✅ passa |
| 2 · classificador de recorte | Sem mascara | 33 | 21 | **63,6%** | ✅ passa |
| 2 · classificador de recorte | Sem Óculos | 23 | 7 | **30,4%** | ⛔ reprova |
| 1 · classe de ausência | Sem protetor de ouvido | 22 | 6 | **27,3%** | ⛔ reprova |
| 1 · classe de ausência | Uso incorreto de mascara | 10 | 2 | **20,0%** | ⛔ reprova (n=10) |

Nenhum limiar salva `Sem protetor de ouvido`: a precisão por faixa vai de 25% a 33% e só chega a
100% sobre **1 alerta** — sorte, não evidência, e a ADR-0067 é explícita que "precisão sem `n` não
é medida".

**Dois resultados que invertem o que se esperava.** O caminho 2 que a ADR propôs **funciona**:
`Sem mascara` valia 0,0% pelo detector e vale 63,6% pelo classificador de recorte. Já
`Uso incorreto de mascara`, que passava com folga (61,9%) no dataset, **despencou para 20% em
campo** — a precisão do acervo curado não transferiu para o pool real.

**Conserto:** `scripts/ops/calibracao_classes.py` — a régua reexecutável, com o `n` visível
(commit `65afe3bf`). ⛔ Deliberadamente **não** grava nada: rebaixar classe é ato humano.

**🔴 Lição de método registrada:** medimos a mesma classe com minutos de intervalo e deu 4/9 e
depois 6/16 — o operador julga a fila o tempo todo. **Chumbar um limiar a partir dessa foto é
calibrar balança com o caminhão em cima.** Por isso a decisão vive numa linha de dado
(`yolo_classes.is_violation`), nunca numa constante no código.

### A1 (ampliado) · A confiança exibida é ornamental

O Vitor mandou eventos de **98%, 99% e 100%** marcados por ele como falso positivo, e perguntou se
o número exibido é mesmo o que decide. Medido:

| confiança exibida | n | acertos | precisão REAL |
|---|---:|---:|---:|
| **100%** | 36 | 21 | **58,3%** |
| 99% | 22 | 13 | 59,1% |
| 97–98% | 17 | 11 | 64,7% |
| 95–96% | 7 | 4 | 57,1% |
| <95% | 7 | 2 | 28,6% |

A precisão é **plana (~58–65%)** em toda a faixa onde vive quase todo alerta. Conferi também que
`alerts.confidence` e `violations[].confidence` são **o mesmo valor** (zero divergências): não é
bug de exibição — o número simplesmente **não carrega informação de acerto**. No detector é pior
ainda: 21–33%, também plano.

### A1 (ampliado) · Rebaixar a classe não conserta o que o cliente já vê

`event_kind` (`alert_repository.py:364-393`) é **binário**: `CASE WHEN compliance THEN 'compliance'
ELSE 'violation'`. Classe de polaridade **indecisa cai em `violation`**. O gate de criação já está
correto (`_has_violation`, `inference.py:300-341`, não alerta para classe indecisa), mas a
**leitura mente**: na quarta o cliente ainda veria 56 alertas de `Sem Luvas`/`Sem Óculos`/`Óculos`
— classes que **nem existem no catálogo do tenant** — rotulados como violação. Daí o terceiro
valor `observacao`: um evento de classe indecisa não é violação nem conformidade.

### A2 · "Sem máscara" ≠ "uso incorreto" — ADR-0068

O print que o Vitor mandou de `Uso incorreto de mascara` estava **correto**. O defeito não era o
caso: era não existir, escrito em lugar nenhum, a regra que separa os dois fatos. Sem regra
escrita, a fronteira é opinião de quem anota naquele dia. Escrita em `ADR-0068` (commit
`abee0f0a`): `Sem mascara` exige a **ausência do objeto**; máscara no queixo/pescoço/nariz de fora
é **uso incorreto** — a pessoa *tem* máscara, e dizer que está sem é afirmação falsa sobre o mundo.

### Procedência dos 89 alertas de 25/08 — ressalva honesta

Os únicos alertas numa janela recente têm `origem=classificador_recorte_v1` e **89/89 com evidência
real do NVR** (⛔ não é mock). Mas o **código que os gravou não existe no repo** — só o módulo de
treino. Foram inseridos por experimento externo. Logo a calibração do caminho 2 vale sobre um
**lote experimental**, não sobre o pipeline servido; em produção o que acusa é só o caminho 1.
E **88 dos 89** carregam `bbox_unidade=recorte_da_pessoa_sem_coordenada_no_frame_original`: o
revisor vê o recorte e não sabe onde a pessoa está no frame, contra a exigência de evidência da
própria ADR-0067. (⛔ Não afirmo que isso cause a rejeição — com n=1 no outro grupo, não dá para testar.)

---

## Bloco D · Dados que mentem (medições novas)

### D4 · A tela de Eventos mostra 2,3 linhas por fato real
Medido no RVB: **423 alertas → 238 são repetição** da mesma câmera+classe em ≤10s → **185 cenas
distintas**. O cliente vê um sistema barulhento onde há um sistema repetitivo.

### D5 · Eventos × Verificação — quase tudo já existe
Medido antes de construir, e o achado é que **o conserto é menor do que parecia**: o gesto de
julgar **já está** na lista de Eventos (`Eventos.tsx:323`, botões "Procedente"/"Falso positivo" em
635/642), usa o **mesmo** `POST /api/verification/<id>/review` da Verificação — fonte única
confirmada — e o motivo já é exibido. Falta a microcopy que explica a diferença entre as duas
telas, e conferir a condição `podeJulgar`. ⛔ Não fundir as telas: são ergonomias distintas para
públicos distintos.

---

## Dívidas, pedidos e ressalvas

- **Pedido-ao-backend**: telemetria real de conectividade por câmera — `cameras.last_seen` existe
  mas **nenhum código a escreve**, então "online" hoje significa "cadastrada e ativa".
- **Pedido-ao-backend**: precisão por classe servida ao front, para a confiança poder ser traduzida
  em língua leiga sem o front inventar número.
- **Pedido a outra pista (SEMANA-CLIENTE)**: o caminho 2 (classificador de recorte) não tem código
  de produção no repo; e a coordenada da caixa no frame original precisa vir junto.
- **Régua que já existia**: `training/classificador_recorte/regua.py` mede o **dataset**;
  `scripts/ops/calibracao_classes.py` mede a **produção**. São complementares — registrado para
  ninguém fundir por engano.
