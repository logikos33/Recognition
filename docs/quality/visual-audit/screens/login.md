# Login — spec visual

**Rota:** `/` (qualquer rota quando `!isAuthenticated` — `App.tsx:29-31` retorna `<Login />` direto, sem router)
**Fontes:** `apps/frontend/src/pages/Login.tsx` · `apps/frontend/src/pages/Login.css.ts` · `apps/frontend/src/hooks/useAuth.ts` (login/register) · `apps/frontend/src/App.tsx` (auth gate)
**Screenshots:**

| Estado | Dark | Light (white-label) |
|---|---|---|
| default | `../screenshots/login/dark-default.png` | `../screenshots/login/light-default.png` |
| tab-register | `../screenshots/login/dark-tab-register.png` | `../screenshots/login/light-tab-register.png` |
| error (client) | `../screenshots/login/dark-error.png` | `../screenshots/login/light-error.png` |
| error-api (401) | `../screenshots/login/dark-error-api.png` | `../screenshots/login/light-error-api.png` |
| loading | `../screenshots/login/dark-loading.png` | `../screenshots/login/light-loading.png` |
| hover-submit | `../screenshots/login/hover-submit.png` | — |
| hover-tab-register | `../screenshots/login/hover-tab-register.png` | — |

> **ATENÇÃO (P0):** todos os screenshots refletem um DEFEITO real da staging — a Login renderiza **sem a classe de tema** (App.tsx retorna `<Login />` fora do `AppShell`, que é quem aplica `recognitionDarkTheme` via `createTheme`; e fora do `ThemeProvider` white-label). Todas as vars vanilla-extract de `Login.css.ts` ficam indefinidas: fundo branco default do browser, texto preto, card/tabs/inputs/CTA sem qualquer estilo. Dark ≈ Light. A spec abaixo descreve o **design pretendido** pelos tokens de `Login.css.ts` + o que aparece nos screenshots atuais.

## Layout — regiões

Página única, sem header/sidebar/footer de app (pré-auth).

- **page**: `minHeight: 100vh`, fundo `vars.color.bgBase` (#0a0c10 dark), flex centrado (horizontal+vertical), `padding: 20px`, fonte `vars.font.sans`.
- **container**: coluna única, `width: 100%; maxWidth: 400px`.
  - **logoWrap** (topo, centrado, `marginBottom: 28px`)
  - **card** (miolo)
  - **footer** (copyright, `marginTop: 20px`)

Espaçamentos internos do card: `padding: 28px 24px`; tabs `marginBottom: 24px`; formStack `gap: 14px`; credHint `marginTop: 16px`.

## Árvore de componentes

- `page`
  - `container` (max 400px)
    - `logoWrap`
      - `logoIcon` — quadrado 72×72, radius 20, gradient 135° `primary→primaryDark` (#06b6d4→#0891b2), glyph "◈" 36px, `boxShadow: glowCyan`
      - `logoTitle` — h1 28px/800, `textPrimary`
      - `logoSub` — p 14px, `textSecondary`, margin `6px 0 0`
    - `card` — `bgSurface`, radius 20, borda 1px `borderDefault`, `shadow.lg`
      - `tabs` — trilho `bgBase`, radius 10, padding 4, gap 4
        - `tabBtn` ×2 — flex 1, padding `9px 0`, radius 8, 14px/600, texto `textMuted`, fundo transparente
        - `tabBtnActive` (variante) — fundo `bgElevated`, texto `primary`, `shadow.sm`
      - `form > formStack` (gap 14)
        - `input` "Nome completo" — só na tab register
        - `input` type=email
        - `input` type=password
        - `input` "Confirmar senha" type=password — só na tab register
        - inputs: padding `12px 14px`, radius 10, borda `1.5px borderDefault`, fundo `bgCard`, 15px `textPrimary`, placeholder `textMuted`; `:focus` borda `primary` + `shadow.glow`
        - `errorBox` (condicional) — padding `10px 14px`, radius 8, fundo `dangerMuted`, borda 1px `danger`, texto `danger` 13px
        - `submitBtn` — padding 13px, radius 10, gradient `primary→primaryDark`, texto `textOnPrimary` (#ffffff) 15px/700, `shadow.glowCyan`; variante `submitBtnLoading`: fundo `primaryDark`, `cursor: not-allowed`, `opacity: 0.7`
      - `credHint` (só tab login) — fundo `bgCard`, radius 8, borda 1px **tracejada** `borderStrong`
        - `credHintLabel` 12px/600 `textSecondary`
        - `credHintValue` 12px `textMuted`, fonte `mono`
    - `footer` — 12px `textMuted`, centrado; `footerBrand` em `primary`/600

## Copy exata

| Elemento | Texto |
|---|---|
| Logo glyph | `◈` |
| Título | `Recognition` |
| Subtítulo | `Visão computacional industrial para sua fábrica` |
| Tab 1 | `Entrar` |
| Tab 2 | `Criar Conta` |
| Placeholder nome | `Nome completo` |
| Placeholder e-mail | `seu@email.com` |
| Placeholder senha | `••••••••` |
| Placeholder confirmar | `Confirmar senha` |
| Erro client-side | `⚠️ As senhas não coincidem` |
| Erro API (401) | `⚠️ Credenciais inválidas` (mensagem vinda da API; fallback genérico: `Erro ao autenticar`) |
| CTA (tab login) | `Entrar` |
| CTA (tab register) | `Criar Conta` |
| CTA loading | `Aguarde...` |
| Hint label | `🔑 Acesso padrão:` |
| Hint valor | `admin@epimonitor.com / EpiMonitor@2024!` |
| Footer | `© 2026 Recognition · Logikos` |

## Dados de exemplo (fixtures dos screenshots)

- **error-api / loading (tab Entrar):** email `mariana.souza@rvbindustrial.com.br`, senha preenchida (16 bullets).
- **error (tab Criar Conta):** nome `Mariana Souza`, email `mariana.souza@rvbindustrial.com.br`, senha e confirmação divergentes → erro client-side.
- **Mock de API:** `POST /api/auth/login` → 401 raw `{error: 'Credenciais inválidas'}` para error-api; request pendurada (stall) para loading. `POST /api/auth/register` → catch-all do harness.

## Estados

- **default** — tab `Entrar` ativa; 2 inputs (email, senha); credHint visível.
- **tab-register** — tab `Criar Conta` ativa; 4 inputs (nome, email, senha, confirmar); credHint oculto.
- **error** — `errorBox` acima do CTA com validação client-side (senhas divergentes); só ocorre na tab register.
- **error-api** — `errorBox` com a mensagem da API (401). Trocar de tab limpa o erro (`setError(null)`).
- **loading** — CTA vira `Aguarde...`, `disabled`, fundo `primaryDark`, opacity 0.7; inputs permanecem editáveis.
- **hover** — **NÃO EXISTE**: `tabBtn` e `submitBtn` declaram `transition` mas nenhum seletor `:hover` (`Login.css.ts:72-90, 127-137`). Screenshots hover-* idênticos ao default.
- **focus (input)** — borda `primary` + `shadow.glow` (não capturado).
- **empty** — N/A (formulário estático, sem fetch de dados).

## Navegação e fluxos

- **Tab Entrar/Criar Conta** — alterna formulário e limpa `error`.
- **Submit (Entrar)** — `useAuth.login(email, password)`; sucesso → `isAuthenticated` vira true e o App monta `ThemeProvider > AppShell > AppLayout > AppRoutes` (aterrissa em `/modules` ou dashboard); falha → `errorBox`.
- **Submit (Criar Conta)** — valida `password === confirm` client-side; depois `useAuth.register(name, email, password)`.
- **Logout de qualquer tela** → sempre volta para esta tela (comentário no source: "logout SEMPRE leva aqui").
- Não há "Esqueci minha senha" nem SSO.

## Problemas identificados

1. **[P0]** Login renderiza sem classe de tema — todas as vars indefinidas; tela branca sem identidade, dark = light (`App.tsx:29-31` + `AppShell.tsx:33`). Classe WS1/task-063.
2. **[P1]** Credenciais padrão de admin (`admin@epimonitor.com / EpiMonitor@2024!`) expostas em produção na tela pública de login (`Login.tsx:92-97`).
3. **[P2]** Nenhum estado `:hover` em tabs e CTA (elementos interativos sem affordance).
4. **[P2 latente]** Pós-fix do tema, o CTA `textOnPrimary #ffffff` sobre `primary #06b6d4` dá **2.43:1** (15px/700 = texto normal, mínimo 4.5:1).
5. **[P3]** `credHintValue #668096` sobre `bgCard #161a20` = **4.23:1** (12px, mínimo 4.5:1) — levemente abaixo do AA no design pretendido.
6. **[P3]** Copy fora da marca: hint usa domínio `epimonitor.com` e senha `EpiMonitor@2024!` — produto chama-se Recognition.
7. **[P3]** White-label não se aplica pré-login (limitação documentada em `Login.css.ts:3-4` — branding vem do JWT): tenant claro vê login dark e app claro.

---

## Findings (develop — 2026-07-07)

| # | Severidade | Tema | Status | Descrição |
|---|---|---|---|---|
| 1 | P0 | both | **PERSISTS** | Login renderiza sem classe de tema — todas as vars vanilla-extract indefinidas; tela branca sem identidade visual. `dark-default` e `light-default` são **idênticos**: fundo branco, glyph "◈" em preto, título/subtítulo preto, tabs/inputs/CTA sem estilo. Commit WS1 (d7a3ad3) não corrigiu esta tela. |
| 2 | P1 | both | **PERSISTS** | Credenciais padrão de admin (`admin@epimonitor.com / EpiMonitor@2024!`) expostas publicamente no HTML da tela de login em produção (`Login.tsx:92-97`). |
| 3 | P2 | both | **PERSISTS** | Nenhum estado `:hover` em tabs e botão CTA (confirmado: hover screenshots idênticos ao default). |
| 4 | P2 | — | **LATENTE (pós-fix)** | Após o fix do tema: CTA `textOnPrimary #ffffff` sobre `primary #06b6d4` = 2.43:1 — abaixo do AA para texto normal (mínimo 4.5:1). |
| 5 | P3 | dark | **LATENTE (pós-fix)** | `credHintValue #668096` sobre `bgCard #161a20` = 4.23:1 (12px normal, mínimo 4.5:1) — levemente abaixo do AA. |
| 6 | P3 | both | **PERSISTS** | Copy fora da marca: hint expõe domínio `epimonitor.com` e senha `EpiMonitor@2024!` — produto se chama Recognition. |
