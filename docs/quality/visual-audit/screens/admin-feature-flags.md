# Feature Flags — spec visual

**Rota:** `/admin/feature-flags`
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminFeatureFlagsPage.tsx` · `admin.css.ts` · `types/admin.ts` (`FeatureFlag`) · service `adminService.getFeatureFlags()/updateFeatureFlag()` (GET `/api/v1/admin/feature-flags` → `{flags}`, PATCH `/api/v1/admin/feature-flags/{key}` `{value}`)
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/admin-feature-flags/dark-default.png` | `../screenshots/admin-feature-flags/light-default.png` |
| empty | `../screenshots/admin-feature-flags/dark-empty.png` | `../screenshots/admin-feature-flags/light-empty.png` |
| loading | `../screenshots/admin-feature-flags/dark-loading.png` | `../screenshots/admin-feature-flags/light-loading.png` |
| error | `../screenshots/admin-feature-flags/dark-error.png` | `../screenshots/admin-feature-flags/light-error.png` |
| saving | `../screenshots/admin-feature-flags/dark-saving.png` | `../screenshots/admin-feature-flags/light-saving.png` |
| hover toggle | `../screenshots/admin-feature-flags/dark-hover-toggle.png` | — (só dark) |

## Layout — regiões

- Shell AdminLayout padrão.
- `pageRoot` (padding 32, maxWidth 1200):
  - `pageHeader`: `pageTitle` "Feature Flags" + `pageSubtitle` "Flags globais da plataforma" (sem ações).
  - Card único (`s.card`) com a tabela — **usa corretamente `s.th`/`s.td`** (padding, bordas `borderSubtle`, headers alinhados à esquerda; referência positiva vs. tabela de roles).

## Árvore de componentes

```
AdminFeatureFlagsPage (pageRoot)
├── pageHeader → pageTitle "Feature Flags" + pageSubtitle
├── [error] alertBanner.danger
└── card
    ├── [loading] muted "Carregando..."
    └── table (th: Flag | Descrição | Última atualização | Valor)
        ├── tr por flag:
        │   ├── td mono flag_key (12px JetBrains Mono, textPrimary)
        │   ├── td muted description ?? '—'
        │   ├── td muted data pt-BR ?? '—'
        │   └── td botão-toggle: flag_value ? btnPrimary "Ativo" : btnGhost "Inativo"
        │        (inline fontSize 11, padding 3px 12px; disabled durante PATCH)
        └── [flags vazio] tr colSpan 4 centrado: muted "Nenhuma flag cadastrada"
```

## Copy exata

- `Feature Flags` · `Flags globais da plataforma`
- Colunas: `Flag`, `Descrição`, `Última atualização`, `Valor`
- Toggle: `Ativo` / `Inativo` · vazios: `—` · empty: `Nenhuma flag cadastrada` · loading: `Carregando...`
- Erro (fixture): `Falha ao carregar feature flags` · fallback `Erro ao atualizar flag`

## Dados de exemplo (fixtures)

| Flag | Descrição | Última atualização | Valor |
|---|---|---|---|
| platform.maintenance_mode | Bloqueia login de usuários não-superadmin durante manutenção | 12/06/2026 | Inativo |
| training.auto_approve | Aprova jobs de treinamento automaticamente (sem revisão manual) | 28/05/2026 | Inativo |
| alerts.email_notifications | Envia e-mail para admins do tenant a cada alerta crítico | 01/07/2026 | Ativo |
| monitoring.live_substream | Usa substream RTSP como padrão no live view | 04/07/2026 | Ativo |
| billing.enforce_camera_limit | Bloqueia cadastro de câmeras acima do limite do plano | 19/04/2026 | Ativo |
| branding.white_label | Habilita personalização de identidade visual por tenant (WS1) | — | Ativo |

## Estados

- **default:** 6 linhas; 4 Ativo (ciano) / 2 Inativo (ghost); flag sem `updated_at` mostra `—`.
- **empty:** cabeçalho da tabela permanece + linha única centrada `Nenhuma flag cadastrada` — sem CTA (flags são criadas por backend/migração, aceitável).
- **loading:** `Carregando...` muted, sem skeleton.
- **error:** banner danger acima do card; tabela vazia embaixo (mesmo padrão ambíguo de roles).
- **saving:** botão da linha clicada fica `:disabled` (opacity .5) — visível no dark-saving (linha alerts.email_notifications esmaecida); demais linhas seguem interativas; **update otimista**: o rótulo só troca depois do PATCH.
- **hover toggle:** opacity .85 do `btn` (sutil, mas presente).

## Navegação e fluxos

- Clique no botão de valor → PATCH `/api/v1/admin/feature-flags/{key}` com `!flag_value` → atualiza a linha localmente. **Sem confirmação** mesmo para flags de alto impacto (ex.: `platform.maintenance_mode` bloqueia login global).

## Problemas identificados

1. **P1 contraste (ambos):** toggle "Ativo" = `btnPrimary` `#fff` sobre `#06b6d4` a 11px/600 = **2.43:1** — o estado da flag é a informação central da tela.
2. **P2 controle ambíguo:** o botão mostra o **estado atual** ("Ativo") mas o clique executa a **ação oposta** (desativar) — padrão status-como-botão sem affordance de switch; sem confirmação para flags destrutivas (maintenance_mode).
3. **P3 copy:** `flag_key` técnico como identificador primário (mitigado pela coluna Descrição em pt-BR); "Última atualização" sem hora.
4. **P3 inconsistência:** estado error mantém a tabela vazia visível sob o banner (mesmo padrão de admin-roles).

## Findings (develop — 2026-07-07)

| # | Sev | Tema | Componente | Descrição | Status |
|---|-----|------|-----------|-----------|--------|
| F-1 | P1 | ambos | Toggle "Ativo" | #fff sobre #06b6d4 = 2.43:1 a 11px/600 — confirmado em dark/light-default.png | **persists** |
| F-2 | P2 | ambos | Botão de valor | Estado-como-botão sem affordance de switch; sem confirmação para flags destrutivas (maintenance_mode) | **persists** |
| F-3 | P3 | ambos | Copy | flag_key técnico como ID primário; "Última atualização" sem hora | **persists** |
| F-4 | P3 | ambos | Estado error | Tabela vazia visível sob banner de erro | **persists** |
| N-1 | P1 | light | Subtítulo / cabeçalhos th | **task-065 regression:** `vars.color.textMuted` = #8a8a93 → ~3.30:1 sobre bgSurface branca. Afeta "Flags globais da plataforma" (13px) e cabeçalhos "Flag / Descrição / Última atualização / Valor" — falha WCAG AA 4.5:1. | **new** |

**Resolved:** nenhum nesta passagem.
