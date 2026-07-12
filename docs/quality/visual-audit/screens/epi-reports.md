# Relatórios (placeholder) — spec visual

**Rota:** `/epi/reports`
**Fontes:** `src/pages/ReportsPage.tsx` (componente inteiro — 15 linhas, 100% estilos inline, sem `.css.ts`)
**Screenshots:**

| Estado  | Dark                                          | Light (white-label claro)                      |
|---------|-----------------------------------------------|------------------------------------------------|
| default | `../screenshots/epi-reports/dark-default.png` | `../screenshots/epi-reports/light-default.png` |

> Página **placeholder estático**: sem chamadas de API, sem estados de dados, sem modais.
> Estados empty/loading/error/export não existem ainda (deferred — recapturar quando o
> módulo de relatórios for implementado).

## Layout — regiões

- **TopBar global** (shell): sticky 52px, breadcrumb `EPI / Relatórios`, sino de notificações,
  toggle Pro, "Auditor Visual" + badge de role, botão "Sair".
- **Conteúdo**: um único flex container centralizado vertical e horizontalmente
  (`display:flex; flexDirection:column; alignItems:center; justifyContent:center; flex:1; gap:16px`).
- **HealthFooter global** (shell): "Banco de dados / Redis / câmeras ativas".
- Sem sidebar expandida no snapshot (hamburger fechado). Sem grid próprio; tudo inline style.

## Árvore de componentes

```
ReportsPage
└── div (flex column centralizado, gap 16, color rgba(255,255,255,0.4))   ← hardcode
    ├── <FileBarChart size={48}/>            (ícone lucide, herda cor do container)
    ├── <h2> "Relatorios"                    (fontSize 20, fontWeight 700,
    │                                         color rgba(255,255,255,0.6))  ← hardcode
    └── <p>  "Em breve — export Excel, ..."  (fontSize 14, herda rgba(255,255,255,0.4))
```

Nenhum componente do UI kit é usado (sem Card, sem EmptyState, sem tokens `vars.*`).

## Copy exata

- Título (h2): `Relatorios` *(sem acento no source — o breadcrumb do shell exibe "Relatórios" com acento)*
- Parágrafo: `Em breve — export Excel, graficos de tendencia, compliance reports.` *(sem acentos em "graficos"/"tendencia")*

## Dados de exemplo

Nenhum — página estática, sem fixtures.

## Estados

- **default (único)**: ícone + título + parágrafo centralizados.
- Sem hover, sem foco, sem loading/empty/error.

## Navegação e fluxos

Nenhuma ação disponível. Chega-se pela navegação do módulo EPI (item "Relatórios").

## Problemas identificados

1. **P0 (light) — task-063**: todas as cores são `rgba(255,255,255,x)` inline. Sob superfície
   clara white-label (#f4f5f7) o conteúdo inteiro fica invisível — título 1.05:1, corpo/ícone
   1.03:1 (`ReportsPage.tsx:8-10`). Ver `light-default.png` (página aparentemente em branco).
2. **P2 (dark)**: parágrafo `rgba(255,255,255,0.4)` sobre `#0a0c10` = 3.78:1 — falha WCAG AA
   4.5:1 para texto de 14px.
3. **P3 — copy**: "Relatorios"/"graficos de tendencia" sem acentos; diverge do breadcrumb
   "Relatórios".
4. **P3 — design system**: placeholder ad-hoc 100% inline, fora do padrão de empty state do
   UI kit (usar tokens `vars.color.textMuted`/`textSecondary` num `.css.ts`).

---

## Findings (develop — 2026-07-07)

### Alterações visíveis no develop

Nenhuma alteração detectada. Página permanece placeholder estático idêntico ao baseline.

### Tabela de findings

| # | Sev | Tema | Status develop | Descrição |
|---|-----|------|---------------|-----------|
| 1 | P0 | light | **PERSISTS** | Conteúdo 100% invisível no light theme — `rgba(255,255,255,x)` hardcoded sobre fundo `#f4f5f7`; título 1.05:1, ícone/body 1.03:1. Confirmado em `light-default.png` (página em branco). WS1 não alcançou `ReportsPage.tsx`. |
| 2 | P2 | dark | **PERSISTS** | Parágrafo `rgba(255,255,255,0.4)` sobre `#0a0c10` = 3.78:1 — falha WCAG AA (4.5:1 para 14px) |
| 3 | P3 | both | **PERSISTS** | Copy sem acentos: `Relatorios`, `graficos de tendencia` — diverge do breadcrumb do shell `Relatórios` |
| 4 | P3 | both | **PERSISTS** | Componente 100% inline sem `.css.ts` e sem uso do UI kit — fora do padrão ADR |
