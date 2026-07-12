# Fila de Verificação — spec visual

**Rota:** `/epi/verification`
**Fontes:** `apps/frontend/src/pages/VerificationQueuePage.tsx`, `apps/frontend/src/components/ui/{Skeleton,Toast}`, `lucide-react` (`ShieldAlert`, `CheckCircle`, `XCircle`, `RefreshCw`)
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (6 itens) | ../screenshots/verification-queue/dark-default.png | ../screenshots/verification-queue/light-default.png |
| empty | ../screenshots/verification-queue/dark-empty.png | ../screenshots/verification-queue/light-empty.png |
| loading | ../screenshots/verification-queue/dark-loading.png | ../screenshots/verification-queue/light-loading.png |
| error (500) | ../screenshots/verification-queue/dark-error.png | ../screenshots/verification-queue/light-error.png |
| hover "Confirmar" | ../screenshots/verification-queue/hover-btn-confirmar.png | — |
| hover "Rejeitar" | ../screenshots/verification-queue/hover-btn-rejeitar.png | — |

## Layout — regiões

- **Container**: `padding: 24`, `maxWidth: 800`, `margin: '0 auto'` (coluna central).
- **Header da página**: flex space-between, `marginBottom: 24` — esquerda: ícone `ShieldAlert` 22px (`primaryLight`) + `h2` "Fila de Verificação" (20px/700) + badge contador pill (bg `primaryDark`, texto `textPrimary`, radius 999, `2px 10px`, 12px/700); direita: botão "⟳ Atualizar" (transparent, borda `1px solid borderStrong`, radius 6, texto `textSecondary` 12px).
- **Subtítulo**: `p` 13px `textMuted`, `marginTop: -12`, `marginBottom: 20`.
- **Lista**: coluna flex `gap: 10`; cada item é um card horizontal `flex gap 16 align-start`, `padding: 16`, radius 10, `background: vars.color.bgBase`, `border: 1px solid vars.color.bgSurface` (token de SUPERFÍCIE usado como borda).
- **Card**: [coluna confiança fixa `minWidth 52`] + [conteúdo `flex:1`] + [ações `flex gap 6`].

## Árvore de componentes

- `VerificationQueuePage`
  - Header: `ShieldAlert` + `h2` (**`color:'#f1f5f9'` hardcoded**) + badge contador + botão Atualizar (sem hover)
  - `p` subtítulo
  - Empty state (se 0 itens): `textAlign center`, `padding '60px 20px'`, `color: textMuted`, **`border: 1px dashed vars.color.bgSurface`**, radius 12; `CheckCircle` 40px opacity 0.3; `p` "Fila vazia" (15px/600); `p` descrição (13px)
  - Item da fila (por alerta):
    - Indicador de confiança: `<NN>%` 18px/700 mono, cor por faixa — `<50% → '#ef4444'` hardcoded, `<70% → '#f59e0b'` hardcoded, `≥70% → vars.color.success`; label `confiança` 10px `textMuted`
    - Conteúdo: rótulo da classe (**`color:'#f1f5f9'` hardcoded**, 14px/600, via `classLabel()`) + separador `·` + nome da câmera (12px `textMuted`); linha `IA: <verification_reason>` (12px itálico `textSecondary`); timestamp `toLocaleString('pt-BR')` (11px, **`color: vars.color.borderStrong`** — token de borda como texto)
    - Ações: botão "✓ Confirmar" (bg `rgba(34,197,94,0.1)`, borda `rgba(34,197,94,0.3)` hardcoded, texto `vars.color.success`, radius 6, 12px/600, `title="Confirmar alerta"`) · botão "✗ Rejeitar" (bg `rgba(239,68,68,0.1)`, borda `rgba(239,68,68,0.3)`, texto **`'#ef4444'` hardcoded**, `title="Rejeitar alerta"`); ambos `opacity 0.5` quando `reviewing`; **sem hover**
  - Loading: `Skeleton title 220` + 4 blocos (`text 80%`, `text 55%`, `rect 120×28`) com `border: 1px solid transparent`
  - `Toast` (sucesso/erro de revisão)

## Copy exata

- Título: `Fila de Verificação` (+ badge com a contagem, ex. `6`)
- Botão: `Atualizar`
- Subtítulo: `Alertas que o agente IA classificou como ambíguos. Confirme ou rejeite abaixo.`
- Empty: `Fila vazia` · `Nenhum alerta aguardando revisão humana no momento.`
- Item: `confiança` · prefixo `IA: ` · botões `Confirmar` / `Rejeitar` · tooltips `Confirmar alerta` / `Rejeitar alerta`
- Rótulos de classe (`classLabel`): `no_helmet → Sem capacete`, `no_vest → Sem colete`, `no_gloves → Sem luvas`, `no_glasses → Sem óculos`, `helmet → Capacete detectado`, `vest → Colete detectado`; chave desconhecida cai crua na UI (fallback `labels[cls] ?? cls`)
- Toasts: `Alerta confirmado` · `Alerta rejeitado` · `Erro ao revisar alerta`

## Dados de exemplo (fixtures — 6 itens)

| conf | cor faixa | classe | câmera | verification_reason | timestamp |
|---|---|---|---|---|---|
| 42% | vermelho | Sem capacete | Câmera Pátio Norte | Oclusão parcial do capacete pela viga — não foi possível confirmar a violação | 06/07/2026, 23:27:33 |
| 55% | âmbar | Sem colete | Câmera Doca 2 | Baixa iluminação na zona de carga; colete pode estar presente | 06/07/2026, 23:20:33 |
| 63% | âmbar | Sem luvas | Câmera Almoxarifado | Mãos parcialmente fora do quadro durante a detecção | 06/07/2026, 23:08:33 |
| 68% | âmbar | Sem óculos | Câmera Portão Leste | Reflexo na lente pode ter sido confundido com ausência de óculos | 06/07/2026, 22:54:33 |
| 74% | verde | Sem capacete | Câmera Linha de Produção A | (sem reason) | 06/07/2026, 22:39:33 |
| 88% | verde | Sem colete | Câmera Oficina | EPI possivelmente presente, porém fora do padrão de cor do tenant | (rolado) |

## Estados

- **default**: 6 cards; polling `GET /verification/queue` a cada 15s.
- **loading**: skeletons (só na primeira carga; `setLoading(false)` permanece após o 1º fetch).
- **empty**: caixa central tracejada com check translúcido — informativo, sem CTA (aceitável: fila vazia é o estado desejado).
- **error (500)**: `catch` só loga no console → `items=[]` → renderiza **"Fila vazia"** — falso tudo-OK; único sinal é toast/console.
- **reviewing**: os dois botões do item com `opacity 0.5` + `disabled`; item some da lista após sucesso.
- **hover**: NENHUM elemento tem estado hover (screenshots hover-btn-confirmar/rejeitar idênticos ao default).

## Navegação e fluxos

- "Atualizar" → refetch imediato da fila.
- "Confirmar" → `POST /verification/<id>/review` `{verdict:'approve'}` → toast "Alerta confirmado" + remoção do item.
- "Rejeitar" → mesmo endpoint com `{verdict:'reject'}`.
- Sem links de saída; chega-se pela navegação do módulo EPI.

## Problemas identificados (resumo)

1. **P0 (light)**: título "Fila de Verificação" e rótulo de classe de cada item com `color:'#f1f5f9'` hardcoded — **1.00:1 no tema claro, invisíveis** (light-default). task-063.
2. **P0/P1 (both)**: timestamps usam `vars.color.borderStrong` como cor de texto — 1.58:1 no dark, 1.71:1 no light. Ilegíveis nos dois temas.
3. **P1 (both)**: bordas de card e do empty state usam `vars.color.bgSurface` (token de superfície) — 1.05:1 dark / 1.09:1 light: cards sem contorno perceptível.
4. **P1 (light)**: indicador de confiança âmbar `#f59e0b` 1.97:1 e texto "Confirmar" `success` sobre pill claro 2.15:1; "Rejeitar" `#ef4444` 3.04:1 — todos abaixo de 4.5:1 (texto 12–18px).
5. **P1 (both)**: erro 500 renderiza "Fila vazia" — falso estado saudável numa tela de segurança (fila de violações pode parecer zerada durante outage).
6. **P2 (both)**: hover ausente em Atualizar/Confirmar/Rejeitar; faixas de confiança com hex hardcoded em vez de `vars.color.danger/warning`.
7. **P2**: radius 999/12 fora da escala; página usa estilos inline ad-hoc em vez de `.css.ts` (única entre as 3 telas do grupo sem arquivo de estilos).

---

## Findings (develop — 2026-07-07)

### Alterações visíveis no develop

Nenhuma alteração detectada. Página idêntica ao baseline em todos os estados capturados (`dark-default.png`, `light-default.png`, hover screenshots).

Observação: em `dark-default.png` os timestamps ("07/07/2026, 09:34:54") aparecem como texto cinza médio mas ainda abaixo de 4.5:1 (token `borderStrong` não é cor de texto).

### Tabela de findings

| # | Sev | Tema | Status develop | Descrição |
|---|-----|------|---------------|-----------|
| 1 | P0 | light | **PERSISTS** | Título "Fila de Verificação" e rótulo de classe de cada item (`Sem capacete`, `Sem colete`, etc.) com `color:'#f1f5f9'` → 1.00:1 no light. Confirmado: `light-default.png` mostra itens sem rótulo de classe visível. task-063 incompleto em `VerificationQueuePage.tsx`. |
| 2 | P0 | both | **PERSISTS** | Timestamps com `vars.color.borderStrong` como cor de texto — 1.58:1 dark / 1.71:1 light. Token de borda ≠ token de texto; ilegível nos dois temas. |
| 3 | P1 | both | **PERSISTS** | Bordas de card e empty state com `vars.color.bgSurface` — 1.05:1 dark / 1.09:1 light; cards sem contorno perceptível |
| 4 | P1 | light | **PERSISTS** | Indicador âmbar `#f59e0b` 1.97:1; botão "Confirmar" `success` 2.15:1; "Rejeitar" `#ef4444` 3.04:1 — todos abaixo de AA para 12–18px |
| 5 | P1 | both | **PERSISTS** | Erro 500 → `items=[]` → renderiza "Fila vazia" — falso estado OK numa tela de segurança crítica. Único sinal é toast que some em segundos. |
| 6 | P2 | both | **PERSISTS** | Hover ausente em Atualizar/Confirmar/Rejeitar (`dark-hover-btn-confirmar.png` e `dark-hover-btn-rejeitar.png` idênticos ao default); faixas de confiança com `#ef4444`/`#f59e0b` hardcoded |
| 7 | P2 | both | **PERSISTS** | Radius 999 (badge)/12 (empty) fora da escala; `VerificationQueuePage.tsx` 100% inline sem `.css.ts` |
