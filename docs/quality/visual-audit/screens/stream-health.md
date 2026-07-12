<!-- HERDADO DA STAGING — revalidar no próximo run do develop -->

# Stream Health (Saúde do Sistema) — spec visual

**Rota:** `/epi/health` (`AppRoutes.tsx:58`) — breadcrumb do shell: `Saúde do Sistema`
**Fontes:** `src/pages/StreamHealthPage.tsx` (página inteira em inline styles — sem `.css.ts`), `src/components/shared/LoadingSpinner`
**Screenshots:**

| Estado | Dark | Light (white-label) |
|---|---|---|
| default | ../screenshots/stream-health/dark-default.png | ../screenshots/stream-health/light-default.png |
| degraded | ../screenshots/stream-health/dark-degraded.png | ../screenshots/stream-health/light-degraded.png |
| empty | ../screenshots/stream-health/dark-empty.png | ../screenshots/stream-health/light-empty.png |
| loading | ../screenshots/stream-health/dark-loading.png | ../screenshots/stream-health/light-loading.png |
| error | ../screenshots/stream-health/dark-error.png | ../screenshots/stream-health/light-error.png |
| hover Atualizar (dark) | ../screenshots/stream-health/dark-hover-atualizar.png | — |
| hover card câmera (dark) | ../screenshots/stream-health/dark-hover-camera-card.png | — |

## Layout — regiões

- **Container:** `padding: 24`, `maxWidth: 960`, `margin: 0 auto` (coluna central; laterais mostram o bg do layout).
- **Header da página:** flex space-between, `marginBottom: 28` — esquerda: ícone `Activity` 22px (`vars.color.primaryLight`) + h2 `Stream Health` (20px/700, **#f1f5f9 hardcoded**); direita: botão `Atualizar`.
- **3 seções empilhadas** (`marginBottom: 20`): cada uma é um painel `background: vars.color.bgBase`, `border: 1px solid vars.color.bgSurface` (token de fundo usado como borda), `borderRadius: 10`, `padding: 20`.
  1. **Status do Sistema** — linha de `StatusChip` (flex, gap 10, wrap).
  2. **Workers Celery** — tabela 3 colunas (ou vazio).
  3. **Câmeras** — grid `repeat(auto-fill, minmax(220px, 1fr))`, gap 12.
- Título de seção (`SectionTitle`): ícone 16px + h3 15px/700 **#f1f5f9 hardcoded**, `marginBottom: 14`.
- Sem modais/drawers. Auto-refresh a cada 15s.

## Árvore de componentes

```
StreamHealthPage
├─ LoadingSpinner                      (estado loading — página inteira)
├─ Header: Activity + h2 "Stream Health" + button "Atualizar" [RefreshCw 13px]
├─ Seção "Status do Sistema" [Server 16px primaryLight]
│  └─ StatusChip × 3: "Database" | "Redis" | "Gateway"
│     (pill radius 999, 12px/600, dot 7px; ok → verde, !ok → vermelho)
├─ Seção "Workers Celery" [Server 16px primaryLight]
│  ├─ p "Nenhum worker detectado."     (vazio)
│  └─ table (fontSize 13, th textMuted 600, borderBottom bgSurface)
│     colunas: Worker ID (mono 12px textSecondary) | Status (WorkerBadge pill "online"/"offline") | Tarefas Ativas
└─ Seção "Câmeras" [Video 16px #34d399 hardcoded]
   ├─ p "Nenhuma câmera cadastrada."   (vazio)
   └─ card por câmera (bg bgSurface, border borderStrong, radius 8, padding 14)
      ├─ linha 1: nome (13px/600 #f1f5f9 hardcoded, ellipsis) + badge "Online"/"Offline" (pill 11px/700)
      ├─ linha 2: localização (11px textMuted) — opcional
      └─ linha 3: "Gateway:" (12px textMuted) + "✓"/"✗" (success | #ef4444) + "TTL {n}s" (textMuted)
```

Cores dos chips/badges (StatusChip, WorkerBadge, badge Online/Offline — mesmo padrão triplicado inline):
- ok/online: `background rgba(34,197,94,0.1)`, `border rgba(34,197,94,0.3)`, `color vars.color.success` (#10b981) — dois verdes misturados (#22c55e no fundo/borda, #10b981 no texto).
- falha/offline: `background rgba(239,68,68,0.1)`, `border rgba(239,68,68,0.3)`, `color #ef4444` (hardcoded; token `danger` existe com o mesmo hex).

## Copy exata

- Título: `Stream Health` (inconsistente com o breadcrumb do shell `Saúde do Sistema` — inglês × português).
- Botão: `Atualizar`.
- Seções: `Status do Sistema`, `Workers Celery`, `Câmeras`.
- Chips: `Database`, `Redis`, `Gateway`.
- Tabela: `Worker ID`, `Status`, `Tarefas Ativas`; badges `online` / `offline`.
- Vazios: `Nenhum worker detectado.` / `Nenhuma câmera cadastrada.`
- Card de câmera: badge `Online` / `Offline`; `Gateway:` `✓`/`✗`; `TTL {n}s`.
- Não há NENHUMA mensagem de erro — falhas de API caem em `catch(() => null)` e a UI degrada silenciosamente para chips vermelhos + vazios.

## Dados de exemplo (fixtures do harness)

**default:** chips Database/Redis/Gateway verdes.

| Worker ID | Status | Tarefas Ativas |
|---|---|---|
| celery@worker-inference-01 | online | 3 |
| celery@worker-training-01 | online | 1 |
| celery@worker-extraction-01 | online | 0 |
| celery@worker-quality-02 | offline | 0 |

Câmeras (6, variadas): `Câmera Pátio Norte` — Pátio Norte — Galpão A — Online — Gateway ✓ — TTL 112s; `Câmera Doca de Carga 2` — Doca 2 — Expedição — Online — Gateway ✓ — TTL 87s; demais abaixo da dobra (fullPage).

**degraded:** Database verde, Redis e Gateway vermelhos; workers: inference-01 online 2, quality-02 offline 0; câmeras com mix Online/Offline e Gateway ✗.
**empty:** chips verdes + `Nenhum worker detectado.` + `Nenhuma câmera cadastrada.`
**error:** os 3 chips vermelhos + os dois textos de vazio (indistinguível de "sistema fora + nada cadastrado").

## Estados

- **loading:** `LoadingSpinner` global (primeira carga apenas; refresh de 15s é silencioso).
- **default:** tudo verde/online.
- **degraded:** chips vermelhos pontuais, worker offline, gateway ✗ — mesma estrutura.
- **empty / error:** ver acima — error não tem tratamento visual próprio.
- **hover:** NENHUM elemento tem hover (inline styles não suportam `:hover`): `dark-hover-atualizar.png` é pixel-idêntico ao default. Cards de câmera não são interativos (sem clique).
- A página NÃO expõe bitrate/FPS — apenas streaming/gateway_online/ttl_seconds.

## Navegação e fluxos

- `Atualizar` → refaz `GET /health`, `GET /streams/status`, `GET /cameras` e, por câmera, `GET /cameras/{id}/stream/status`.
- Auto-refresh: `setInterval(load, 15000)`.
- Nenhum link/modal/navegação a partir da página (beco terminal — sem atalho para Câmeras/Monitoramento).

## Contratos de API (fragilidade)

- `/health` e `/streams/status` são lidos na **raiz** da resposta (`healthRes.status`, `healthRes.checks`, `workerRes.workers` — linhas 124-134), enquanto `/cameras` e `/stream/status` seguem o envelope padrão `res.data`. Se o backend padronizar o envelope `{status:'success', data:{...}}` nesses dois endpoints, a página quebra silenciosamente (chips vermelhos falsos).

## Problemas identificados (resumo — detalhe no findings JSON)

1. **P0 hardcode (task-063, light):** `#f1f5f9` em h2/h3/nome de câmera → 1.0–1.1:1 sobre superfícies claras white-label; títulos invisíveis (`light-default.png`).
2. **P1 contrast (light):** texto dos chips/badges — verde #10b981 sobre rgba(34,197,94,.1)+claro = 2.15:1; vermelho #ef4444 = 3.04:1 (texto 11-12px).
3. **P2 hardcode/inconsistency (both):** `#ef4444` literal (token `danger` existe), verde de fundo #22c55e × verde de texto #10b981 no mesmo chip, `#34d399` no ícone Câmeras (1.76:1 no claro); pattern de pill triplicado inline em vez de componente `StatusBadge` compartilhado.
4. **P2 hover (both):** botão `Atualizar` sem hover/focus.
5. **P2 inconsistency (both):** página inteira em inline styles fora do design system (task-065); tokens de fundo usados como borda (`bgSurface`/`bgBase`) → separadores de tabela invisíveis.
6. **P2 inconsistency (both):** envelope lido na raiz para `/health` e `/streams/status`.
7. **P3 copy (both):** título `Stream Health` (EN) × breadcrumb `Saúde do Sistema` (PT); vazios/erro sem orientação de ação; erro indistinguível de vazio.
