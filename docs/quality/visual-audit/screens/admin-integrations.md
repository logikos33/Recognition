# Integrações (self-service, superadmin) — spec visual

**Rota:** `/admin/integrations`
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminIntegrationsPage.tsx` (página inteira em estilos inline, **não usa** `admin.css.ts`) · `services/api.ts` — GET `/api/v1/admin/integrations/` (trailing slash obrigatório), PUT `/api/v1/admin/integrations/{type}`, POST `/api/v1/admin/integrations/{type}/test` · guard `useAuth().isSuperAdmin` (redirect `/admin` se não for)
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/admin-integrations/dark-default.png` | `../screenshots/admin-integrations/light-default.png` |
| empty | `../screenshots/admin-integrations/dark-empty.png` | `../screenshots/admin-integrations/light-empty.png` |
| loading | `../screenshots/admin-integrations/dark-loading.png` | `../screenshots/admin-integrations/light-loading.png` |
| error | `../screenshots/admin-integrations/dark-error.png` | `../screenshots/admin-integrations/light-error.png` |
| testing | `../screenshots/admin-integrations/dark-testing.png` | `../screenshots/admin-integrations/light-testing.png` |
| hover Salvar | `../screenshots/admin-integrations/dark-hover-salvar.png` | — (só dark) |
| hover Testar | `../screenshots/admin-integrations/dark-hover-testar.png` | — (só dark) |

## Layout — regiões

- Shell AdminLayout padrão; item "Integrações" ativo na sidebar (grupo RELATÓRIOS).
- Root inline: padding `24px 32px`, maxWidth **900** (≠ `pageRoot` 32px/1200 das demais páginas admin).
- Título `h1` 24px/700 (≠ `pageTitle` 20px) + subtítulo 14px `textSecondary`.
- Grid `repeat(auto-fill, minmax(380px, 1fr))`, gap 20 — 2 colunas em 1280px, 4 cards fixos (`CARD_SPECS`): R2, Vast.ai, GPU Genérico, Notificações.
- Card inline: bg `bgCard` (≠ `bgSurface` do `s.card`), borda `borderDefault`, radius 10, padding `20px 24px`, `boxShadow: 0 1px 4px rgba(0,0,0,.06)` hardcoded, flex column gap 12.
- **Inputs inline SEM `background`/`color`** → caem no default do user-agent: **fundo branco + texto preto mesmo no tema dark** (AdminIntegrationsPage.tsx:383-389).

## Árvore de componentes

```
AdminIntegrationsPage (root inline, superadmin only)
├── h1 "Integrações" + p "Credenciais armazenadas cifradas (Fernet). O plaintext nunca é exibido."
└── grid → 4× IntegrationCard(spec, current)
    ├── cardHeader: cardTitle 16px/600 + cardDesc 13px textSecondary
    │   + statusBadge 12px/600 à direita: "● Conectado" (success) | "● Erro" (#ef4444 hardcoded)
    │     | "○ Não configurado" (textMuted)
    ├── [last_tested_at] lastTested 12px textMuted "Último teste: {dd/mm/aaaa, hh:mm:ss}"
    ├── [status=error] errorMsg: 12px #ef4444 sobre dangerMuted, radius 6 — texto de last_error
    ├── form (flex column gap 10):
    │   ├── label 13px/500 "Label" + input (placeholder = type)
    │   ├── label(s) de config por spec + input
    │   └── label secret + span 11px textMuted "atual: ••••XXXX" + input type=password
    │         placeholder "Deixe vazio para manter atual" (autoComplete new-password)
    ├── actions: btnPrimary inline "Salvar"/"Salvando..." | btnSecondary inline "Testar conexão"/"Testando..."
    │     (Testar disabled se !current)
    └── [saveMsg|testMsg] feedback 13px/500 — success ou #ef4444
```

Specs dos 4 cards (`CARD_SPECS`):

| type | título | descrição | campos config | secret |
|---|---|---|---|---|
| r2 | Storage — Cloudflare R2 | Armazenamento de frames, modelos e datasets. | Endpoint (`https://ACCOUNT.r2.cloudflarestorage.com`), Bucket (`recognition-prod`) | Secret Access Key |
| vast_ai | Provedor GPU — Vast.ai | Treinamento de modelos YOLO em GPUs sob demanda. | GPU preferida (`RTX_3090`) | API Key |
| generic_gpu | GPU Genérico | Provedor GPU alternativo (SSH/API personalizado). | Endpoint SSH/API (`https://meu-gpu.exemplo.com`) | Token / Senha |
| notification | Notificações | Webhook ou chave para envio de alertas externos. | Webhook URL (`https://hooks.exemplo.com/...`) | Secret do Webhook |

## Copy exata

- `Integrações` · `Credenciais armazenadas cifradas (Fernet). O plaintext nunca é exibido.`
- Status: `● Conectado` · `● Erro` · `○ Não configurado`
- `Último teste: {data}` · `atual: ••••{last4}` · placeholder secret `Deixe vazio para manter atual`
- Botões: `Salvar` / `Salvando...` · `Testar conexão` / `Testando...`
- Feedback: `Salvo com sucesso` · `Conexão estabelecida com sucesso` · `Falha na conexão` · fallbacks `Erro ao salvar` / `Erro ao testar`
- Loading de página: `Carregando integrações...` · Erro de página: `Erro: {mensagem}` (fixture: `Serviço de integrações indisponível`)

## Dados de exemplo (fixtures — task-058)

| Card | Label | Config | Secret | Status | Último teste | last_error |
|---|---|---|---|---|---|---|
| R2 | R2 Produção RVB | endpoint `https://f8a2c1.r2.cloudflarestorage.com`, bucket `recognition-rvb-prod` | ••••4f2a | ok | 05/07/2026, 19:14:00 | — |
| Vast.ai | Vast.ai Treinos | gpu_type `RTX_4090` | ••••9c1e | error | 04/07/2026, 00:40:00 | Falha na autenticação: chave de API expirada |
| GPU Genérico | generic_gpu | {} | — | unconfigured | — | — |
| Notificações | Webhook Alertas Slack | webhook_url `https://hooks.slack.com/services/T0RVB/B44/xyz` | ••••b7d0 | ok | 06/07/2026, 08:02:00 | — |

## Estados

- **default:** 4 cards, secrets mascarados visíveis (`••••4f2a` etc. — task-058 OK, plaintext nunca no DOM), card vast_ai com faixa de erro vermelha.
- **empty:** integrations=[] → 4 cards todos `○ Não configurado`, labels default (`r2`, `vast_ai`…), placeholders visíveis, `Testar conexão` desabilitado (sem indicação visual de disabled — estilos inline não têm `:disabled`).
- **loading:** só o texto `Carregando integrações...` (sem shell de cards/skeleton).
- **error:** só o texto vermelho `Erro: Serviço de integrações indisponível` — página inteira substituída, sem retry.
- **testing:** botão vira `Testando...` (permanece com visual normal — sem spinner/opacity).
- **hover:** **nenhum efeito** em Salvar/Testar (estilos inline não expressam `:hover`; screenshots idênticos ao default).

## Navegação e fluxos

- Não-superadmin → redirect imediato para `/admin`.
- `Salvar` → PUT `/{type}` com `{label, config, secret?}` (secret só se digitado) → feedback + refetch.
- `Testar conexão` → POST `/{type}/test` → feedback ok/erro + refetch (atualiza status/último teste).

## Problemas identificados

1. **P1 tema (dark):** inputs sem `background`/`color` → **fundo branco com texto preto no tema dark** (todos os 12 inputs). Quebra total da identidade; classe task-063/065. Fix: usar `s.input` do kit (bg `bgElevated` + `textPrimary`).
2. **P1 contraste (light):** `● Conectado` `#10b981` sobre `bgCard` claro `#eceef1` = **2.18:1**; `● Erro` `#ef4444` = **3.24:1** — status é a informação principal do card.
3. **P1 contraste:** faixa `last_error` `#ef4444` 12px sobre `dangerMuted`: light **2.86:1**, dark **4.23:1** — reprova nos dois temas.
4. **P2 hardcode:** `#ef4444` literal em 4 pontos (statusColor, errorMsg, pageError, feedback) em vez de `vars.color.danger`; `boxShadow rgba(0,0,0,.06)` hardcoded (task-065).
5. **P2 inconsistência:** página inteira fora do design system — título 24px vs 20px, maxWidth 900 vs 1200, padding 24/32 vs 32, card `bgCard`/radius 10 vs `bgSurface`/radius 6, botões próprios em vez de `btnPrimary`/`btnGhost` do kit.
6. **P2 hover ausente:** botões inline sem estados `:hover`/`:disabled` (Testar desabilitado é indistinguível do habilitado no estado empty).
7. **P2 contraste (ambos, borderline):** `○ Não configurado` 12px/600 — dark `#668096` sobre `#161a20` = **4.23:1**, light `#6b7280` sobre `#eceef1` = **4.16:1**.
8. **P2 copy:** estado de erro da página é `Erro: {msg}` cru, sem instrução de recuperação nem botão de retry.
9. **P3:** loading sem skeleton; jargão "cifradas (Fernet)" no subtítulo é detalhe de implementação para o usuário.

## Findings (develop — 2026-07-07)

**Screenshots analisados:** dark-default, light-default, dark-empty, light-empty, dark-error, dark-loading, dark-testing, light-testing, dark-hover-salvar, dark-hover-testar
**Commits relevantes:** d7a3ad3 (WS1 design system — tokenizou superfícies e inputs), task-058 (secrets), task-065

### Findings resolvidos

| ID | Sev original | Descrição | Resolução |
|---|---|---|---|
| ~~F1~~ | ~~P1~~ | ~~Inputs sem `background`/`color` → fundo branco com texto preto no tema dark~~ | RESOLVED — WS1 (commit d7a3ad3): inputs agora usam bg tokenizado; dark-default.png confirma todos os 12 inputs com fundo escuro correto |

### Findings que persistem

| ID | Sev | Descrição | Evidência |
|---|---|---|---|
| F2 | P1 | `● Conectado` #10b981 sobre `bgCard` claro = 2.18:1; `● Erro` #ef4444 = 3.24:1 — status é informação principal do card | light-default — "● Conectado" verde de baixo contraste nos cards R2 e Notificações |
| F3 | P1 | Faixa `last_error` #ef4444 12px sobre `dangerMuted`: light 2.86:1, dark 4.23:1 — reprova nos dois | dark-default — faixa "Falha na autenticação: chave de API expirada" no card Vast.ai |
| F4 | P2 | `#ef4444` literal em 4 pontos (statusColor, errorMsg, pageError, feedback) em vez de `vars.color.danger` | code (task-065 alvo) |
| F5 | P2 | Página inteira fora do design system: título 24px vs 20px, maxWidth 900 vs 1200, padding divergente, card `bgCard`/radius 10 vs `bgSurface`/radius 6, botões próprios | dark-default vs demais páginas admin |
| F6 | P2 | Botões inline sem estados `:hover`/`:disabled` — `Testar conexão` desabilitado indistinguível do habilitado no empty | dark-hover-salvar/dark-hover-testar idênticos ao default |
| F7 | P2 | `○ Não configurado` 12px/600: dark #668096 = 4.23:1, light #6b7280 = 4.16:1 — borderline, reprova AA | light-default — card GPU Genérico |
| F8 | P2 | Estado de erro da página exibe `Erro: {msg}` cru, sem instrução de recuperação nem botão de retry | dark-error |
| F9 | P3 | Loading sem skeleton (só texto); jargão "cifradas (Fernet)" no subtítulo é detalhe de implementação | dark-loading |

### Findings novos

*(nenhum)*
