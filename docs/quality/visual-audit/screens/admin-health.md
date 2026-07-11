<!-- HERDADO DA STAGING — revalidar no próximo run do develop -->

# Saúde da Plataforma — spec visual

**Rota:** `/admin/health` (dentro do `AdminLayout`, role `superadmin`)
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminHealthPage.tsx` · `apps/frontend/src/modules/admin/components/PlatformHealthCard.tsx` · `apps/frontend/src/modules/admin/components/admin.css.ts` · `apps/frontend/src/components/ui/Toast/Toast.tsx` + `Toast.css.ts` (toast global de erro) · serviço `adminService.getPlatformHealth()` → GET `/api/v1/admin/health/platform`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (rico, degradado) | `../screenshots/admin-health/dark-default.png` | `../screenshots/admin-health/light-default.png` |
| empty (healthy, sem serviços) | `../screenshots/admin-health/dark-empty.png` | `../screenshots/admin-health/light-empty.png` |
| loading | `../screenshots/admin-health/dark-loading.png` | `../screenshots/admin-health/light-loading.png` |
| error (500) | `../screenshots/admin-health/dark-error.png` | `../screenshots/admin-health/light-error.png` |
| hover "Atualizar" | `../screenshots/admin-health/dark-hover-atualizar.png` | — (só dark) |

## Layout — regiões

- **Shell do app:** topbar global (hambúrguer, logo, "Painel Admin", sino, toggle "Pro", "Auditor Visual", badge `SUPERADMIN` verde, botão "Sair") + sidebar admin 220px (grupos Visão Geral / Operação / Modelos & Treino / Relatórios / Administração / Saúde — item ativo "Health") + rodapé de status ("● Banco de dados · ● Redis · ● câmeras ativas").
- **Conteúdo** (`admin.css.ts#pageRoot`): padding 32px (`space.xl`), maxWidth 1200px.
  - `pageHeader` (flex space-between, marginBottom 32): à esquerda `pageTitle` "Saúde da Plataforma" (20px/700 `textPrimary`) + `pageSubtitle` (13px `textMuted`, marginTop 4); à direita `btnGhost` "Atualizar" com ícone `RefreshCw` 14px.
  - Banner de erro condicional: `alertBanner.danger` (bg `rgba(239,68,68,0.1)`, borderLeft `3px solid #dc2626`, padding 8×16, radius 4, marginBottom 16).
  - Um único card (`PlatformHealthCard`).
- **Card** (`admin.css.ts#card`): `bgSurface`, borda 1px `borderSubtle`, radius 6 (`radius.md`), padding 24 (`space.lg`).
- **Toast global** (`Toast.css.ts#viewport`): fixed top 16 / right 16, width 340, zIndex 9999 — sobrepõe a topbar (56px). Disparado pelo `api.ts` em erro 500. **Bug:** montado fora do escopo do tema (ver Problemas).

## Árvore de componentes

```
AdminLayout
└── AdminHealthPage (pageRoot)
    ├── pageHeader
    │   ├── pageTitle "Saúde da Plataforma" + pageSubtitle "Atualizado a cada 30s · Última verificação: HH:MM:SS"
    │   └── btnGhost [RefreshCw 14] "Atualizar" (disabled durante loading)
    ├── alertBanner.danger (só em erro)
    ├── muted "Carregando..." (só em loading inicial)
    └── PlatformHealthCard (card)
        ├── flex (marginBottom 12): cardTitle "Saúde da Plataforma" (13px/600 textSecondary, uppercase)
        │   └── healthBadge[status] — pill 11px/600: healthy|degraded|critical
        ├── coluna (gap 8) — 1 linha por serviço:
        │   flex: dot[healthy|degraded|critical] 8px + nome (13px, flex 1) + latência `muted` + details `muted`
        └── (se celery_queues não vazio)
            ├── cardTitle "Filas Celery" (marginTop 16)
            └── flex wrap gap 8: mono 12px "fila: <strong>N</strong>" por fila
ToastProvider (global, top-right) — toast error com borda danger ao falhar o GET
```

Mapeamento status→dot (`statusToDot`): `ok|healthy → healthy` (verde `success`), `degraded → degraded` (`#ca8a04` hardcoded), resto → `critical` (`danger`).

## Copy exata

- Título: `Saúde da Plataforma`
- Subtítulo: `Atualizado a cada 30s` + condicional ` · Última verificação: {hora pt-BR}`
- Botão: `Atualizar`
- Loading: `Carregando...`
- Card título: `Saúde da Plataforma` (duplica o título da página)
- Badge de status geral: `healthy` / `degraded` / `critical` (chave crua do backend, sem tradução)
- Seção: `Filas Celery`
- Erro (banner e toast): `Erro interno do servidor` (mensagem da API, sem instrução de recuperação)
- Não existe mensagem de vazio — card fica com corpo em branco.

## Dados de exemplo (fixtures do spec 21-admin-health)

Status geral: `degraded`. Serviços (nome · dot · latência · details):
- `PostgreSQL` · verde · `12 ms`
- `Redis` · verde · `3 ms`
- `Celery Worker` · verde · — · `3 workers ativos · fila inference drenando`
- `R2 Storage` · amarelo · `844 ms` · `latência alta região GRU`
- `WS Gateway` · vermelho · — · `sem heartbeat há 4 min`
- `Pre-annotation (DINO/SAM)` · verde · `211 ms`
- `Camera Gateway` · verde · `38 ms`

Filas Celery: `inference: 12`, `training: 2`, `extraction: 0`, `quality: 7`, `versioning: 1`.
Empty: `{ status: 'healthy', services: {}, celery_queues: {} }` — badge verde `healthy`, corpo vazio.

## Estados

- **default:** card com 7 serviços + filas; subtítulo mostra hora da última verificação; polling a cada 30s (`setInterval`).
- **empty:** card renderiza só o header (título + badge `healthy`); nenhuma linha, seção de filas omitida (guard `length > 0`). Corpo em branco — beco sem saída.
- **loading:** texto `Carregando...` (`muted`, 12px) no lugar do card; botão "Atualizar" disabled (opacity .5).
- **error:** banner `alertBanner.danger` com a mensagem; card ausente (health nulo). Toast de erro global aparece no topo direito **com fundo transparente** (bug), sobrepondo a topbar.
- **hover "Atualizar":** `btnGhost` só muda `opacity: 0.85` — em fundo transparente a mudança é imperceptível (screenshot hover ≈ idêntico ao default).

## Navegação e fluxos

- `Atualizar` → refaz o GET imediatamente (mesmo `load()` do polling).
- Nenhum modal, nenhuma navegação interna. Sidebar/topbar são a navegação.

## Problemas identificados (resumo — detalhe no findings JSON)

1. **P1 · transparency (ambos os temas):** toast global de erro renderizado sem fundo — `ToastProvider` é montado em `main.tsx` como irmão de `<App/>`, fora do `AppShell` que aplica a classe do tema; todos os `vars.*` do `Toast.css.ts` resolvem para vars indefinidas (background/cores viram transparente). Texto do toast se mistura com "Auditor Visual"/badge SUPERADMIN da topbar.
2. **P1 · contrast:** `btnGhost`? não — `healthBadge` no tema claro: `degraded` #ca8a04 sobre tint 2.67:1, `healthy` #16a34a 2.89:1, `critical` #ef4444 3.10:1 — todos reprovam AA 4.5:1. No dark, `healthy` 4.41:1 e `critical` 4.28:1 também ficam abaixo.
3. **P2 · hardcode:** `healthBadge`, `alertBanner` e `dot.degraded` (#ca8a04) usam rgba/hex fora dos tokens (classe task-063/065) em `admin.css.ts`.
4. **P2 · copy:** status geral exibido como chave crua do backend (`degraded`) em UI pt-BR.
5. **P2 · layout/empty:** estado vazio é um card em branco, sem mensagem nem ação.
6. **P3 · copy:** título do card repete o título da página; erro genérico sem instrução.
7. **P3 · hover:** hover do `btnGhost` (opacity .85 em fundo transparente) sem feedback perceptível.
