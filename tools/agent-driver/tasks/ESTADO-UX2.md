# ESTADO-UX2 — rodada de correção UX #2 (modo delta; reentrante: releia TUDO antes de agir)

> Origem: 2ª revisão do Vitor no front novo (31/08), 12 achados. Cliente embarca **quarta 02/09**.
> 🔴 Congelamento de merge: **terça 02/09 18h** → quarta pós-onboarding = ZERO merge.

## Identidade
- Worktree: `~/Logikos-mutirao/wt-ux2`, branch base `ux2/base` de origin/develop **e0bb03e4**
  (⛔ nunca o checkout em `~/Documents` — eviction do iCloud trava o git).
- Cascata: `.claude/agents/` (arquiteto=opus · leitor=haiku · implementador=sonnet · cetico=opus).
- DEV: `https://api-v3-desenvolvimento.up.railway.app` — no SHA **e0bb03e4** (= develop), `running_jobs=0`.
- DB DEV: `railway variables -s Postgres --kv | grep DATABASE_PUBLIC_URL` (railway já linkado ao
  env Desenvolvimento). ⛔ Segredo nunca na transcrição. **Só leitura** — banco vivo, o Vitor está
  julgando nele agora.

## Contexto herdado (rodada #1 — ⛔ NÃO REFAZER)
10 PRs #620–#630 mergeados. Já resolvido: fila de verificação (critério fantasma `needs_human` →
`verification_verdict IS NULL`) · propostas (filtro residual) · dashboard com clique nos widgets ·
catálogo "—" em 5 superfícies · régua de LINGUAGEM (escopo por alcançabilidade + detecção
estrutural) · saída do Estúdio + `rotaHomeDoUsuario()`.
**Pranchas que já existem no bundle** (não redesenhar): `Modelos por Câmera.dc.html` (= E2 desta
rodada: chips por par, colapsável, **ações em massa**, pedido P1 do endpoint de lote) ·
`Fila de Propostas.dc.html` · `Admin Plataforma.dc.html` · `Saúde da Operação.dc.html` (proposta).

## 🔴 ACHADO CENTRAL DA ABERTURA (A1) — a decisão já existia e não foi aplicada

**Não é "recalibrar um limiar". É uma ADR aceita que o código nunca cumpriu.**

`ADR-0067` (Aceita, 25/08, decisor Vitor) — régua: classe de ausência só gera violação enquanto
sustentar **precisão ≥ 50% em campo virgem**. E nomeia o réu, textualmente:
> "`Sem protetor de ouvido` está em 40% e **ainda não passa** — fica fora até passar."

**Medição de hoje (31/08), nos vereditos reais do Vitor em produção, não no dataset:**

| classe | approve | reject | precisão | régua ADR-0067 |
|---|---:|---:|---:|---|
| **Sem protetor de ouvido** | 6 | 16 | **27,3%** | ⛔ reprova (era 40% no dataset; em campo é pior) |
| Uso incorreto de mascara | 2 | 5 | ~28,6% | ⛔ reprova (era 61,9% no dataset — **despencou**) |

Precisão por limiar (`Sem protetor de ouvido`, n=22 julgados):

| limiar | julgados | acertos | falsos | precisão |
|---:|---:|---:|---:|---:|
| ≥0,25 | 22 | 6 | 16 | 27,3% |
| ≥0,30 | 12 | 3 | 9 | 25,0% |
| ≥0,35 | 3 | 1 | 2 | 33,3% |
| ≥0,40 | 2 | 1 | 1 | 50,0% |
| ≥0,45 | 1 | 1 | 0 | 100% |

**Nenhum limiar sustenta ≥50% com `n` que preste** — ADR-0067 exige `n` visível ("precisão sem `n`
não é medida"). Os 100% em ≥0,45 são **1 alerta**: sorte, não evidência. Veredito: a classe **sai
do gatilho de violação** e vira registro/telemetria, exatamente como a ADR já mandava.

### 🔴 LIÇÃO DE MÉTODO — o dado está SE MOVENDO enquanto medimos
Duas queries com minutos de intervalo deram 4/9 e depois 6/16 para a mesma classe: o Vitor está
julgando ao vivo (112→108). **Consequência: ⛔ nenhum limiar chumbado a partir de uma foto.** O
conserto tem de ser um script de calibração reexecutável + a decisão por dado (coluna), nunca uma
constante no código. Todo número reportado leva timestamp.

## Estado dos 12 achados
| # | achado | estado |
|---|---|---|
| A1 | falso positivo "sem protetor de ouvido" | 🔴 MEDIDO — conserto = aplicar ADR-0067 |
| A2 | classes de máscara (sem × uso incorreto) | catálogo JÁ distingue as duas (migration 125) — falta medir acervo |
| A3 | modelos não captam ao vivo | pista SEMANA-CLIENTE (só reportar) |
| B1..B4, C1..C3, D1..D3 | — | varredura em curso |

## Fronteiras anunciadas
- **@F5-PESADA**: C1/C2/E1 tocam `app/admin` (sua faixa). Seu ESTADO-F5 (29/08) diz "admin no
  front novo virá em /novo/admin/usuarios, não antes de quarta". **Medido: `/novo/admin` JÁ EXISTE
  e está completo** (Admin/Usuarios/Tenants/TenantDetalhe/Auditoria/Dispositivos/VisaoGeral). Logo
  o achado do Vitor é de NAVEGAÇÃO (caiu no antigo), não de ausência. Assumo a navegação e a
  fronteira plataforma×tenant; se retomarem, falem aqui e eu devolvo.
- **@SEMANA-CLIENTE**: A3 (modelos não captam ao vivo) é de vocês. Do meu lado só garanto que o
  overlay do Ao Vivo mostre detecção real quando existir.

## 🔴 A1 AMPLIADO (adendo do Vitor) — a confiança exibida é ORNAMENTAL

O Vitor mandou eventos com **98%, 99% e 100%** marcados por ele como falso positivo. Medi se a
confiança prevê o acerto. **Não prevê** (tenant rvb, vereditos humanos reais, 31/08):

| confiança exibida | n | acertos | precisão REAL |
|---|---:|---:|---:|
| **100%** | 36 | 21 | **58,3%** |
| 99% | 22 | 13 | 59,1% |
| 97–98% | 17 | 11 | 64,7% |
| 95–96% | 7 | 4 | 57,1% |
| <95% | 7 | 2 | 28,6% |

A precisão é **plana (~58–65%)** em toda a faixa onde vive quase todo alerta. Um aviso que diz
"100% de confiança" acerta 58% das vezes. Conferi também que `alerts.confidence` e
`violations[].confidence` são **o mesmo valor** (0 divergências) — não é bug de exibição, é que o
número **não carrega informação de acerto**. Mesma família do "zero é uma afirmação", agora como
**"100% é uma afirmação"** — e é a mentira mais cara da tela, porque o operador confia no número.
No detector é ainda pior: 21–33% de precisão, também plana. → PR **A1c**.

### Impacto medido do A1 no que o cliente vê
`event_kind` (alert_repository.py:364-393) é **binário**: `CASE WHEN compliance THEN 'compliance'
ELSE 'violation'`. Classe de polaridade **indecisa cai em 'violation'**. Rebaixar a classe impede
alerta NOVO (`_has_violation` já respeita NULL) mas **não muda o que já está gravado** — na quarta o
cliente ainda veria os 56 alertas de `Sem Luvas`/`Sem Óculos`/`Óculos`, classes que **nem existem no
catálogo do tenant**, rotulados como violação. → PR **A1**: `event_kind` ganha o terceiro valor
`observacao`. ⚠️ Isto é o elo com **D2**: o catálogo e o que o sistema detecta divergem.

### Procedência dos 89 alertas de 25/08 (os únicos numa janela recente)
`origem=classificador_recorte_v1`, 89/89 com evidência real do NVR (⛔ não é mock). **Mas o código
que os gravou NÃO EXISTE no repo** — só o módulo de treino `training/classificador_recorte/`. Foram
inseridos por experimento externo. Consequência honesta: a calibração do caminho 2 é sobre um **lote
experimental**, não sobre o pipeline servido. Em produção o que acusa é só o caminho 1.
⚠️ **88 dos 89 têm `bbox_unidade=recorte_da_pessoa_sem_coordenada_no_frame_original`** — o revisor vê
o recorte e não sabe onde a pessoa está no frame, contra a exigência de evidência da própria
ADR-0067. Pedido registrado. (Não afirmo que isso causa rejeição: n=1 no outro grupo, não dá para testar.)

### Régua já existente — não duplicar
`training/classificador_recorte/regua.py` já faz precisão/recall/abstenção com `PRECISAO_MINIMA=0.50`
e até linha-de-base. Ela mede o **dataset**; `scripts/ops/calibracao_classes.py` (novo) mede
**produção**. São complementares — registrado para ninguém fundir por engano.

## C1 medido (o agente falhou 2×; medi eu)
3 links **absolutos** para o front antigo, sem `rotaNova()`:
`app/admin/Usuarios.tsx:344` (o pior — dentro do admin novo, joga para `/admin/tenants/<id>` legado) ·
`app/modulos/Modulos.tsx:297` (`/admin/observability`) · `app/estudio/Treino.tsx:263`
(`/admin/integrations`, com comentário que ADMITE ser o front antigo). O legado renderiza
`components/layout/Sidebar/CollapsibleSidebar.tsx` — identidade antiga, item "Contagem" (linha 29).
**"Dois admins" esclarecido:** `admin:panel` é SUPERADMIN-ONLY (navPorPerfil.ts:81-89); admin de
tenant não vê item de administração. Não há menu vazando por papel — o vazamento é por link.

## 🔴 LOTE 1 — os 8 temas foram REPROVADOS pelos céticos (com quebra provada)

Isto é o sistema funcionando. Quebras que os céticos provaram rodando:

| tema | quebra provada |
|---|---|
| A1 | conserto de UMA tela só: Dashboard segue binário → o mesmo alerta é "Não definida" em Eventos e **violação** no Dashboard, derrubando o score. Trocou uma mentira coerente por duas telas que se desmentem |
| B1 | 🔴 `salvarCaixa()` carimba por **posição na fila**, não por id → correção **e autoria** caem no alerta ERRADO se a fila reordenar durante o await |
| B4 | consertou a fila, mas o **export** (`versioning_v2.py`) segue descartando o que a fila serve → o anotador trabalha e o dataset perde. Pior que o bug original: gasta gente |
| C2 | Carga tem **2 ramos sem saída nenhuma** (sem `counting:read`, e módulo desligado) — um deles é o estado real do tenant da demo |
| D1 | o teste não trava o "sem fração": a mutação reintroduzindo a fração passou VERDE |
| D3 | serve `display_name` no JSON e a tela ignora (`dashboardEdgeService.ts` sem o campo) |
| A1c, B2 | **CI vermelho**: `manifesto.test.ts` desatualizado. Medi na develop limpa: **8/8 passa** → a desatualização é dos PRs, não pré-existente |

### Achado do cético do A1 que vale além da rodada
`annotation_repository.create_class` insere **sem** `is_violation`, e a coluna é nullable sem
default → **toda classe que o cliente criar no Estúdio nasce indecisa**. Hoje o dano é zero (medi:
**0 classes NULL** no DEV, a migration 125 backfillou tudo), mas é o estado de NASCIMENTO daqui
para a frente. Entrou no conserto.

### 🔴 Onde EU refutei o cético (regra: não alegar sem evidência vale para nós)
Ele afirmou "magnitude atual = 0 — o fix não muda rótulo nenhum no DEV". **Falso.** Medi com o
predicado real (`_IS_COMPLIANCE_SQL` lê o **jsonb `violations`**, não `class_name` — nisso ele
estava certo e eu, na primeira tentativa, errado):

| classe | hoje | com o fix | n |
|---|---|---|---:|
| Sem Luvas | violação | **observação** | 33 |
| Sem Óculos | violação | **observação** | 23 |
| Óculos | violação | **observação** | 12 |

**68 de 423 alertas mudam** — 56% das violações atuais (68 de 121). Isso torna a Quebra 1 dele
**mais grave**: a contradição Eventos × Dashboard atingiria 68 alertas reais na demo, não um caso
hipotético.

### Como fix e calibração se compõem (o que o cliente vê no fim)
Violações hoje: 121. Depois do fix do `event_kind`: 53. Depois de rodar
`aplicar_calibracao_rvb.py` (cadastra `Sem Luvas`=violação 69,7%, `Óculos`=conformidade,
`Sem Óculos`=indecisa; rebaixa `Sem protetor de ouvido` 27,3% e `Uso incorreto` 20,0%):
**66 violações, todas com precisão medida ≥63%**. A demo continua tendo o que mostrar — e o que
mostra acerta 6 em 10, em vez de acusar quem cumpre em 7 de 10.

## Delta (mais recente primeiro)
- 31/08 lote 1 despachado: 8 consertos em worktrees próprios (`wt-ux2-{a1,a1c,c2,b1,b2,d1,b4,d3}`)
  + C1 em `wt-ux2-c1`, cada um com cético opus por cima. Adendo do Vitor incorporado (A1 ampliado,
  D4 dedup, D5 Eventos×Verificação — os dois últimos entram após A1/C2/C1/B1/B2).
- 31/08 abertura: worktree `ux2/base` de e0bb03e4 · 4 agentes criados · contexto herdado lido ·
  **A1 medido no banco e batido contra ADR-0067** · varredura dos 12 achados concluída (12/12).
