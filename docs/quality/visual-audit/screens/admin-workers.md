# Workers On-Premise — spec visual

**Rota:** `/admin/workers` (dentro do `AdminLayout`, role `superadmin`)
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminWorkersPage.tsx` · `apps/frontend/src/modules/admin/components/WorkerStatusBadge.tsx` · `apps/frontend/src/modules/admin/components/admin.css.ts` · hook `useWorkerMonitor` (GET `/api/v1/admin/workers`, polling 10s) · `adminService.restartWorker(schema)` → POST `/api/v1/admin/workers/:schema/restart`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (6 workers) | `../screenshots/admin-workers/dark-default.png` | `../screenshots/admin-workers/light-default.png` |
| empty | `../screenshots/admin-workers/dark-empty.png` | `../screenshots/admin-workers/light-empty.png` |
| loading | `../screenshots/admin-workers/dark-loading.png` | `../screenshots/admin-workers/light-loading.png` |
| error (500) | `../screenshots/admin-workers/dark-error.png` | `../screenshots/admin-workers/light-error.png` |
| hover linha | `../screenshots/admin-workers/dark-hover-row.png` | — (só dark) |
| hover Restart | `../screenshots/admin-workers/dark-hover-restart.png` | — (só dark) |

## Layout — regiões

- **Shell do app:** topbar global + sidebar admin 220px (item ativo "Workers", grupo Saúde) + rodapé de status.
- **Conteúdo** (`pageRoot`): padding 32px, maxWidth 1200px.
  - `pageHeader`: `pageTitle` "Workers On-Premise" + `pageSubtitle` "Atualizado a cada 10s · N registrados". Sem botão à direita.
  - Banner de erro condicional (`alertBanner.danger`).
  - Um `card` (`bgSurface`, borda `borderSubtle`, radius 6, padding 24) contendo a tabela.
- **Tabela** (`admin.css.ts#table`): width 100%, borderCollapse, 13px. `th`: 8×12px, 600, `textMuted`, borderBottom `borderSubtle`, nowrap. `td`: 10×12px, borderBottom `borderSubtle`, `textPrimary`. Linhas com `trHover` (hover `bgHover`, cursor pointer — apesar de a linha não ter ação de clique).

## Árvore de componentes

```
AdminLayout
└── AdminWorkersPage (pageRoot)
    ├── pageHeader → pageTitle + pageSubtitle
    ├── alertBanner.danger (só em erro)
    └── card
        ├── muted "Carregando..." (loading inicial)
        └── table — 10 colunas
            ├── thead: Tenant | Hostname | GPU | Status | GPU% | VRAM | FPS | Câmeras | Último heartbeat | (vazia)
            └── tbody: tr.trHover por worker
                ├── td Tenant: nome (600) + slug (muted 12px)
                ├── td Hostname: mono 12px (— se null)
                ├── td GPU: muted (— se null)
                ├── td Status: WorkerStatusBadge (pill 11px/600 com ícone 11px)
                │     onpremise → [Server] "On-premise" · railway → [Wifi] "Railway" · offline → [WifiOff] "Offline"
                ├── td GPU% / VRAM / FPS / Câmeras: valor de live_metrics ou muted "—"
                ├── td Último heartbeat: muted HH:MM:SS pt-BR
                └── td ação: btnGhost 11px "Restart" [RefreshCw 11] — só quando status === 'onpremise'
            └── (vazio) tr única: td colSpan 10, centralizado, muted "Nenhum worker registrado"
```

## Copy exata

- Título: `Workers On-Premise`
- Subtítulo: `Atualizado a cada 10s · {N} registrados`
- Colunas: `Tenant`, `Hostname`, `GPU`, `Status`, `GPU%`, `VRAM`, `FPS`, `Câmeras`, `Último heartbeat`
- Badges: `On-premise`, `Railway`, `Offline`
- Botão: `Restart`
- Confirm nativo: `Reiniciar worker de {schema}?` · Alert nativo: `Comando enviado: {command_sent}` ou mensagem de erro / `Erro`
- Vazio: `Nenhum worker registrado`
- Loading: `Carregando...`
- Erro: `Erro interno do servidor` (banner + toast global transparente)

## Dados de exemplo (fixtures do spec 21-admin-health)

| Tenant (slug) | Hostname | GPU | Status | GPU% | VRAM | FPS | Câm. | Heartbeat |
|---|---|---|---|---|---|---|---|---|
| Tenant RVB Industrial (rvb-industrial) | rvb-edge-01 | NVIDIA RTX 4070 | On-premise | 62.4% | 9.8 GB | 24.6 | 11 | há 1 min |
| Frigorífico Boa Vista (frigorifico-boa-vista) | bvista-gpu-02 | NVIDIA RTX 3060 | On-premise | 91.2% | 11.4 GB | 17.3 | 9 | há 2 min |
| Construtora Horizonte Sul (horizonte-sul) | — | — | Railway | — | — | — | — | há 6 min |
| Transportadora Andrade & Filhos (transportadora-andrade) | — | — | Railway | — | — | — | — | há 15 min |
| Metalúrgica São Carlos (metalurgica-sao-carlos) | msc-edge-01 | NVIDIA GTX 1660 Super | Offline | — | — | — | — | há 2 dias |
| Agroindústria Vale Verde (vale-verde) | valeverde-nuc | NVIDIA RTX 3050 | Offline | — | — | — | — | há 7 dias |

## Estados

- **default:** 6 linhas; botão Restart só nas 2 linhas On-premise; polling 10s.
- **empty:** tabela com header + 1 linha "Nenhum worker registrado" centralizada; sem CTA/orientação de como registrar um worker.
- **loading:** `Carregando...` no card (só quando ainda não há workers).
- **error:** banner danger + toast global (transparente — ver admin-health) sobre a topbar.
- **hover linha:** bg da linha vira `bgHover` — funciona (visível no screenshot).
- **hover Restart:** apenas `opacity: 0.85` no `btnGhost` — mudança imperceptível; feedback fica por conta do hover da linha.

## Navegação e fluxos

- `Restart` → `confirm()` NATIVO do browser (`Reiniciar worker de {schema}?`) → POST restart → `alert()` NATIVO com `command_sent` ou erro. Diálogos nativos não seguem a identidade visual e não são theméveis (deferred: incapturáveis via screenshot DOM).
- Linha tem `cursor: pointer` + hover mas NÃO tem ação de clique — affordance falsa.
- Nenhum modal próprio; nenhuma navegação interna.

## Problemas identificados (resumo — detalhe no findings JSON)

1. **P1 · contrast (light):** `workerBadge` sob superfície clara — `On-premise` #10b981 sobre tint verde = 2.23:1; `Railway` #ca8a04 = 2.67:1; `Offline` #ef4444 = 3.10:1. No dark, `Offline` = 4.28:1 (marginalmente reprovado).
2. **P2 · inconsistency:** `confirm()`/`alert()` nativos para Restart — fora do padrão de Modal do kit (ADR-0023) e fora da identidade visual.
3. **P2 · hardcode:** `workerBadge` em `admin.css.ts` usa `rgba(34,197,94,.15)`, `rgba(234,179,8,.15)`, `rgba(239,68,68,.15)` e `#ca8a04` fora dos tokens.
4. **P3 · a11y-other:** `trHover` aplica `cursor: pointer` em linhas sem ação — affordance enganosa.
5. **P3 · copy:** vazio sem convite à ação (como registrar um worker); título "Workers On-Premise" lista também Railway/Offline.
6. **P3 · hover:** botão Restart sem feedback visual próprio (opacity .85 em fundo transparente).

---

## Findings (develop — 2026-07-07)

### Contexto de mudanças relevantes
- **WS1** (d7a3ad3): ~70 telas migradas para tokens de design. `AdminWorkersPage` **não está na lista** — usa `admin.css.ts` mas os `workerBadge` hardcodes não foram endereçados.
- **task-065**: `textMuted` subiu para `#8a8a93` no tema professional. Melhora levemente legibilidade de `th` de tabelas em light, mas não afeta os badges hardcoded.
- Demais tasks (063, 067, 068): escopo unrelated (vídeo/streaming).

### Tabela de findings

| # | Sev | Descrição | Status |
|---|---|---|---|
| 1 | P1 | `workerBadge` contraste insuficiente no light: On-premise `#10b981` sobre verde-tint ≈ 2.23:1; Railway `#ca8a04` ≈ 2.67:1; Offline `#ef4444` ≈ 3.10:1. No dark Offline ≈ 4.28:1. Confirmado visualmente no `light-default.png`. | **PERSISTE** |
| 2 | P2 | `confirm()`/`alert()` nativos para Restart — fora do kit de Modal (ADR-0023), sem branding. | **PERSISTE** |
| 3 | P2 | `workerBadge` hardcoded: `rgba(34,197,94,.15)`, `rgba(234,179,8,.15)`, `rgba(239,68,68,.15)`, `#ca8a04` fora dos tokens (`successAlpha`, `warningAlpha`, `dangerAlpha`, `vars.color.warning`). | **PERSISTE** |
| 4 | P3 | `trHover` aplica `cursor: pointer` em linhas sem ação de clique — affordance enganosa. | **PERSISTE** |
| 5 | P3 | Estado vazio sem CTA nem orientação de como registrar um worker. Título "Workers On-Premise" incorreto (inclui Railway/Offline). | **PERSISTE** |
| 6 | P3 | Botão Restart sem feedback hover próprio (opacity 0.85 em fundo transparente — inperceptível, conforme `dark-hover-restart.png`). | **PERSISTE** |

### Novos findings (develop)

Nenhum finding novo. Nota: o item "Workers" existe na sidebar (`AdminLayout.tsx:217`) no grupo "Saúde", mas o grupo fica abaixo da seção ADMINISTRAÇÃO (8 itens), exigindo scroll lateral — não fica visível no viewport 900px sem rolar. Não constitui orphan, mas é uma UX friction de baixa descobribilidade (P3 latente).

### Resumo

- **Resolvidos:** 0
- **Persistem:** 6
- **Novos:** 0

### Notas de observação visual
- `dark-error.png`: toast global de erro sobrepõe o topbar (área de "Pro" toggle) — artefato já documentado em admin-health.
- `light-error.png`: toast visível no topbar em modo claro — mesmo comportamento.
- `dark-hover-row.png` / `dark-hover-restart.png`: hover de linha funciona; hover do botão Restart quase imperceptível.
- Sidebar: grupo "Saúde" (Workers, Inventário, Health) está presente no código mas fica abaixo do fold — requer scroll da sidebar para ser visto.
