# Migration Wiring Spec — Frontend v3 "Centro de Comando" × Backend

> **Objetivo:** conectar o novo frontend (`Recognition-visao-final.dc.html`) aos endpoints **corretos**,
> tela a tela, sem carregar os bugs de fiação do front atual. Meta: o que funciona hoje continua
> funcionando; o que está com drift hoje é **consertado**, não replicado.
> **Data:** 2026-07-12 · **Relaciona:** ADR-0041 (migração v3), task-069 (contrato),
> ADR-0037 (contrato de treino).

## Fontes de verdade

1. **Design:** `docs/design/recognition-v3/Recognition-visao-final.dc.html` (+ `support.js`, `screenshots/`).
2. **Contrato de tipos/versionamento:** `docs/API_CONTRACT_MAP.md` (mapa por domínio + 15 achados graves + tabela de divergências).
3. **Contrato de operabilidade:** `docs/quality/CONTRATO_FRONT_BACK.md` (246 endpoints, quais têm UI, raw-fetch, órfãos).

## Políticas de fiação (inegociáveis)

1. **Envelope:** todo response é `{status, data}` (`app.core.responses`). Onde um service atual assume
   `{success, message, data}` (ex.: `eventsService`, achado #3), a migração usa `{status, data}`.
   Verificar em runtime antes de portar.
2. **Sempre via `api.ts`** (injeta JWT/timeout/erro). **Zero `raw fetch()`** — o contrato listou 10
   violações; a migração não cria a 11ª. Telas que hoje usam raw fetch (Annotation, TabletTransition,
   admin audit-log) são portadas **para o wrapper**.
3. **Path real registrado, não a pasta:** vários blueprints em `api/v1/<dom>/` servem em `/api/...`
   sem `/v1` (cameras, modules, operations, reports, training…). Usar o path que o mapa marca como
   **real**, não presumir `/api/v1`.
4. **Endpoint inexistente/morto ⇒ UI "em breve" + nota, NUNCA chamada fabricada.** Casos: Counting
   #1/#2 (endpoints que não existem), Frames #9 (blueprint vazio — sem `pre-annotate`). A tela mostra
   estado "em breve", não chama rota morta.
5. **`tenant_id` sempre.** Não portar nenhuma chamada que dependa de comportamento cross-tenant
   inseguro (achados #6, #7, #14) — ver Trilha de Defeitos.
6. **Sem inventar contrato:** endpoint/campo que o design pressupõe e o backend não tem → "em breve" +
   entra como pendência de backend (ADR/nova task), não como chamada chutada.

## Mapa tela → endpoints (por tela do design)

> Legenda: ✅ contrato ok (portar direto) · ⚠️ divergência (portar consertando) · ⛔ não existe (UI "em breve").
> Detalhe exaustivo de cada domínio em `API_CONTRACT_MAP.md §1.x` (referenciado).

### Boot / Login  → Auth (MAP §1.3, família `/api`)
- ✅ `POST /api/auth/login` `{email,password}` → `{status,data:{token,user}}`. (via `useAuth`.)
- Registro: não há UI hoje; o design não expõe → não fiar.

### Module Select  → Modules (MAP §1.18, família `/api`)
- ✅ `GET /api/modules/` → módulos habilitados do tenant. `GET /api/modules/<code>`, `/classes`, `/stats`.
- ⚠️ Nome de módulo customizável (ADR-0035) vem daqui — usar o campo do tenant, não chumbar "EPI".

### App Shell (nav, usuário, notificações, ⌘K, tema)
- ✅ Notificações: Notifications (MAP §1.19, `/api/v1/notifications`).
- ✅ Perfil/logout: Auth.
- ✅ Tema/white-label: branding **canônico** `PUT/GET /api/v1/admin/tenants/<id>/branding` (MAP §1.4).
  ⚠️ **NÃO** usar `/api/v1/admin/branding` (deprecated, achado #10).
- ⌘K: casca no andaime (task-070); ações reais plugam nos services existentes por tela.

### Monitorar (situation room)
- ✅ `GET /api/reports/home` (Reports, MAP §1.23, família `/api`) — KPIs/cards.
- ✅ Dashboard KPIs (MAP §1.8, `/api/v1`, blueprint sem prefix — checar paths reais).
- ✅ Alertas recentes: Alerts (MAP §1.2). Câmeras/status: Cameras (MAP §1.5). Live: Streams (MAP §1.30, `/api`).
- ⚠️ Se usar timeline de eventos: Events (MAP §1.12) — **corrigir envelope** (achado #3) antes de portar.

### Câmeras + Camera Wizard + Scenario/ROI Editor
- ✅ Cameras (MAP §1.5): CRUD `/api/cameras`, `stream/start|stop`, `probe`, `config`, `test`, `health-context`.
- ⚠️ Migração `/api`→`/api/v1` **incompleta** (achado #12): só `probe/effective-model/config/health-context`
  têm alias `/api/v1`. Usar o path real por rota (o mapa marca cada uma), não presumir.
- ✅ Scenario/ROI: Scenarios (MAP §1.27, `/api/v1`) + Operations (MAP §1.20, `/api`).
- ⛔ Pré-anotação de frame: Frames (MAP §1.14) é **blueprint vazio** — `pre-annotate` não existe. UI
  "em breve" (casa com WS-B4 flag OFF, ADR-0031). Não chamar.

### Alertas + Alert Detail Drawer
- ✅ Alerts (MAP §1.2, `/api`): lista + filtros + export CSV.
- ⚠️ `acknowledge` está **registrado 2x** (achado #11: alerts + training). Fiar no dono natural
  (`alerts/routes.py`), não no delegado de training.
- ⚠️ `GET /api/alerts/<id>/snapshot` — **sem filtro tenant_id** (achado #7, P0). Não portar até o fix
  (Trilha de Defeitos); enquanto isso, drawer mostra o alerta sem o snapshot cross-tenant.
- ✅ Fila de revisão/verify: Verification (MAP §1.32) — ⚠️ checar tenant_id no service (achado #14).

### Modelos
- ✅ Models (MAP §1.17, `/api/v1`): lista, `activate` (gate de eval), `eval`, `drift`, `evaluate` (PR-4),
  model-config por câmera `POST /api/cameras/<id>/model-config` + history/rollback (PR-4, WS-C2).

### Treinar (canvas do pipeline)
- ✅ Training (MAP §1.31, majoritária `/api`): `jobs`, `jobs/<id>/progress|status`, `models`,
  `models/<id>/activate`, `videos`. Canvas via @dnd-kit.
- ✅ Datasets (MAP §1.9, `/api/v1`): versões/COCO. Operation Wizard: Operations (MAP §1.20).
- ⚠️ **3 pipelines de upload coexistem** (achado #13): FE hoje usa `/api/training/videos` (legado);
  existe `/api/v1/videos/*` (14 rotas, R2+Celery, **zero consumidor**). Decidir na migração qual é o
  canônico (recomendo `/api/v1/videos/*`) e fiar só nele — não manter os dois.

### Admin / Super — Tenant Detail
- ✅ Admin (MAP §1.1, `/api/v1/admin`, `require_superadmin`): tenants CRUD, overview, plan-history, suspend/reactivate.
- ✅ Roles (MAP §1.25) — namespace `/api/admin/*` (distinto de `/api/v1/admin/*`; atenção ao prefixo).
- ⚠️ Criação de tenant devolve `temp_password` previsível (achado #4, P0 segurança) — Trilha de Defeitos.

## Trilha de Defeitos (independente da migração — mas a migração NÃO pode surfar o bug)

Estes são bugs reais **de hoje**, achados no contrato. Não são culpa da migração, mas a spec acima
manda a UI nova **não depender** deles. Cada um vira issue rastreada (não bloqueia o andaime/Fase 0):

| # | Defeito | Sev | Ação na migração |
|---|---------|-----|------------------|
| #4 | `temp_password` de tenant previsível (`...2024!`) | P0 seg | não exibir/depender; fix backend |
| #5 | `POST /api/v1/quality/demo/seed?force=true` apaga dados reais (qualquer user do tenant) | P0 seg | não expor botão; fix backend (exigir admin) |
| #6 | `PATCH /api/modules/.../classes/...` sem tenant_id/role | P0 seg | não portar edição de classe até fix |
| #7 | `GET /api/alerts/<id>/snapshot` sem tenant_id | P0 seg | drawer sem snapshot até fix |
| #8 | `edge_events/ingest` passa `request` em vez do token (auth sempre falha?) | P0 func | verificar; não é UI, mas quebra ingest |
| #14 | verification/queue sem tenant_id visível | P0 (verificar) | confirmar filtro no service antes de portar |
| #3 | `eventsService` parseia envelope errado | P0 | corrigir envelope ao portar Monitorar/timeline |
| #1/#2 | `countingService` chama endpoints inexistentes | P0 | UI "em breve"; wire só no real (`/plate`) |
| #9 | `frames_bp` vazio (sem `pre-annotate`) | P1 | UI "em breve" |
| #10 | branding duplicado (deprecated ainda vivo) | P1 | usar só o canônico |
| #11 | `acknowledge` registrado 2x | P1 | fiar no dono (alerts) |
| #12/#13 | `/api`×`/api/v1` e uploads duplicados | P1 | escolher canônico, fiar num só |
| #15 | `storage/health` público executa I/O real | P1 seg | não expor; fix backend |

## Ordem de execução (casada com ADR-0041)

1. **Fase 0 — andaime** (task-070): flag `ui_v3`, shell vazio, tema real, ⌘K casca. Não fia dado.
2. **Fases 1..6 — por tela** (ADR-0041): cada tela porta os endpoints da seção acima, **consertando** a
   divergência marcada (⚠️) e mostrando "em breve" onde ⛔. Um PR por fatia, STOP-for-review.
3. **Paralelo — Trilha de Defeitos:** abrir as issues P0/P1; os P0 de segurança priorizados (não
   dependem da migração, mas são risco real hoje).
4. **Gate de "funciona igual":** por tela migrada, checklist de paridade — cada endpoint que o front
   atual chama com sucesso deve responder igual no novo (mesma resposta, mesmo comportamento), e as
   chamadas ⚠️/⛔ documentadas como conserto/adiamento consciente.

## Aberto pra você decidir

- **Uploads (achado #13):** consolidar em `/api/v1/videos/*` (recomendo) e aposentar `/api/training/videos`?
- **Defeitos P0 de segurança:** corrigir **antes** de migrar as telas que os tocam (Alertas, Módulos,
  Admin, Quality), ou em paralelo com issues rastreadas? (Recomendo: os de segurança antes.)
