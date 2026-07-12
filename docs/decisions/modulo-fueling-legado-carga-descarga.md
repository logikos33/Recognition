# ⚠️ Módulo `fueling` (legado) → Carga e Descarga — LIXO ANTIGO A REVISAR

> **Status:** 🔴 Aberto · Revisão pendente
> **Criado em:** 2026-06-19
> **Classificação de impacto:** P0-CRÍTICO (multi-serviço: backend + frontend + migrations + testes)
> **Contexto:** Levantamento feito durante o brainstorming de marca (Logikos Vision).

---

## TL;DR

O código tem um módulo chamado **`fueling` / "abastecimento"**. **Esse nome é legado e está errado.**
A realidade do produto é **Carga e Descarga** (pátio / baia de caminhões, com leitura de placa — LPR).
Os dados atuais do módulo são **mock** (`fueling_mock_service.py`), ou seja, **não há lógica real
de produção por trás** — é resíduo de uma fase antiga que precisa ser revisado e renomeado/removido.

**Decisão de terminologia:** parar de usar "abastecimento/fueling". Usar **"Carga e Descarga"**
(interno e externo). O `module_code` técnico pode permanecer durante a transição, mas a comunicação,
os rótulos de UI e a documentação devem dizer **Carga e Descarga**.

---

## De onde isso veio (a conexão Rocca Bella)

A memória do projeto (`.omc/project-memory.json`) aponta uma pasta **`Roccatextil`** com:

- `Apresentacao-Rocca-Bella-Patio-Conteineres.pdf`
- `Apresentacao-RoccaBela-Patio-Conteineres.pptx`
- `Apresentacao-Executiva-Patio-Conteineres-CATH.pptx`
- `Apresentacao-Validacao-CATH-Patio-Conteineres.html`
- `Email-Daniel-Proposta-Expedicao.md`

Ou seja: o caso de uso real evoluiu de "abastecimento" para **pátio de contêineres / expedição /
carga e descarga**, no contexto da oportunidade **Rocca Bella (Roccatextil)**. A task
`tools/agent-driver/tasks/task-050-lpr-carga-descarga.md` confirma o rumo: LPR (leitura de placa)
sobre a classe `plate` já detectada, para fechar o ciclo "qual caminhão / quanto carregou".

> **Sim, os ajustes estão relacionados à parte da Rocca Bella.** O `fueling` é o nome antigo do que
> hoje é a frente de Carga e Descarga para pátio de contêineres.

---

## Esclarecimento de produto

Internamente, o produto aparece como **"Recognition"** com 3 módulos: **EPI**, **Fueling** e **Quality**
(ver `docs/decisions/quality-module-status.md`). Para a marca, a decisão de brainstorming é:

| Camada | Antes (código/legado) | Agora (marca / Logikos Vision) |
|---|---|---|
| Produto | Recognition | **Logikos Vision** |
| Módulo 1 | EPI | Vision Safety (EPI) |
| Módulo 2 | Quality | Vision Quality (Quality Gate) |
| Módulo 3 | **Fueling / Abastecimento** ❌ | **Carga e Descarga** (Vision Yard) ✅ |

---

## Inventário: onde o `fueling` está espalhado

> ⚠️ **Nada disso é standalone.** Todo arquivo de `fueling` é importado/referenciado em outro lugar.
> Apagar um arquivo isolado **quebra o build** (backend ou `tsc` do frontend). Por isso a remoção é
> um refactor coordenado, não um `rm`.

### Backend (`services/api/`)
| Arquivo | O que é | Ação recomendada |
|---|---|---|
| `app/api/v1/fueling/routes.py` | Blueprint `fueling_bp` (KPIs mock) | Renomear → `carga_descarga` ou remover |
| `app/domain/services/fueling_mock_service.py` | **Dados mock** (não-produção) | Remover na limpeza |
| `app/__init__.py` (linhas ~170 e ~197) | Importa e registra `fueling_bp` | Atualizar junto |
| `app/api/v1/cameras/stream_handlers.py` | Referência a fueling | Revisar |
| `app/api/v1/admin/demo_videos_routes.py` | Referência (demo videos) | Revisar |
| `tests/security/test_fueling_endpoints.py` | Testes do endpoint | Renomear/remover com o módulo |
| `tests/integration/test_rvb_operation_types.py` | Testes RVB (carga/descarga) | Manter — é a direção nova |
| `tests/test_demo_videos.py` | Referência | Revisar |

### Frontend (`apps/frontend/src/`)
| Arquivo | O que é | Ação recomendada |
|---|---|---|
| `pages/fueling/FuelingPage.tsx` | Página do módulo | Renomear → `carga-descarga/` |
| `pages/fueling/FuelingPlaceholder.tsx` | Placeholder "Em breve" | Remover/renomear |
| `AppRoutes.tsx` | Rotas `/fueling` | Atualizar rota e import |
| `pages/HomePage.tsx` | Card do módulo | Atualizar rótulo |
| `pages/ModuleSelectionPage.tsx` | Seletor de módulos | Atualizar rótulo (6 refs) |
| `components/layout/Sidebar/CollapsibleSidebar.tsx` | Menu lateral (10 refs) | Atualizar rótulo |
| `components/layout/TopBar/TopBar.tsx` | Topo | Atualizar |
| `stores/appStore.ts` | Estado/módulo ativo | Atualizar chave/rótulo |
| `modules/admin/pages/DemoVideosPage.tsx`, `AdminTenantDetailPage.tsx` | Admin | Atualizar |

### Landing (`apps/landing/src/`)
| Arquivo | Ação |
|---|---|
| `components/UseCases.astro`, `components/RecognitionPossibilities.astro` | Trocar "abastecimento" → "carga e descarga" |

### Migrations (`infra/migrations/`) — ⚠️ NÃO APAGAR
`009_module_classes.sql`, `020_module_classes_dino.sql`, `041_update_fueling_classes.sql`,
`015_counting_sessions.sql`, `037_demo_videos.sql`, `048…`, `049…`

> A regra do projeto (`CLAUDE.md`) é **migrations são append-only — nunca `DROP`/`DELETE`**.
> Logo, as classes `fueling` semeadas no histórico **não devem ser removidas editando migrations
> antigas**. Se for preciso desativar a seed, criar **uma nova migration aditiva** que marque o
> módulo como desabilitado (ex.: `enabled = false`) — decisão a registrar separadamente.

### Artefatos gerados / caches — ignorar (regeneráveis)
`graphify-out/`, `apps/frontend/dist/`, `*/.pytest_cache/`, `.omc/` — não editar à mão.

---

## Riscos / governança (por que não foi feito `rm` direto)

1. **Multi-serviço (P0):** mexe em backend, frontend, testes e seed de banco ao mesmo tempo.
   Pela `CLAUDE.md`, P0 exige verificação manual + testes + e2e.
2. **Quebra de build:** remover arquivos sem refatorar imports quebra `tsc --noEmit` (frontend) e
   o boot da API (`__init__.py` registra o blueprint).
3. **Migrations append-only:** não dá para "limpar" a seed do histórico sem violar a regra; precisa
   de migration aditiva nova.
4. **Branch:** `staging` faz deploy automático no Railway. Um refactor desses **não** deve ir direto
   em `staging` sem testes — deve nascer em `feat/cleanup-carga-descarga` e passar pelo smoke test.

---

## Plano de limpeza recomendado (faseado, seguro)

1. **Fase 0 — Decisão:** confirmar rótulo final ("Carga e Descarga" / "Vision Yard") e se o módulo
   continua (renomear) ou sai de cena agora (remover).
2. **Fase 1 — Branch:** `feat/cleanup-carga-descarga` a partir de `staging`.
3. **Fase 2 — Backend:** renomear `fueling/` → `carga_descarga/`, remover `fueling_mock_service.py`,
   atualizar `__init__.py`, ajustar testes. Rodar `ruff` + `pytest`.
4. **Fase 3 — Frontend:** renomear `pages/fueling/` → `pages/carga-descarga/`, atualizar rotas,
   sidebar, módulo selection, store, home. Rodar `tsc --noEmit`.
5. **Fase 4 — Landing/Docs:** trocar terminologia "abastecimento/fueling" → "carga e descarga".
6. **Fase 5 — Banco (opcional):** nova migration aditiva para renomear `display_name`/desabilitar
   seed legada (sem `DROP`).
7. **Fase 6 — Verificação:** smoke test + revisão antes de merge para `staging`.

---

## Marcação

🚮 **LIXO ANTIGO** — o módulo `fueling`/"abastecimento" é resíduo de fase anterior, com dados mock,
e **precisa ser revisado/renomeado para Carga e Descarga**. Origem: pivô para pátio de contêineres
(oportunidade **Rocca Bella / Roccatextil**). Não usar o termo "abastecimento" em nenhum material
novo (marketing ou produto).
