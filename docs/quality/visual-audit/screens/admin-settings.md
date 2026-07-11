# Configurações da Plataforma — spec visual

**Rota:** `/admin/settings`
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminSettingsPage.tsx` · `components/PermissionMatrixTable.tsx` · `hooks/usePermissions.ts` (cache em módulo + **catch vazio**) · service `adminService.getPermissionMatrix()` (GET `/api/v1/admin/permissions/matrix` → `{matrix: {permissão: role[]}}`)
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/admin-settings/dark-default.png` | `../screenshots/admin-settings/light-default.png` |
| empty | `../screenshots/admin-settings/dark-empty.png` | `../screenshots/admin-settings/light-empty.png` |
| loading | `../screenshots/admin-settings/dark-loading.png` | `../screenshots/admin-settings/light-loading.png` |
| error (idêntico ao empty) | `../screenshots/admin-settings/dark-error.png` | `../screenshots/admin-settings/light-error.png` |
| hover linha da matriz | `../screenshots/admin-settings/dark-hover-matrix-row.png` | — (só dark) |

## Layout — regiões

- Shell AdminLayout padrão.
- `pageRoot` (padding 32, maxWidth 1200):
  - `pageHeader`: `pageTitle` "Configurações da Plataforma" + `pageSubtitle` "Permissões e configurações globais" (sem ações à direita).
  - Card 1 (`s.card`, marginBottom 24): `cardTitle` uppercase "MATRIZ DE PERMISSÕES" + tabela (wrapper `overflowX:auto`).
  - Card 2 (`s.card`): `cardTitle` "SOBRE" + duas linhas `s.flex`.
- Tabela da matriz usa o kit corretamente (`s.table`/`s.th`/`s.td`): th 8px 12px textMuted/600 com borda inferior, td 10px 12px com borda `borderSubtle`. Células de role centralizadas (`textAlign:center` inline).

## Árvore de componentes

```
AdminSettingsPage (pageRoot)
├── pageHeader → pageTitle "Configurações da Plataforma" + pageSubtitle
├── card "MATRIZ DE PERMISSÕES"
│   ├── [loading] muted "Carregando..."
│   ├── [matrix] PermissionMatrixTable
│   │   └── table: th "Permissão" + 6 th de roles (superadmin|admin|operator|analyst|trainer|viewer)
│   │       tr por permissão: td s.mono chave técnica | 6× td centrado "✓" (textPrimary) ou "–" (muted)
│   └── [else] alertBanner.warning "Não foi possível carregar a matriz de permissões."
└── card "SOBRE"
    ├── flex: muted "Versão da plataforma" + mono "Recognition 2.0"
    └── flex (marginTop 8): muted "Desenvolvido por" + "Logikos"
```

## Copy exata

- `Configurações da Plataforma` · `Permissões e configurações globais`
- `Matriz de Permissões` (renderizada uppercase pelo `cardTitle`) · coluna `Permissão` · roles em inglês/lowercase: `superadmin`, `admin`, `operator`, `analyst`, `trainer`, `viewer`
- Células: `✓` / `–`
- Warning: `Não foi possível carregar a matriz de permissões.`
- Loading: `Carregando...`
- Sobre: `Versão da plataforma` → `Recognition 2.0` · `Desenvolvido por` → `Logikos`

## Dados de exemplo (fixture — 13 permissões × 6 roles)

| Permissão | superadmin | admin | operator | analyst | trainer | viewer |
|---|---|---|---|---|---|---|
| cameras:read | ✓ | ✓ | ✓ | ✓ | – | ✓ |
| cameras:write | ✓ | ✓ | ✓ | – | – | – |
| cameras:delete | ✓ | ✓ | – | – | – | – |
| alerts:read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| alerts:export | ✓ | ✓ | – | ✓ | – | – |
| training:read | ✓ | ✓ | – | – | ✓ | – |
| training:write | ✓ | – | – | – | ✓ | – |
| training:approve | ✓ | – | – | – | – | – |
| reports:read | ✓ | ✓ | – | ✓ | – | ✓ |
| reports:export | ✓ | ✓ | – | ✓ | – | – |
| admin:users | ✓ | ✓ | – | – | – | – |
| admin:roles | ✓ | – | – | – | – | – |
| admin:settings | ✓ | – | – | – | – | – |

## Estados

- **default:** matriz completa; card "Sobre" abaixo do fold em 720p (só 12 linhas visíveis).
- **empty (matrix null):** banner warning âmbar no lugar da tabela; card "Sobre" fica visível.
- **loading:** `Carregando...` muted; sem skeleton.
- **error (500):** **visualmente idêntico ao empty** — `usePermissions` engole a exceção (`.catch(() => {})`, usePermissions.ts:17) e o usuário vê o mesmo banner genérico, sem saber que houve falha de servidor nem como resolver.
- **hover linha:** **nenhuma mudança** (linhas não têm `trHover`) — aceitável pois as linhas não são interativas, mas o screenshot confirma ausência total de affordance.

## Navegação e fluxos

- Página somente leitura: nenhum botão, link ou ação. A matriz não é editável (roles built-in). Não há caminho para as roles customizadas (`/admin/roles`) a partir daqui.

## Problemas identificados

1. **P1 feedback de erro:** erro 500 na matriz é engolido silenciosamente (`catch` vazio em `usePermissions.ts:17`) — erro e vazio são indistinguíveis; banner diz o que aconteceu mas não por quê nem como resolver (sem retry). Cache em variável de módulo também nunca é invalidado após falha.
2. **P2 copy/i18n:** nomes de roles em inglês técnico (`superadmin`, `operator`, `viewer`…) e chaves de permissão cruas (`cameras:read`) numa UI toda em pt-BR.
3. **P3 a11y:** células usam apenas os glifos `✓`/`–` sem `aria-label`/texto acessível — leitores de tela leem "sinal de menos".
4. **P3 layout:** página estática sem nenhuma "configuração" editável apesar do título; card "Sobre" abaixo do fold.

## Findings (develop — 2026-07-07)

**Screenshots analisados:** dark-default, light-default, dark-empty, light-empty, dark-error, dark-loading, dark-hover-matrix-row
**Commits relevantes:** d7a3ad3 (WS1), task-065

### Findings resolvidos

*(nenhum — página read-only não foi escopo do WS1)*

### Findings que persistem

| ID | Sev | Descrição | Evidência |
|---|---|---|---|
| F1 | P1 | Erro 500 na matriz engolido silenciosamente (`catch` vazio em `usePermissions.ts:17`) — erro e empty indistinguíveis; banner sem instrução de recuperação nem retry | dark-error idêntico ao dark-empty |
| F2 | P2 | Nomes de roles em inglês técnico (`superadmin`, `operator`, `viewer`) e permissões como chaves cruas (`cameras:read`) em UI toda em pt-BR | dark-default, light-default — cabeçalhos da matriz |
| F3 | P3 | Células usam glifos `✓`/`–` sem `aria-label` — leitores de tela anunciam "sinal de menos" para negação | dark-default |
| F4 | P3 | Página sem nenhuma "configuração" editável apesar do título; link para `/admin/roles` ausente; card "Sobre" abaixo do fold em 720p | dark-default — "admin:settings" é última linha visível |

### Findings novos

*(nenhum)*
