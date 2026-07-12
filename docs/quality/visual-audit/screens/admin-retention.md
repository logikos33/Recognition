# Tiers de Retenção — spec visual

**Rota:** `/admin/retention`
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminRetentionPage.tsx` · `admin.css.ts` · `adminService.getTenants/updateTenant`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/admin-retention/dark-default.png` | `../screenshots/admin-retention/light-default.png` |
| empty | `../screenshots/admin-retention/dark-empty.png` | `../screenshots/admin-retention/light-empty.png` |
| edit-tier (TierSelector inline) | `../screenshots/admin-retention/dark-edit-tier.png` | `../screenshots/admin-retention/light-edit-tier.png` |

## Layout — regiões

- Shell AdminLayout (nenhum item da sidebar corresponde à rota).
- `pageRoot` → `pageHeader` (só título+subtítulo, sem ação) → **card "Referência de Tiers"** (mb 24) → banner de erro condicional → **card da tabela de tenants**.
- Referência de Tiers: grid `repeat(4, 1fr)`, gap 12; cada box: `padding: 12px 14px; borderRadius: 8; border: 1px borderDefault; background: bgSurface`.
- TierSelector (inline na célula "Retenção atual" quando editando): grid `repeat(4, 1fr)`, gap 8, container `minWidth: 320`; botão de tier: `padding: 10px 8px; borderRadius: 6`; selecionado = borda `2px solid primary` + bg `rgba(37,99,235,0.07)`; não selecionado = borda 1px borderDefault + bg transparente.

## Árvore de componentes

- `pageTitle` "Tiers de Retenção" + `pageSubtitle` (texto longo, ver copy)
- Card referência: `cardTitle` "REFERÊNCIA DE TIERS" + 4 boxes, cada um com: linha `Clock` 13px (textMuted) + label do tier (14px/700 — **cor bugada, ver problemas**) · descrição (12px, textPrimary) · texto de conformidade (11px, textSecondary)
- Card tabela: th `Tenant` · `Plano` · `Retenção atual` · `Conformidade` · (ações, width 120)
  - Tenant: nome (600) + slug (11px, textMuted)
  - Plano: `s.planBadge[plan]` (basic cinza / standard azul / premium roxo / enterprise âmbar)
  - Retenção atual (view): `s.badge` inline `background: rgba(37,99,235,0.08); color: primary` com `Clock` 10px — "{n} dia(s)"; badge "Salvo" verde (`rgba(34,197,94,0.1)` + success) após salvar
  - Retenção atual (edit): `TierSelector` (4 botões: label 15px/700 + descrição 11px textMuted)
  - Conformidade: 12px textSecondary, maxWidth 260
  - Ações: view → `btnGhost` "Editar" (4px 10px, 12px); edit → `btnPrimary` "Salvar" (ícone `Save` 11) + `btnGhost` "Cancelar"

## Copy exata

- Título: `Tiers de Retenção`
- Subtítulo: `Configura por quantos dias as evidências (frames/clipes) de cada tenant são retidas no R2. Tiers: 1, 7, 30 e 90 dias.`
- Card: `Referência de Tiers` (renderizado uppercase)
- Tiers (label · descrição · compliance):
  - `1 dia` · `Mínimo operacional` · `Não recomendado para LGPD — ciclo de auditoria insuficiente`
  - `7 dias` · `Padrão básico` · `Retenção mínima para auditoria semanal`
  - `30 dias` · `Padrão recomendado` · `Cobre ciclo mensal de inspeções e auditorias internas`
  - `90 dias` · `Conformidade estendida` · `Adequado para auditorias externas e requisitos LGPD mais rigorosos`
- Badge retenção: `{n} dia` / `{n} dias` · badge pós-save: `Salvo`
- Botões: `Editar` · `Salvar` / `Salvando…` · `Cancelar`
- Carregando: `Carregando tenants...` · Vazio: `Nenhum tenant encontrado.` · Erro: `Erro ao salvar retenção`
- Conformidade sem tier exato: `—`

## Dados de exemplo (fixtures)

| Tenant (slug) | Plano | Retenção | Conformidade |
|---|---|---|---|
| Tenant RVB Industrial (rvb-industrial) | enterprise | 90 dias | Adequado para auditorias externas e requisitos LGPD mais rigorosos |
| Construtora Horizonte Sul (horizonte-sul) | premium | 30 dias | Cobre ciclo mensal de inspeções e auditorias internas |
| Metalúrgica São Carlos (metalurgica-sao-carlos) | standard | 7 dias | Retenção mínima para auditoria semanal |
| Agroindústria Vale Verde (vale-verde) | basic | 1 dia | Não recomendado para LGPD — ciclo de auditoria insuficiente |
| Transportadora Andrade & Filhos (transportadora-andrade) | standard | 30 dias (default — campo ausente) | Cobre ciclo mensal... |

## Estados

- **default**: todas as linhas em modo view (badge + Editar).
- **edit-tier**: primeira linha com TierSelector inline (4 opções, "90 dias" selecionada em ciano) + Salvar/Cancelar.
- **saving**: botão "Salvando…" desabilitado.
- **saved**: volta ao modo view com badge verde "Salvo".
- **empty**: linha "Nenhum tenant encontrado." · **loading**: "Carregando tenants...".
- **erro**: `alertBanner.danger` acima da tabela.

## Navegação e fluxos

- "Editar" → troca a célula para TierSelector (estado por linha).
- Clique num tier → atualiza `draftDays` local.
- "Salvar" → `PUT updateTenant {video_retention_days}` → view + badge Salvo.
- "Cancelar" → descarta draft e volta ao valor original.

## Problemas identificados

1. **P0 contraste (ambos os temas)** — `AdminRetentionPage.tsx:61` e `:196` usam **`vars.color.bgSurface` como cor de TEXTO** nos labels dos tiers ("1 dia", "7 dias", "30 dias", "90 dias"). O texto fica sobre fundos iguais ou quase iguais ao próprio valor (`bgSurface` no card de referência; transparente sobre `bgSurface` no TierSelector) → **ratio 1.00:1 — invisível nos dois temas**. Nas capturas, os 4 boxes de referência e 3 dos 4 botões do seletor aparecem SEM o label do tier; só a opção selecionada (cor `primary`) é legível. Operador não consegue distinguir as opções de 1/7/30/90 dias.
2. **P1 contraste (light)** — badge "Retenção atual": `primary` #06b6d4 (11px/600) sobre `rgba(37,99,235,0.08)` sobre branco = **2.18:1**.
3. **P2 hardcode** — `rgba(37,99,235,0.07)` (:55) e `rgba(37,99,235,0.08)` (:259) são azul blue-600 fixo fora da identidade ciano; usar `vars.color.primaryAlpha`. Também `rgba(34,197,94,0.1)` (:267) em vez de `vars.color.successMuted`.
4. **P3 copy** — badges de plano exibem a chave crua em inglês (`enterprise`, `premium`, `standard`, `basic`).

## Findings (develop — 2026-07-07)

| # | Sev | Tema | Componente | Descrição | Status |
|---|-----|------|-----------|-----------|--------|
| F-1 | P0 | ambos | TierSelector / Referência | Labels "1 dia"/"7 dias"/"30 dias"/"90 dias" usam `vars.color.bgSurface` como cor de texto → 1.00:1 invisível. Confirmado em dark/light-edit-tier.png: somente opção selecionada (ciano) é legível. | **persists** |
| F-2 | P1 | light | Badge "Retenção atual" | #06b6d4 11px/600 sobre rgba(37,99,235,0.08) sobre branco = 2.18:1 — confirmado em light-default.png | **persists** |
| F-3 | P2 | ambos | TierSelector bg / badge Salvo | rgba(37,99,235,0.07/.08) azul blue-600 hardcoded; rgba(34,197,94,0.1) verde hardcoded — usar `primaryAlpha`/`successMuted` | **persists** |
| F-4 | P3 | ambos | Badges de plano | Chaves cruas inglês (enterprise/premium/standard/basic) | **persists** |
| N-1 | P1 | light | Subtítulo / texto Conformidade | **task-065 regression:** `vars.color.textMuted` = #8a8a93 → ~3.30:1 sobre bgSurface branca. Afeta subtítulo longo 13px e coluna "Conformidade" 12px textSecondary — falha WCAG AA 4.5:1. | **new** |

**Resolved:** nenhum nesta passagem.
