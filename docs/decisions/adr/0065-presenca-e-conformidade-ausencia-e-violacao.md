# ADR-0065 — Presença de EPI é conformidade; ausência é violação

**Status:** Proposta · **Data:** 2026-08-24 · **Autores:** Vitor Emanuel (Logikos)
**Relaciona:** ADR-0058 (estágio `validando` = sombra: "infere e registra, mas não notifica"),
ADR-0017 (fail-loud, nunca fallback silencioso), ADR-0004/C-01 (isolamento por tenant),
`docs/FLYWHEEL_ANOTACAO_EPI.md`, D-103 (taxonomia RVB = 6 classes)
**Numeração:** última ADR local é 0062; confirmar que **0063** está livre na `origin/develop`
fresca antes do merge (colisão de numeração já derrubou startup — ADR-0021).

## Contexto

O shadow EPI da RVB roda desde 08/2026 e já gravou 149 linhas em `public.alerts`
(tenant 63c219d8-…). Ao olhar o conteúdo, **a maioria é EPI PRESENTE**:
`{"class": "Protetor auditivo", "confidence": 0.76, "modo": "shadow"}`. Um
trabalhador **usando** protetor auricular vira, hoje, uma linha na tabela de
ALERTAS, exibida na coluna "Violação" do histórico, contada no sino de
notificações e somada ao KPI de conformidade.

Não é um bug de tela. O sistema tem o conceito certo e não o aplica:

- `module_classes.is_violation` (migration 009) existe e está correto para o
  catálogo **global**: `helmet=false`, `no_helmet=true`.
- As classes da RVB **não estão no catálogo global** — são classes custom do
  tenant, em `yolo_classes` (003 + 093), tabela que **não tem a coluna**.
- `module_service.get_classes()` monta a lista devolvida por
  `GET /api/modules/epi/classes` e escrevia `"is_violation": False`
  **hardcoded** para toda classe de tenant. Para a RVB, "Sem protetor de
  ouvido" e "Protetor auditivo" chegavam ao frontend com a mesma polaridade —
  e ela era a errada.

O estrago se propagava:

1. `GET /api/alerts` não distinguia nada. Histórico, `EventLogWidget`,
   `RecentAlertsWidget` e `NotificationBell` tratavam todo alerta como violação.
2. `module_service.get_stats` calcula
   `compliance_rate = 100*(1 − horas-câmera-com-violação / (câmeras*24))`
   sobre `alert_repo.camera_hours_with_violation`, que contava TODO alerta.
   Efeito perverso: **quanto mais gente usa EPI, mais o "compliance" cai**.
   `compliance_by_class` tinha o mesmo defeito, via `violation_hours_by_class`.
3. `InvestigationPage.tsx` já pinta `is_violation ? 'danger' : 'success'` — e
   por causa do hardcoded pintava toda a taxonomia da RVB de verde.
4. `_save_alert` (`infrastructure/queue/tasks/inference.py`) grava em
   `violations` **todas** as detecções do frame: presença sempre viajou junto.

## Decisão

**1. Semântica.** *EPI PRESENTE = CONFORMIDADE* — é telemetria (taxa de uso por
área), **não** evento alertável. *EPI AUSENTE* (classes que começam com "Sem " e
"Uso incorreto de mascara") = **VIOLAÇÃO** — evento alertável.

**2. A polaridade mora no banco, por classe, e é editável — não é regex em
código.** `yolo_classes` ganha `is_violation` (migration 125), a mesma coluna que
`module_classes` já tem. O prefixo "Sem " é usado UMA VEZ, no backfill, para dar
o valor inicial às classes existentes; a partir daí a fonte da verdade é a linha,
e um admin pode corrigir sem deploy. Regra por nome em runtime foi **recusada**:
nesta taxonomia o oposto é o mesmo nome com prefixo de negação ("Botas" × "Sem
botas"), e uma heurística de string erraria em silêncio na direção cara.

**3. Coluna ANULÁVEL, e o backfill roda só `WHERE is_violation IS NULL`.**
Produção re-executa **toda** migration a cada boot (`railway_start.py`, sem
`schema_migrations`). Um backfill sem essa guarda desfaria a escolha do admin a
cada reinício da API. `NULL` = "ninguém decidiu ainda".

**4. Classificação do alerta (derivada na leitura, fail-loud).**
Um alerta é **conformidade** quando tem ≥1 entrada em `violations` **e toda**
classe está explicitamente marcada como presença (`is_violation IS FALSE`).
Qualquer outra coisa é **violação**:
  - classe fora do catálogo (nome que o modelo emitiu e ninguém cadastrou);
  - entrada sem chave `class` — é o caso dos alertas `camera_gap` do liveness
    (`[{"type": "camera_gap", …}]`, `liveness_alert_repository.create_gap_alert`),
    que **precisam** continuar visíveis;
  - `is_violation IS NULL` (não decidida).
Sumir da tela é o erro caro; aparecer a mais é barato (ADR-0017).

**5. Nada é reescrito no banco.** `event_kind` é derivado por query. Os 149
alertas existentes são reinterpretados, não migrados — reversível revertendo o
código.

**6. Padrão das telas.** `GET /api/alerts` ganha `?kind=violation|compliance`,
**default "todos"** (nenhum consumidor existente muda de comportamento). Quem
muda são as telas, explicitamente: histórico, dashboard e sino passam a pedir
`kind=violation`. Conformidade fica em filtro separado, com um painel de **taxa
de uso por área** = `conformidade / (conformidade + violação)`, agrupado por
`cameras.location` (a câmera é a proxy de área hoje).

**7. Notificação nasce ligada à AUSÊNCIA, por construção.**
`notification_channels` tem 0 linhas — o roteamento continua DESLIGADO. Quando
nascer, o predicado que ele consultará é o mesmo `kind=violation` desta ADR, e o
sino já passa a usá-lo agora. Não existe caminho em que "EPI presente" chegue a
notificar alguém sem código NOVO escrito para isso.

## Medição de campo (2026-08-24, campo virgem)

Das **5 classes de ausência**, só **DUAS** sustentam precisão ≥ 0,50:

| Classe | Limiar | Precisão | Veredito |
|---|---|---|---|
| Sem protetor de ouvido | 0,25 | ≥ 0,50 | **sustenta** |
| Uso incorreto de mascara | 0,30 | 0,75–1,00 | **sustenta** |
| Sem Luvas | — | < 0,50 | não sustenta — gap de dado |
| Sem mascara | — | < 0,50 | não sustenta — gap de dado |
| Sem Oculos | — | < 0,50 | não sustenta — gap de dado |

**Isto é uma segunda chave, não a mesma.** "Sem Luvas" **é** ausência e **é**
violação semanticamente — continua `is_violation = true` e continua aparecendo na
tela. O que a precisão decide é se ela pode **acordar alguém**. Quando o
roteamento de notificação nascer, começa restrito às duas que sustentam; as
outras três são **gap de dado registrado**, não classe "desligada" — precisam de
mais frames anotados, não de menos taxonomia.

## Consequências

- **Positivo:** o KPI de conformidade para de andar para trás. O sino para de
  tocar por gente usando EPI. A polaridade vira dado editável em vez de
  hardcoded. `InvestigationPage` (que já lê `is_violation`) passa a pintar
  vermelho o que é vermelho, sem tocar nela.
- **Números vão mudar:** `compliance_rate` e `compliance_by_class` mudam de valor
  no dia do deploy — não é regressão, é o número saindo de invertido. Vale avisar
  antes de mostrar para o cliente.
- **Não conserta o ESCRITOR.** O processo que grava o shadow não está nesta
  branch. Ele continua criando linha em `alerts` para EPI presente; esta ADR
  garante que essa linha seja **lida** como conformidade. Fazer presença nascer
  como telemetria (e não como alerta) é PR separado, no escritor — e a `taxa de
  uso` desta ADR é exatamente o consumidor que ela vai alimentar. Enquanto isso,
  `alerts_today`/`alerts_week` (que não têm o predicado) seguem contando presença.
- **`module_classes` é global, sem tenant.** Um tenant que crie classe custom com
  nome igual a uma global herda a polaridade global. Aceito: o namespacing de
  `class_id` já existe (`class_namespace`), o de NOME não, e inventá-lo aqui seria
  escopo de outra decisão.
- **Só `class_name` entra no conjunto de presença**, não `display_name`. Ampliar o
  casamento de nomes amplia o lado "conformidade" — a direção cara. Se algum dia
  um escritor emitir display_name, isso aparece como violação (visível), não como
  sumiço.
- **Dívida aberta:** o `<select>` de "tipo de violação" no histórico ainda tem
  `no_helmet/no_vest/no_gloves/no_safety_glasses` fixos no JSX — classes que a RVB
  **não usa** (D-103). Filtro morto para o cliente âncora; trocar por
  `useModuleClasses` é conserto de 10 linhas em outro PR.
- **Fora do predicado, de propósito:** `search_events` (aba Investigação) e
  `demo_events` continuam sem distinguir — manter o diff pequeno.

## Testes

- `services/api/tests/unit/api/test_alerts_kind_filter.py` — fronteira HTTP:
  `?kind=` chega ao repositório, valor inválido não vira 500, `event_kind`
  sobrevive ao envelope, `/alerts/usage-rate` existe de verdade (e não é
  engolida pela rota dinâmica `/<alert_id>`).
- `services/api/tests/integration/test_alert_event_kind.py` — Postgres real:
  alerta só-presença = conformidade; uma ausência basta para ser violação;
  `camera_gap` sem `class` = violação; classe fora do catálogo = violação;
  `is_violation NULL` = violação; `total` acompanha o filtro; cross-tenant
  (C-01); os dois agregados do KPI invertido; taxa de uso por área.

Medido em 2026-08-24: **26 falham** no código pré-fix, **27 passam** depois.
Migration 125 rodada 2× no harness, com correção manual de admin no meio —
a escolha do admin sobreviveu à segunda passada.

---

## Nota de numeração (2026-08-25)

Esta ADR nasceu como **ADR-0063** e foi renumerada para **0065** ao mergear
`origin/develop`, que havia criado uma ADR-0063 própria (handshake SocketIO).
Quem mergeia depois renumera.

**As migrations `125_yolo_classes_is_violation.sql` e
`127_polaridade_nao_erode.sql` continuam citando "ADR-0063" no texto, e isso é
deliberado.** As duas já foram aplicadas e o ledger guarda o `sha256` de cada
uma; editar qualquer caractere — inclusive dentro de comentário — faz o boot da
API abortar com `MIGRATION EDITADA: checksum divergente`. Já aconteceu nesta
mesma rodada.

O script de renumeração passou por cima delas e foi barrado pelo guard
`test_polaridade_nao_erode.py::test_a_125_nao_pode_ser_editada`, que existe
exatamente para isso. Texto de migration aplicada é congelado; uma citação
desatualizada lá dentro é o preço correto dessa imutabilidade.
