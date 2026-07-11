# Tema Padrão Recognition — spec visual

**Rota:** `/admin/branding/default` (dentro do `AdminLayout`)
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminBrandingDefaultPage.tsx` (94 linhas — catálogo hardcoded no componente, read-only)
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/admin-branding-default/dark-default.png` | `../screenshots/admin-branding-default/light-default.png` |

## Layout — regiões

- Conteúdo: `padding: 32px`, `maxWidth: 820px`, coluna única.
- Header breadcrumb: botão `← Tenants` (13px `#668096` hardcoded) + `/` (`vars.color.borderStrong`) + H2 `Tema Padrão Recognition` (20px/700 `#f0f4f8` hardcoded) + badge `🔒 Somente leitura` (ícone Lock 10px, bg `#161a20`, texto `#668096`, 11px/600).
- Parágrafo descritivo 13px `#668096`, `margin: 0 0 28px`.
- Lista de grupos: coluna, `gap: 24`.

## Árvore de componentes

- `AdminBrandingDefaultPage`
  - Card de grupo (um por grupo de tokens; NÃO usa `Panel`): bg `#111318`, border `1px solid #1e2730`, radius 10
    - Header do grupo: padding `10px 18px`, bg `#0d1117`, borda inferior `#1e2730`, label 11px/600 uppercase `#668096`
    - Linhas de token (padding `8px 18px`, `gap: 14`):
      - `Swatch` 28×28 radius 5, borda `rgba(255,255,255,0.08)`; valores rgba ganham fundo xadrez (`linear-gradient` 45° com `vars.color.borderDefault`)
      - nome do token: `code` 12px `#06b6d4` mono, minWidth 140
      - valor: `code` 11px `#8ba3bc` mono, minWidth 200
      - descrição: 12px `#668096`

## Copy exata

- Título: `Tema Padrão Recognition` · badge `Somente leitura`
- Descrição: `Tokens de design base da plataforma Recognition. Tenants herdam esses valores e podem sobrescrever primary, accent e nome.`
- Grupos e itens (literais do array `TOKENS`):
  - **Fundo**: `bgBase #0a0c10` "Fundo principal da aplicação" · `bgSurface #111318` "Superfícies elevadas (cards, sidebar)" · `bgElevated #1e2330` "Modais, dropdowns" · `bgCard #161a20` "Cards secundários"
  - **Texto**: `textPrimary #f0f4f8` "Texto principal" · `textSecondary #8ba3bc` "Texto de suporte" · `textMuted #668096` "Labels, metadados (WCAG AA: 4.76:1)"
  - **Cor Primária (ciano)**: `primary #06b6d4` "Ações principais, links, foco" · `primaryLight #22d3ee` "Hover de botões primários" · `primaryDark #0891b2` "Estado active" · `primaryAlpha rgba(6,182,212,0.1)` "Fundos de foco, seleção"
  - **Acento (laranja-segurança)**: `accent #ea580c` "Alertas visuais, destaques" · `accentLight #f97316` "Hover de acento" · `accentDark #c2410c` "Estado active"
  - **Semânticas**: `success #10b981` "Conformidade, OK" · `warning #f59e0b` "Atenção, limiar" · `danger #ef4444` "Violação, erro crítico"
  - **Bordas**: `borderSubtle #161c24` "Separadores de baixo contraste" · `borderDefault #1e2730` "Bordas padrão de cards" · `borderStrong #2a3545` "Bordas em foco/hover"

## Dados de exemplo

O catálogo é estático (array `TOKENS` no componente) — os dados acima SÃO o conteúdo integral. Nenhum endpoint específico além dos do `AdminLayout`.

## Estados

- **default** apenas. Não existem loading/empty/error (página estática). Sem hover em nenhum elemento (somente leitura de fato).

## Navegação e fluxos

- `← Tenants` → `/admin/branding/tenants`. Nenhuma outra ação.

## Problemas identificados (resumo — detalhe no findings JSON)

1. **P0 (light)** Título `#f0f4f8` hardcoded → invisível sobre bgBase claro (`1.01:1`).
2. **P2 (light)** Botão `← Tenants` e descrição `#668096` → `3.78:1` (falha AA).
3. **P2** Chrome da página hardcoded (cards `#111318`, header `#0d1117`, textos) — os SWATCHES devem mesmo ser fixos (catálogo do tema dark), mas o contêiner/labels deveriam usar tokens para não virar ilha escura no white-label claro.
4. **P3 (dark)** Badge `Somente leitura` `#668096` sobre `#161a20` = `4.23:1` em 11px — abaixo de AA 4.5:1.
5. **P3** Copy desatualizada: "podem sobrescrever primary, accent e nome" omite as 7 superfícies WS1 + favicon que o editor já suporta.
6. **P3** Catálogo duplicado à mão (diverge de `DesignSystemPage` e do token real: falta `bgHover`, `accentAlpha`, `textDim`, `overlay`, `textOnPrimary`, muteds semânticos) — fonte única deveria ser o contrato/tokens.
7. **P3** Swatch border `rgba(255,255,255,0.08)` hardcoded (classe task-063; baixa gravidade por ser decorativa sobre swatch fixo).

---

## Findings (develop — 2026-07-07)

### Contexto de mudanças relevantes
- **WS1** (d7a3ad3): `AdminBrandingDefaultPage.tsx` (94 linhas, catálogo estático hardcoded no componente) **não foi coberto** pela migração WS1 — usa inline styles exclusivamente.
- **task-065**: guard-rail no CI. Inline styles escapam ao lint de CSS files; catálogo de tokens da página está desatualizado em relação ao token real do WS1.
- **WS1 impact na copy**: A descrição "podem sobrescrever primary, accent e nome" ficou ainda mais desatualizada: WS1 adicionou `bgBase`, `bgSurface`, `bgElevated`, `bgCard`, `bgHover`, `accentAlpha`, `textOnPrimary`, `overlay`, `favicon` ao editor de branding — nenhum destes aparece no catálogo estático da página.

### Tabela de findings

| # | Sev | Descrição | Status |
|---|---|---|---|
| 1 | P0 | Título `#f0f4f8` hardcoded → invisível no light (1.01:1). Confirmado em `light-default.png`: breadcrumb mostra "← Tenants /" + badge "Somente leitura" mas o H2 "Tema Padrão Recognition" está ausente. | **PERSISTE** |
| 2 | P2 | `← Tenants` `#668096` → 3.78:1 no light; descrição mesma cor. Confirmado em `light-default.png`. | **PERSISTE** |
| 3 | P2 | Chrome hardcoded: cards `#111318`, header interno `#0d1117` — ilhas escuras no light. Confirmado em `light-default.png`: blocos de token FUNDO/TEXTO aparecem como painéis escuros sobre fundo claro. | **PERSISTE** |
| 4 | P3 | Badge "Somente leitura" `#668096` sobre `#161a20` = 4.23:1 em 11px/600 (abaixo de 4.5:1 AA). | **PERSISTE** |
| 5 | P3 | Copy desatualizada: "podem sobrescrever primary, accent e nome" omite as 7+ superfícies WS1 + favicon suportadas pelo editor. Agravou-se com WS1. | **PERSISTE** (agravado) |
| 6 | P3 | Catálogo estático diverge do token real: faltam `bgHover`, `accentAlpha`, `textDim`, `overlay`, `textOnPrimary`, `successMuted`, `warningMuted`, `dangerMuted` — todos adicionados pelo WS1. | **PERSISTE** (agravado) |
| 7 | P3 | Swatch border `rgba(255,255,255,0.08)` hardcoded (decorativo, baixa gravidade). | **PERSISTE** |

### Novos findings (develop)

| # | Sev | Descrição |
|---|---|---|
| 8 | P2 | Após WS1, o catálogo está **desatualizado em ≥8 tokens** (os novos tokens de WS1 não aparecem na página). Um superadmin consultando "Tema Padrão" para entender o design system vê informação incompleta/incorreta. Escopo: copy/conteúdo, não visual puro. |

### Resumo

- **Resolvidos:** 0
- **Persistem:** 7 (findings 5 e 6 agravados pelo WS1)
- **Novos:** 1 (P2 — catálogo mais desatualizado após WS1)

### Notas de observação visual
- `dark-default.png`: catálogo funcional no dark — swatches de cor visíveis, nomes de token em ciano, valores em azul-acinzentado, descrições em cinza. Layout de tabela por grupo limpo.
- `light-default.png`: title invisível; cards escuros contrastam fortemente com o fundo claro; swatches mostram cores corretas (são fixos por design — catálogo do dark theme).
- A página tem apenas um estado (sem loading/empty/error) — análise limitada a `dark-default.png` e `light-default.png`.
