# Identidade Visual por Tenant — spec visual

**Rota:** `/admin/branding/tenants` (dentro do `AdminLayout`)
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminBrandingTenantsPage.tsx` (190 linhas); layout: `apps/frontend/src/modules/admin/AdminLayout.tsx` + `AdminLayout.css.ts`
**Screenshots:**

| Estado  | Dark                                                        | Light                                                        |
|---------|-------------------------------------------------------------|--------------------------------------------------------------|
| default | `../screenshots/admin-branding-tenants/dark-default.png`    | `../screenshots/admin-branding-tenants/light-default.png`    |
| empty   | `../screenshots/admin-branding-tenants/dark-empty.png`      | `../screenshots/admin-branding-tenants/light-empty.png`      |

## Layout — regiões

- **AdminLayout** (compartilhado): topbar fixa (logo "Painel Admin", sino, toggle Pro, "Auditor Visual", badge `SUPERADMIN`, botão "Sair") + sidebar 220px (grupos VISÃO GERAL / OPERAÇÃO / MODELOS & TREINO / RELATÓRIOS / ADMINISTRAÇÃO) + área de conteúdo com scroll interno (`height: 100vh; overflow: hidden` no shell — o scroll é do container interno).
- **Conteúdo da página**: `padding: 32px`, `maxWidth: 720px`, coluna única.
  - Cabeçalho: ícone `Palette` 20px (cor `#06b6d4` hardcoded) + H2 20px/700 (`#f0f4f8` hardcoded), `gap: 10`, `marginBottom: 6`.
  - Parágrafo descritivo 13px `#668096` (hardcoded), `margin: 0 0 28px`.
  - Lista vertical de cards de tenant: `flexDirection: column`, `gap: 10`.
  - Rodapé de ações: `marginTop: 24`, dois botões ghost lado a lado (`gap: 10`).

## Árvore de componentes

- `AdminBrandingTenantsPage`
  - Header (ícone + `h2` + `p`) — tudo inline-style, sem `PageHeader` canônico
  - Card de tenant (div clicável, um por tenant; NÃO usa `Panel`):
    - background `#111318`, border `1px solid #1e2730`, radius 10, padding `14px 18px`, `cursor: pointer`
    - hover: só `borderColor → #2a3545` (mouseenter/mouseleave inline)
    - Swatches: 2 quadrados 24×24 radius 4 (primária + secundária), borda `rgba(255,255,255,0.08)`
    - Info: nome do tenant 14px/600 `#f0f4f8`; linha meta 12px `#668096` com nome do produto + badges condicionais `• Suspenso` (`#ef4444`, 11px) e `• Customizado` (`#06b6d4`, 11px)
    - Logo (se `logo_url`): `img` height 28, maxWidth 80, opacity 0.8
    - `ChevronRight` 16px cor `vars.color.borderStrong` (único uso de token na página)
  - Botões "Ver tema padrão" e "Abrir Sandbox": transparent, border `1px solid #1e2730`, radius 6, texto 13px `#8ba3bc`, padding `8px 16px` — sem componente `Button`, sem hover

## Copy exata

- Título: `Identidade Visual por Tenant`
- Descrição: `Configure cores, logo e nome do produto por tenant. As alterações são salvas no banco de dados.`
- Loading: `Carregando tenants...`
- Vazio: `Nenhum tenant encontrado.`
- Badges: `• Suspenso` | `• Customizado`
- Botões: `Ver tema padrão` | `Abrir Sandbox`
- Fallbacks: produto `Recognition`, primária `#06b6d4`, secundária `#ea580c`

## Dados de exemplo (fixtures do builder)

| Tenant | Produto | Swatches | Badges | Logo |
|---|---|---|---|---|
| Tenant RVB Industrial | RVB Safety Vision | verde `#16a34a` + âmbar `#f59e0b` | • Customizado | SVG "RVB" (pílula verde, data-URL) |
| Construtora Horizonte Sul | Horizonte Vision | azul `#2563eb` + âmbar | • Customizado | — |
| Metalúrgica São Carlos | Recognition | ciano + laranja padrão | — | — |
| Agroindústria Vale Verde | Recognition | ciano + laranja padrão | • Suspenso | — |
| Transportadora Andrade & Filhos | Andrade Monitor | roxo `#7c3aed` + laranja | • Customizado | — |

## Estados

- **default**: 5 cards + 2 botões de rodapé.
- **loading**: apenas texto `Carregando tenants...` 13px `#668096` com padding 32 (sem `Skeleton`).
- **empty**: header + `Nenhum tenant encontrado.` + botões de rodapé (sem call-to-action de criação).
- **hover (card)**: borda `#1e2730 → #2a3545` — mudança quase imperceptível; swatches/texto não mudam.
- **hover (botões rodapé)**: inexistente.
- **erro**: inexistente — `catch(() => {})` engole falha da API e cai no estado vazio silenciosamente.

## Navegação e fluxos

- Clique no card → `/admin/branding/tenants/:id` (editor).
- `Ver tema padrão` → `/admin/branding/default`.
- `Abrir Sandbox` → `/admin/branding/sandbox`.
- Branding por tenant carregado em paralelo (`Promise.allSettled`); falha individual usa `DEFAULT_BRANDING`.

## Problemas identificados (resumo — detalhe no findings JSON)

1. **P0 (light)** Título `#f0f4f8` hardcoded → invisível sobre bgBase claro (`1.01:1`).
2. **P1 (light)** Botões de rodapé `#8ba3bc` sobre fundo claro → `2.39:1`.
3. **P1** Cards com fundo/borda hardcoded (`#111318`/`#1e2730`) — ilhas escuras sob white-label claro (classe task-063/WS1); página inteira fora do padrão de tokens (só 1 uso de `vars`).
4. **P2 (light)** Descrição/meta `#668096` → `3.78:1` (falha AA 4.5:1).
5. **P2** Card clicável é `div` sem `role="button"`/`tabIndex`/focus — inacessível por teclado.
6. **P3** Hover do card sutil demais; botões sem hover; swatch border `rgba(255,255,255,0.08)` hardcoded; empty state sem convite à ação; loading sem Skeleton; badge `Customizado` ignora `color_secondary` customizado; erro de API silencioso.
7. Nota transversal (fora do escopo da página): faixa escura na borda esquerda em todos os screenshots light (artefato do shell/scrollbar, compartilhado com outros grupos).

---

## Findings (develop — 2026-07-07)

### Contexto de mudanças relevantes
- **WS1** (d7a3ad3): `AdminBrandingTenantsPage.tsx` usa **190 linhas de inline styles** com apenas 1 uso de `vars` (ChevronRight). **Não foi coberta** pela migração WS1 — identificada como risco pré-existente.
- **task-063**: abordou painel de vídeo de Operações; não afeta esta página.
- **task-065**: guard-rail no CI para CSS files. Inline styles escapam ao guard.

### Tabela de findings

| # | Sev | Descrição | Status |
|---|---|---|---|
| 1 | P0 | Título `#f0f4f8` hardcoded → invisible sobre bgBase claro (1.01:1). Confirmado em `light-default.png`: área do título vazia entre ícone Palette e parágrafo descritivo. | **PERSISTE** |
| 2 | P1 | Botões de rodapé "Ver tema padrão" / "Abrir Sandbox" com `#8ba3bc` sobre fundo claro → 2.39:1. Confirmado em `light-default.png` e `light-empty.png`. | **PERSISTE** |
| 3 | P1 | Cards com fundo `#111318` e borda `#1e2730` hardcoded — ilhas escuras claras no light. Todos os 5 cards aparecem como blocos escuros sobre fundo claro em `light-default.png`. | **PERSISTE** |
| 4 | P2 | Descrição `#668096` → 3.78:1 no light (abaixo de 4.5:1 AA para texto 13px/normal). | **PERSISTE** |
| 5 | P2 | Cards são `div` sem `role="button"`, `tabIndex` ou foco visual — inacessíveis por teclado. | **PERSISTE** |
| 6 | P3 | Hover de card quase imperceptível (`#1e2730 → #2a3545` — diferença de ~6% em brightness); botões sem hover; swatch border `rgba(255,255,255,0.08)` hardcoded; loading sem Skeleton; badge "Customizado" ignora `color_secondary` do tenant; erro de API silencioso (catch vazio). | **PERSISTE** |

### Novos findings (develop)

| # | Sev | Descrição |
|---|---|---|
| 7 | P2 | `light-empty.png`: texto "Nenhum tenant encontrado." aparece em cor desconhecida (possivelmente `#668096` = 3.78:1 no light, abaixo de AA). Ícone de Palette (ciano) presente mas sem h2 acima — confirma que o problema de P0 persiste mesmo no estado vazio. |

### Resumo

- **Resolvidos:** 0
- **Persistem:** 6
- **Novos:** 1 (P2 — texto empty state abaixo de AA no light)

### Notas de observação visual
- `dark-default.png`: página funciona corretamente no dark — swatches coloridos, badges "Customizado" (ciano) e "Suspenso" (vermelho), logo RVB visível, navegação clara.
- `light-default.png`: ilhas escuras (#111318) dramaticamente visíveis contra fundo branco; título ausente; botões de rodapé com texto de baixo contraste.
- `dark-empty.png`: ícone + título + descrição + botões — correto no dark.
- `light-empty.png`: ícone visível (ciano), descrição cinza, título ausente, botões de baixo contraste.
