# Aprovações de Treinamento — spec visual

**Rota:** `/admin/training-approvals`
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminTrainingApprovalsPage.tsx` · `components/TrainingApprovalCard.tsx` · `admin.css.ts` · `adminService.getTrainingApprovals/approveTraining/rejectTraining`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (filtro pending) | `../screenshots/admin-training-approvals/dark-default.png` | `../screenshots/admin-training-approvals/light-default.png` |
| empty | `../screenshots/admin-training-approvals/dark-empty.png` | `../screenshots/admin-training-approvals/light-empty.png` |

Modais de aprovar/rejeitar usam `window.prompt()` nativo — não capturáveis em screenshot (deferred).

## Layout — regiões

- Shell AdminLayout (sidebar ativa em **Aprovações**, badge vermelho "3" no item).
- `pageRoot` → `pageHeader` → linha de filtros (`s.flex`, mb 16) → grid de cards `repeat(auto-fill, minmax(320px, 1fr))`, gap 16 → paginação condicional (`total > 20`).

## Árvore de componentes

- `pageTitle` "Aprovações de Treinamento" + `pageSubtitle` "{total} registros"
- Filtros (5 botões): valor ativo = `btnPrimary`, demais = `btnGhost` — `pending` · `approved` · `rejected` · `auto_approved` · `Todos` (string vazia)
- `TrainingApprovalCard` (`s.card`):
  - Linha 1: nome do job (600) + "{tenant} · módulo: {module}" em `muted`; badge à direita `s.badge` inline `background: rgba(249,115,22,0.15); color: #ea580c` com texto fixo **"Pendente"**
  - Métricas (`s.twoColumn`, 12px, mb 12): `mAP50 {x}%` · `mAP50-95 {x}%` · `Dataset {n} imgs` · `Épocas {n}` (cada label em `muted`; célula some se métrica ausente)
  - Ações (só se `status === 'pending'`): `btnSuccess` `CheckCircle` "Aprovar" · `btnDanger` `XCircle` "Rejeitar"
- Card vazio: `s.card` com `muted` "Nenhuma aprovação encontrada"

## Copy exata

- Título: `Aprovações de Treinamento` · Subtítulo: `{total} registros`
- Filtros: `pending` · `approved` · `rejected` · `auto_approved` · `Todos`
- Card: `{job_name}` · `{tenant_name} · módulo: {module}` · badge `Pendente` · labels `mAP50`, `mAP50-95`, `Dataset` (`{n} imgs`), `Épocas`
- Botões: `Aprovar` · `Rejeitar`
- Prompts nativos: `Notas de aprovação (opcional):` · `Motivo da rejeição (obrigatório):` · erro `Erro`
- Vazio: `Nenhuma aprovação encontrada` · Carregando: `Carregando...`
- Paginação: `Anterior` · `Pág {n}` · `Próxima`

## Dados de exemplo (fixtures — 5 cards pending)

| Job | Tenant · módulo | mAP50 | mAP50-95 | Dataset | Épocas |
|---|---|---|---|---|---|
| EPI RVB — dataset v4 (capacete/colete) | Tenant RVB Industrial · epi | 91.2% | 74.4% | 4820 imgs | 120 |
| EPI Canteiro — luvas e óculos | Construtora Horizonte Sul · epi | 86.1% | 65.2% | 2140 imgs | 80 |
| Fueling — bico e placa v2 | Transportadora Andrade & Filhos · fueling | 88.3% | 70.1% | 1675 imgs | 100 |
| EPI Fundição — retreino trimestral | Metalúrgica São Carlos · epi | 79.4% | 58.8% | 980 imgs | 60 |
| Qualidade — inspeção de solda | Tenant RVB Industrial · quality | 92.8% | 80.2% | 3410 imgs | 150 |

## Estados

- **default**: filtro `pending` ativo (btnPrimary ciano), 5 cards com Aprovar/Rejeitar.
- **empty**: um único card "Nenhuma aprovação encontrada" no grid.
- **carregando**: `Carregando...`.
- **erro**: `alertBanner.danger`; falha de ação → `alert()` nativo.
- Filtros `approved`/`rejected`/`auto_approved`: cards sem botões de ação (mas badge continua "Pendente" — bug, ver problemas).

## Navegação e fluxos

- Filtro → recarrega `GET /api/v1/admin/training-approvals?status=...&page=n` (20/página).
- "Aprovar" → `prompt()` p/ notas opcionais → `approveTraining(id, notes)` → reload.
- "Rejeitar" → `prompt()` p/ motivo obrigatório (cancela se vazio) → `rejectTraining(id, reason)` → reload.

## Problemas identificados

1. **P1 copy/estado** — badge do card tem texto fixo `Pendente` (TrainingApprovalCard.tsx:21), ignorando `approval.status`: ao filtrar por `approved`/`rejected`/`auto_approved`, todos os cards continuam rotulados "Pendente".
2. **P2 contraste (both)** — badge "Pendente": `#ea580c` hardcoded (11px/600) sobre `rgba(249,115,22,0.15)` = **4.29:1 no dark** e **3.05:1 no light** (AA exige 4.5 p/ texto pequeno). Usar `vars.color.accent`/`accentAlpha` com tom ajustado por tema.
3. **P2 copy** — filtros exibem chaves cruas em inglês (`pending`, `approved`, `rejected`, `auto_approved`) misturadas com "Todos" em pt-BR; módulo também em chave (`epi`, `fueling`, `quality`).
4. **P2 a11y-other** — Aprovar/Rejeitar via `window.prompt()`/`alert()` nativos: fora do kit (ADR-0023), sem branding, sem validação visível, impossível de tematizar.
5. **P3 layout** — empty state é um card solto no grid (ocupa 1 coluna de 320px) sem CTA nem ícone — beco em vez de convite.

---

## Findings (develop — 2026-07-07)

### Contexto de mudanças relevantes
- **WS1** (d7a3ad3): `AdminTrainingApprovalsPage` e `TrainingApprovalCard` usam `admin.css.ts`. WS1 pode ter migrado a estrutura de `card`/`pageRoot` mas os hardcodes do badge `Pendente` (cor e texto) não foram abordados.
- **task-065**: `textMuted → #8a8a93` no professional. Melhora labels de métricas mas não resolve badge hardcode.
- Nenhuma das tasks (063/067/068) é relevante para esta página.

### Tabela de findings

| # | Sev | Descrição | Status |
|---|---|---|---|
| 1 | P1 | Badge texto fixo "Pendente" em `TrainingApprovalCard.tsx` — ignora `approval.status`. Ao filtrar por approved/rejected/auto_approved os cards ainda exibem "Pendente". Confirmado: todos os 5 cards em `dark-default.png` e `light-default.png` mostram badge "Pendente". | **PERSISTE** |
| 2 | P2 | Badge "Pendente": `#ea580c` 11px/600 sobre `rgba(249,115,22,0.15)` = 3.05:1 no light (abaixo de 4.5:1 AA). Confirmado em `light-default.png`. | **PERSISTE** |
| 3 | P2 | Filtros exibem chaves cruas em inglês (`pending`, `approved`, `rejected`, `auto_approved`); apenas "Todos" em pt-BR. Confirmado em ambos os temas. | **PERSISTE** |
| 4 | P2 | Aprovar/Rejeitar via `window.prompt()`/`alert()` nativos — sem branding, sem validação visual, fora do kit ADR-0023. | **PERSISTE** |
| 5 | P3 | Empty state é um card 320px sem ícone nem CTA. Confirmado em `dark-empty.png` e `light-empty.png`. | **PERSISTE** |

### Novos findings (develop)

Nenhum finding novo identificado nos screenshots do develop.

### Resumo

- **Resolvidos:** 0
- **Persistem:** 5
- **Novos:** 0

### Notas de observação visual
- `dark-default.png` (thumbnail reduzido): grade visível com 5 cards; badges "Pendente" laranja uniformes; botões Aprovar (verde) e Rejeitar (vermelho) presentes. Layout responsivo auto-fill funciona corretamente.
- `light-default.png`: mesma grade em tema claro; badge "Pendente" com fundo laranja-tint e texto `#ea580c` — contraste baixo confirmado visualmente.
- `dark-empty.png` / `light-empty.png`: card solitário "Nenhuma aprovação encontrada" em largura ~320px; sem ícone, sem orientação ao superadmin.
