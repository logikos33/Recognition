# Console de Teste E2E — spec visual

**Rota:** `/admin/test-console`
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminTestConsolePage.tsx` · `admin.css.ts` · `adminService.getTestConsoleStatus/startTestConsole/stopTestConsole/getIntegrations/upsertIntegration/getModelsForConsole`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (sessão running) | `../screenshots/admin-test-console/dark-default.png` | `../screenshots/admin-test-console/light-default.png` |
| empty (idle + Vast.ai não configurada) | `../screenshots/admin-test-console/dark-empty.png` | `../screenshots/admin-test-console/light-empty.png` |
| modal-add-integracao (form inline) | `../screenshots/admin-test-console/dark-modal-add-integracao.png` | `../screenshots/admin-test-console/light-modal-add-integracao.png` |

Obs.: os fullPage do default aparecem rolados até o fim (scrollIntoView do log); "modal-add-integracao" é um **form inline** dentro do card Integrações, não um modal.

## Layout — regiões

- Shell AdminLayout (sidebar ativa em **Console de Teste**). `pageRoot` → `pageHeader` (título + pill de status à direita) → banner condicional Vast.ai → `s.twoColumn` (grid 1fr 1fr, gap 24):
  - **Esquerda** (coluna flex, gap 16): card "Câmeras Simuladas" (range 1–28 + número 24px/700) · card "Modelo" (select full-width bgElevated) · card "Configuração de Cenário" (chips de classes, slider de limiar, input Zona/ROI) · linha de botões Iniciar/Parar (flex 1 cada).
  - **Direita**: `metricsGrid` forçado `repeat(2, 1fr)` com 4 `MetricBox` · card "Log da Sessão" (flex 1) com painel `background: rgba(0,0,0,0.3)` radius 6, padding 12, mono 11px, maxHeight 260, auto-scroll.
- **Card Integrações** (mt 24, largura total): header flex space-between → form inline condicional (`background: rgba(0,0,0,0.2)`, radius 8, padding 16, grid 2 col p/ Chave/Valor + Tenant ID + ações) → tabela de integrações.

## Árvore de componentes

- `pageTitle` "Console de Teste E2E" + `pageSubtitle`
- Pill de status (4px 10px, radius 6, 12px/600): running `rgba(34,197,94,0.15)`+success "● Em andamento" · stopped/idle `rgba(100,116,139,0.15)`+textMuted "◼ Parado"/"○ Idle"
- `alertBanner.warning` com `AlertTriangle` 16 + link-botão sublinhado (abre o form de integração)
- Chips de classe EPI (8): pill 3px 10px radius 12, 11px; selecionado = borda+texto `primary`, bg `rgba(59,130,246,0.15)`; não selecionado = borda borderSubtle, texto textMuted
- `MetricBox` (`s.metricCard`): ícone `Zap`/`Terminal` 14 + valor 22px/700 (danger se warn: VRAM > 85%) + `metricLabel`; `opacity: 0.5` quando inativo; borda `rgba(239,68,68,0.4)` se warn
- Botões: `btnPrimary` `Play` "Iniciar Teste"/"Iniciando..." · `btnDanger` `Square` "Parar"/"Parando..."
- Card Integrações: `cardTitle` "Integrações Configuradas" · `btnGhost` "+ Adicionar / Atualizar"/"Cancelar" · banners success/danger · form (2 inputs + password + tenant) · `btnPrimary` "Salvar (cifrado)" + microcopy · tabela th `Chave`/`Tenant`/`Atualizado`/`Status`, célula status "● configurada" (success 11px/600)

## Copy exata

- Título: `Console de Teste E2E` · Subtítulo: `Dispara e acompanha o teste ponta a ponta pela plataforma, sem terminal`
- Status: `● Em andamento` · `◼ Parado` · `○ Idle`
- Banner: `Configure sua chave Vast.ai em Administração → Integrações para habilitar instâncias de GPU cloud.` (trecho "Administração → Integrações" é botão sublinhado)
- Cards: `Câmeras Simuladas` (hint `1 a 28 câmeras simultâneas`) · `Modelo` (fallback `Pré-treinado (YOLOv8n base)`) · `Configuração de Cenário`
- Cenário: `Classes detectadas` (chips: helmet, no_helmet, vest, no_vest, gloves, no_gloves, glasses, no_glasses) · `Limiar de confiança: {n}%` · `Zona / ROI (descrição)` placeholder `ex: portão norte, linha de produção A...`
- Métricas: `Detecções/s` · `Latência ms` · `Throughput inf/s` · `VRAM %` (valor `—` sem sessão)
- Log: `Log da Sessão` + id da sessão (8 chars, mono) · vazio: `Nenhuma sessão iniciada.`
- Botões: `Iniciar Teste`/`Iniciando...` · `Parar`/`Parando...` · erros `Erro ao iniciar teste`/`Erro ao parar teste`
- Integrações: `Integrações Configuradas` · `+ Adicionar / Atualizar`/`Cancelar` · labels `Chave (ex: vast_ai)`, `Valor (cifrado ao salvar)` (placeholder `sk-...`), `Tenant ID (deixe em branco para usar o tenant do seu JWT)` (placeholder `UUID do tenant...`) · `Salvar (cifrado)`/`Salvando...` · microcopy `O valor nunca é retornado após salvar.` · sucesso `Integração salva com sucesso.` · validação `Valor é obrigatório` · vazio `Nenhuma integração configurada.`

## Dados de exemplo (fixtures)

- Sessão running: id `a3f8c2d1…`, 8 câmeras, modelo `mdl-epi-rvb-v3`; métricas 42.7 det/s · 187 ms · 96.3 inf/s · VRAM 71%.
- Log (6 linhas): `[14:02:11] Sessão a3f8c2d1 iniciada — 8 câmeras simuladas` · `[14:02:14] Instância Vast.ai provisionada (RTX 4090, 24GB)` · `[14:02:31] Modelo mdl-epi-rvb-v3 carregado em 6.2s` · `[14:03:02] Câmeras 1-8 conectadas — streams RTSP ok` · `[14:05:47] 2.418 detecções acumuladas · latência média 187ms` · `[14:09:12] VRAM 71% · throughput estável em 96 inf/s`
- Modelos: EPI RVB Industrial v3.1.0 · EPI Base Multi-tenant v2.4.0 · Fueling Detecção de Bico v1.0.2
- Integrações: `vast_ai` — Logikos (plataforma) — 03/07/2026 · `slack_webhook` — Tenant RVB Industrial — 22/06/2026
- Form preenchido no harness: chave `vast_ai`, valor mascarado (password `vast-9f83aa71bc55`).

## Estados

- **default/running**: pill verde, config desabilitada (slider/select/chips/inputs), "Iniciar" disabled, "Parar" ativo, métricas vivas (polling 3s), log com auto-scroll.
- **empty/idle**: pill "○ Idle", banner amarelo Vast.ai, métricas `0.0/0/0.0/0%` com opacity 0.5, log "Nenhuma sessão iniciada.", integrações "Nenhuma integração configurada.".
- **form aberto**: painel translúcido escuro com 3 campos + salvar.
- **warn**: VRAM > 85% → valor e borda em danger.
- **erro**: `alertBanner.danger` sob o header.

## Navegação e fluxos

- "Iniciar Teste" → `POST startTestConsole {camera_count, model_id, scenario_config}` → polling de status a cada 3s.
- "Parar" → `POST stopTestConsole`.
- Banner Vast.ai e "+ Adicionar / Atualizar" → abrem o form inline; "Salvar (cifrado)" → `upsertIntegration` → recarrega integrações + status.

## Problemas identificados

1. **P1 contraste (light)** — painel do log: `rgba(0,0,0,0.3)` sobre card branco vira cinza `#b2b2b2`, com texto `textMuted` (#6b7280 no light) = **2.28:1** (:438-441). No dark passa (4.71). O "console escuro intencional" (comentário allow) fixa só o fundo, mas deixa o texto seguir o tema — quebra no white-label claro.
2. **P2 hardcode/inconsistency (light)** — form de integrações `rgba(0,0,0,0.2)` (:485) vira slab cinza `#ccc` no light; labels textMuted = **3.01:1** e o painel destoa de qualquer superfície do sistema.
3. **P1 contraste (light)** — "● configurada" `vars.color.success` #10b981 11px/600 sobre branco = **2.54:1** (:587); pill "● Em andamento" success sobre `rgba(34,197,94,0.15)` clara = **2.23:1** (:222-226). No dark ambos ≥7.
4. **P2 hardcode** — chips selecionados usam `rgba(59,130,246,0.15)` (azul fixo) com texto `primary` ciano (:328): mistura de matiz fora da paleta; no light o chip fica **2.04:1**. Usar `primaryAlpha`.
5. **P2 hardcode** — pills de status com `rgba(34,197,94,0.15)`/`rgba(100,116,139,0.15)` (:222) e borda warn `rgba(239,68,68,0.4)` (:616) fora dos tokens (`successMuted`, `dangerMuted`).
6. **P3 copy** — banner manda ir a "Administração → Integrações", mas o botão abre um form na própria página — instrução e comportamento divergem.

---

## Findings (develop — 2026-07-07)

### Contexto de mudanças relevantes
- **WS1** (d7a3ad3): migração de tokens em ~70 telas. `AdminTestConsolePage` usa `admin.css.ts` para estrutura, mas os hardcodes de pills/chips/log/form de integração **não foram removidos**.
- **task-065**: `textMuted → #8a8a93` no professional. Melhora labels mas não resolve o background `rgba(0,0,0,0.3)` do log nem o `#10b981` do badge "configurada".
- **task-058** (admin-integrations-secrets): pode ter alterado o card de integrações, mas a análise visual não mostra mudança no fundo `rgba(0,0,0,0.2)`.

### Tabela de findings

| # | Sev | Descrição | Status |
|---|---|---|---|
| 1 | P1 | Log panel `rgba(0,0,0,0.3)` sobre branco → fundo ≈ `#b2b2b2`; texto `textMuted` ≈ 2.28:1 no light. Confirmado em `light-empty.png` ("Nenhuma sessão iniciada." em caixa cinza). | **PERSISTE** |
| 2 | P2 | Form de integrações `rgba(0,0,0,0.2)` vira slab cinza ≈ `#cccccc` no light; labels ≈ 3.01:1; destoa de qualquer superfície do sistema. Confirmado em `light-modal-add-integracao.png`. | **PERSISTE** |
| 3 | P1 | "● configurada" `#10b981` 11px/600 sobre branco = 2.54:1; pill "● Em andamento" success sobre tint verde ≈ 2.23:1. Ambos visíveis em `light-default.png` (tabela de integrações). | **PERSISTE** |
| 4 | P2 | Chips ativos usam `rgba(59,130,246,0.15)` (azul fixo) + texto `primary` (ciano) — matiz divergente; no light ≈ 2.04:1. Visível em `dark-default.png` e `light-default.png` (helm/no_helm/vest/no_vest ativos). | **PERSISTE** |
| 5 | P2 | Pills de status hardcoded `rgba(34,197,94,0.15)` / `rgba(100,116,139,0.15)`; borda warn `rgba(239,68,68,0.4)` fora dos tokens de semântica. | **PERSISTE** |
| 6 | P3 | Banner diz "Administração → Integrações" mas clique abre form inline na própria página — instrução e comportamento divergem. | **PERSISTE** |

### Novos findings (develop)

Nenhum finding novo identificado nos screenshots do develop.

### Resumo

- **Resolvidos:** 0
- **Persistem:** 6
- **Novos:** 0

### Notas de observação visual
- `dark-default.png` e `light-default.png`: capturados com scroll até a seção de Integrações; seção superior (pill de status, banner Vast.ai, controles de câmera) fora da viewport — não verificável diretamente.
- `dark-modal-add-integracao.png`: form inline em dark com background escuro translúcido — aceitável no tema escuro; problema concentrado no light.
- `light-modal-add-integracao.png`: slab cinza claramente visível e destoa do card branco ao redor.
