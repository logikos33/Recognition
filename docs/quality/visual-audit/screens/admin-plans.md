# Planos — spec visual

**Rota:** `/admin/plans`
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminPlansPage.tsx` · `apps/frontend/src/modules/admin/components/admin.css.ts` (`planBadge`) · `types/admin.ts` (`Plan`) · service `adminService.getPlans()/createPlan()/updatePlan()` (GET/POST `/api/v1/admin/plans`, PATCH `/api/v1/admin/plans/{id}`)
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/admin-plans/dark-default.png` | `../screenshots/admin-plans/light-default.png` |
| empty | `../screenshots/admin-plans/dark-empty.png` | `../screenshots/admin-plans/light-empty.png` |
| loading | `../screenshots/admin-plans/dark-loading.png` | `../screenshots/admin-plans/light-loading.png` |
| error | `../screenshots/admin-plans/dark-error.png` | `../screenshots/admin-plans/light-error.png` |
| modal Novo Plano | `../screenshots/admin-plans/dark-modal-novo-plano.png` | `../screenshots/admin-plans/light-modal-novo-plano.png` |
| modal Editar Plano | `../screenshots/admin-plans/dark-modal-editar-plano.png` | `../screenshots/admin-plans/light-modal-editar-plano.png` |
| hover card | `../screenshots/admin-plans/dark-hover-card.png` | — (só dark) |
| hover Novo Plano | `../screenshots/admin-plans/dark-hover-novo-plano.png` | — (só dark) |

## Layout — regiões

- Shell AdminLayout idêntico ao admin-roles (topbar + sidebar + rodapé de status).
- `pageRoot` (padding 32, maxWidth 1200):
  - `pageHeader`: `pageTitle` "Planos" + `pageSubtitle` "{n} planos cadastrados"; à direita `btnPrimary` "+ Novo Plano".
  - Grid inline `repeat(auto-fill, minmax(280px, 1fr))`, gap 16 — em 1280px: 3 colunas + quebra (4º card na 2ª linha).
- Card de plano: `s.card` (bg `bgSurface`, borda `borderSubtle`, radius 6, padding 24) com `cursor: pointer` inline — **sem estilo :hover/:focus** (o kit `card` não tem hover e o inline não adiciona).
- **Modal ad-hoc (NÃO é o Modal do kit / ADR-0023):** overlay inline `position:fixed; inset:0; background: vars.color.overlay (rgba(0,0,0,.7)); zIndex:1000` com comentário `TODO-WS1: converter para Modal do kit` (AdminPlansPage.tsx:75). Caixa `s.card` width 480 fixa. Sem X, sem Escape, sem focus-trap.

## Árvore de componentes

```
AdminPlansPage (pageRoot)
├── pageHeader → pageTitle "Planos" + pageSubtitle | btnPrimary [Plus 14] "Novo Plano"
├── [error] alertBanner.danger
├── grid auto-fill 280px
│   ├── [loading] muted "Carregando..."
│   └── card por plano (onClick → abre modal de edição)
│       ├── flex: nome (700, flex 1) + planBadge[slug] (fallback s.badge se slug desconhecido)
│       ├── muted "Máx câmeras: {n}" (marginTop 8)
│       ├── muted "Retenção: {n} dias"
│       ├── muted "Aprovação de treino: Sim|Não"
│       └── linha de badges de módulo: s.badge inline bg rgba(59,130,246,.1) + color primary
└── [editing] overlay inline zIndex 1000 → s.card 480px
    ├── pageTitle "Editar Plano" | "Novo Plano"
    ├── 4 campos (label muted + s.input full-width): Nome | Slug | Máx câmeras (number) | Retenção (dias) (number)
    ├── label muted "Módulos permitidos (separados por vírgula)" + s.input (CSV)
    ├── flex: checkbox nativo + "Requer aprovação de treinamento"
    ├── [error] alertBanner.danger
    └── flex justify-end: btnGhost "Cancelar" | btnPrimary "Salvar"/"Salvando..."
```

## Copy exata

- Header: `Planos` · `{n} planos cadastrados` · `Novo Plano`
- Card: `Máx câmeras: {n}` · `Retenção: {n} dias` · `Aprovação de treino: Sim|Não` · badge do slug cru (`basic`, `standard`, `premium`, `enterprise`) · badges de módulo (`epi`, `fueling`, `quality`)
- Loading: `Carregando...`
- Modal: `Novo Plano` / `Editar Plano` · `Nome` · `Slug` · `Máx câmeras` · `Retenção (dias)` · `Módulos permitidos (separados por vírgula)` · `Requer aprovação de treinamento` · `Cancelar` · `Salvar` / `Salvando...` · fallback `Erro ao salvar plano`
- Erro de load (fixture): `Falha ao carregar planos`

## Dados de exemplo (fixtures)

| Nome | slug (badge) | Máx câmeras | Retenção | Aprovação treino | Módulos |
|---|---|---|---|---|---|
| Essencial | basic (cinza) | 5 | 15 dias | Não | epi |
| Profissional | standard (azul) | 12 | 30 dias | Não | epi, fueling |
| Avançado | premium (roxo) | 24 | 60 dias | Sim | epi, fueling, quality |
| Corporativo RVB | enterprise (âmbar) | 60 | 90 dias | Sim | epi, fueling, quality |

Novo Plano abre com defaults: max_cameras `10`, retenção `30`, demais vazios, checkbox desmarcado. `price_per_camera` e `active` existem no tipo `Plan` mas **não são editáveis** no modal.

## Estados

- **default:** 4 cards; badges de slug com as 4 variantes `planBadge`.
- **empty:** subtítulo "0 planos cadastrados" e **conteúdo totalmente vazio** — nenhuma mensagem, ícone ou CTA no corpo (beco sem saída; divergente do empty de roles).
- **loading:** só `Carregando...` muted, sem skeleton.
- **error:** banner danger no topo; grid vazio abaixo.
- **hover card:** **nenhuma mudança visual** (dark-hover-card idêntico ao default) apesar de `cursor:pointer` e card clicável.
- **hover Novo Plano:** opacity .85 (sutil).
- **modal:** backdrop 70% preto opaco nos dois temas (verificado por pixel: `#49494a` sobre light, `#030405` sobre dark); caixa opaca `bgSurface`. Editar abre pré-preenchido (ex.: Corporativo RVB / enterprise / 60 / 90 / "epi, fueling, quality" / checkbox marcado).

## Navegação e fluxos

- `Novo Plano` → modal com `emptyPlan`; `Salvar` → POST `/api/v1/admin/plans`.
- Clique em qualquer card → modal Editar Plano (cópia do plano); `Salvar` → PATCH `/api/v1/admin/plans/{id}`.
- `Cancelar` fecha (único jeito além de salvar — sem X/Escape/click-fora).

## Problemas identificados

1. **P1 contraste (dark):** `planBadge` 11px/600 reprova nas 4 variantes sobre `bgSurface` escuro — enterprise `#b45309`→**2.80:1**, premium `#9333ea`→**2.94:1**, standard `#2563eb`→**3.01:1**, basic `#6b7280`→**3.33:1**. No light, basic fica **4.02:1** (ainda < 4.5).
2. **P1 contraste (light):** badges de módulo `#06b6d4` sobre `rgba(59,130,246,.1)`→branco = **2.11:1** (task-063).
3. **P2 hover ausente:** card clicável sem feedback de hover/focus (dark-hover-card = default); área inteira é o único caminho de edição.
4. **P2 empty state:** corpo 100% vazio, sem convite à ação — usuário não sabe se carregou.
5. **P2 inconsistência:** modal ad-hoc TODO-WS1 fora do ADR-0023; zIndex 1000 ≠ 9999 do modal de roles; sem botão X (roles tem).
6. **P2 hardcode:** `rgba(59,130,246,.1)` inline no TSX + todas as variantes `planBadge` com rgba/hex hardcoded no admin.css.ts (task-063/065).
7. **P3 copy:** badge exibe slug técnico cru ao lado do nome humano; campo "Módulos permitidos (separados por vírgula)" é entrada CSV frágil (sem validação visível); `price_per_camera`/`active` não editáveis.

## Findings (develop — 2026-07-07)

**Screenshots analisados:** dark-default, light-default, dark-empty, light-empty, dark-error, dark-loading, dark-modal-novo-plano, light-modal-novo-plano (não capturado), dark-modal-editar-plano, dark-hover-card, dark-hover-novo-plano
**Commits relevantes:** d7a3ad3 (WS1), task-065

### Findings resolvidos

*(nenhum)*

### Findings que persistem

| ID | Sev | Descrição | Evidência |
|---|---|---|---|
| F1 | P1 | `planBadge` 11px/600 reprova no dark: enterprise 2.80:1, premium 2.94:1, standard 3.01:1, basic 3.33:1; no light basic 4.02:1 (< 4.5) | dark-default — todos os 4 badges visíveis |
| F2 | P1 | Badges de módulo: `#06b6d4` sobre `rgba(59,130,246,.1)` → branco = 2.11:1 no light | light-default — "epi", "fueling", "quality" |
| F3 | P2 | Cards clicáveis sem nenhum feedback visual de hover/focus — dark-hover-card idêntico ao dark-default | dark-hover-card |
| F4 | P2 | Empty state com corpo 100% vazio — sem mensagem, ícone nem CTA (divergente do empty de roles) | dark-empty |
| F5 | P2 | Modal ad-hoc `TODO-WS1` sem botão X, sem Escape/focus-trap; zIndex 1000 ≠ 9999 do modal de Roles | dark-modal-novo-plano |
| F6 | P2 | Hardcodes: `rgba(59,130,246,.1)` inline no TSX + variantes `planBadge` com rgba/hex no admin.css.ts | code (task-065 alvo) |
| F7 | P3 | Badge exibe slug técnico cru (`basic`, `enterprise`) ao lado do nome; "Módulos permitidos (separados por vírgula)" é entrada CSV frágil; `price_per_camera`/`active` não editáveis | dark-default, dark-modal-novo-plano |

### Findings novos

*(nenhum)*
