# Handoff: Redesign To-Be — Logikos Vision

## Visão geral
Redesign completo do SaaS Logikos Vision (visão computacional sobre CFTV industrial), aprovado em 3 lotes em 04/08/2026: shell único multi-módulo, jornada EPI (8 telas), módulo Qualidade integrado (telas aprovadas + Retrabalho/Câmeras), módulo Carga unificado, Estúdio (persona técnica, gateado) e modo TV. Jornada-mestra de todo módulo: DETECTAR → TRIAR → AGIR → PROVAR — nenhuma tela mostra detecção sem oferecer o próximo passo.

## Sobre os arquivos de design
Os arquivos `.dc.html` deste pacote são **referências de design em HTML** (protótipos navegáveis — abra no navegador; `support.js` e `lk-loader.js` na mesma pasta). **Não são código de produção.** A tarefa é recriá-los no frontend real do repo `Recognition` (`apps/frontend`: React 18 + TypeScript + Vite, Zustand, Radix UI, HLS.js), usando os padrões existentes e preservando a ponte de white-label (ThemeProvider → `/v1/tenant/branding` → CSS vars).

## Fidelidade
**Alta (hi-fi).** Cores, tipografia, espaçamentos, medidas e copy são finais — recriar pixel-perfect. As barras "ESTADO"/"DEMO" flutuantes no canto inferior esquerdo são artefato de demonstração: NÃO implementar.

## Tokens (contrato — nunca hex solto em componente)
```css
--lk-preto:#0A0A0F;        /* fundo */
--lk-grafite:#14141C;      /* superfícies, topbar, sidebar, cards */
--lk-borda:#23242F;        /* bordas 1px, divisores */
--lk-branco-sinal:#F4F6F8; /* texto principal, logo */
--lk-cinza-nevoa:#8A8F98;  /* secundário, labels overline */
--lk-ciano-visao:#00E5FF;  /* SÓ interativo: ativo, foco, primário, playhead. ≤10%, nunca fundo */
--lk-ciano-profundo:#0091AD; /* hover/pressed do acento */
--lk-magenta-glitch:#FF2E63; /* SÓ franja de glitch do loader */
--st-ok:#3ECF8E;  --st-atencao:#E8A13C;  --st-nc:#E5484D; /* estado = cor + ícone + palavra, sempre */
```
Telas aprovadas do Qualidade usam #FFB020/#FF5C47 — na implementação convergem para --st-atencao/--st-nc via token.

Tipografia 3 vozes (Google Fonts): **Space Grotesk** 500/700 (títulos, números grandes, wordmark LOGIKOS), **Inter** 400/500/600 (UI), **JetBrains Mono** 400/500/700 (dados, códigos, timers, labels overline uppercase tracking .16–.22em). Zero escrita grega em UI. Zero jargão de ML fora do Estúdio.

## Medidas do shell
TopBar 56px · sidebar 236px (64px colapsada) · item de nav 38px (borda esquerda 2px ciano no ativo) · banner admin 42px + faixa 2px âmbar · conteúdo max-width 1280px, padding 24px · raio 8–12px · grid 8pt · palette ⌘K 600px · botões de veredito ≥48px (verificação ≥56px).

## Telas (arquivo ↔ rota ↔ fase)
| Arquivo | Rota | Fase |
|---|---|---|
| Shell Logikos Vision.dc.html | shell global (TopBar/sidebar/admin/sessão/⌘K) | F1 |
| Logikos Loading.dc.html + lk-loader.js | todos os estados de espera | F1 |
| Kiosk RVB.dc.html (aprovado) | /tablet/:station — fora do shell | F2 |
| EPI Dashboard.dc.html | /epi/dashboard | F3 |
| EPI Ao Vivo.dc.html | /epi/live | F3 |
| EPI Eventos.dc.html | /epi/eventos | F3 |
| EPI Evento Detalhe.dc.html | /epi/eventos/:id | F3 |
| EPI Ações.dc.html | /epi/acoes | F3 |
| EPI Verificação.dc.html | /epi/verificacao | F3 |
| EPI Câmeras.dc.html | /epi/cameras | F3 |
| EPI Relatórios.dc.html | /epi/relatorios | F3/F5 (digest) |
| Qualidade.dc.html (+ Gestão/Revisão/Configuração aprovadas) | /quality/* | F4 |
| Carga.dc.html | /carga/* | F4 |
| Estúdio.dc.html | /estudio/* | F5 |
| TV RVB.dc.html | /tv/:site | F5 |
| Admin Plataforma.dc.html | /admin/* (visão geral, tenants + white-label, usuários/reset, dispositivos, share links, auditoria) | F5/F6 |
| Acesso Logikos.dc.html | /login, /esqueci-senha, troca obrigatória | F5 |
| Mobile EPI.dc.html | mobile <768px — eventos/ações só leitura | F3 |

## Interações e estados
- Toda rota: carregado / loading (LogikosLoader) / vazio (EmptyState com CTA) / erro (com retry). Estúdio soma SEM PERMISSÃO.
- LogikosLoader (`lk-loader.js`, conceito C2 "tranca de cofre"): variantes fullscreen/tile/spinner≤24px; estados entering·waiting·retry·resolving·idle; glitch 0,4–0,6s SÓ em entrada/retry/saída; steps(8); CSS vars --lk-tick-dur/--lk-steps/--lk-glitch-dur; prefers-reduced-motion → pulso de opacidade. Portar como componente React com a MESMA máquina de estados.
- Motion global: curto, seco, steps(), termina em repouso. Nunca loop decorativo.
- Ack de evento sempre botão explícito; seleção múltipla com barra de ações.
- Detalhe do evento: faixa 24h clicável (scrubbing), Prev/Próx câmera vizinha, veredito máx. 3 escolhas (Confirmar/Descartar/Criar ação), Compartilhar com expiração 1h/24h/7d e permissão ver/ver+baixar.
- Verificação: atalhos ← → C R A; "A" envia para a fila de anotação do Estúdio.
- Ao Vivo: presets 2×2/3×3/4×3 + colunas 2–6 + modo DESTAQUE (1 grande + trilho); overlay de detecção com toggle; em ≥5 colunas o status vira só ponto e labels de bbox somem.
- Validação de contagem (Carga): contado vs manual editável; decisão explícita registrada com autor/hora.
- Sessão expirando: aviso 5 min antes, countdown mono, Renovar/Sair.
- ⌘K: câmeras, eventos, telas, ações — com atalhos exibidos.

## Estado / dados
Dados de exemplo nos protótipos refletem o formato real do backend (site RVB Isolantes — Blumenau; CAM-01/04/07; classes capacete/colete/óculos/luvas; score 87 vs 82; ação "Reforçar DDS na doca" — Carlos M. — 08/08; sessão {ABC-1D23, 142 vs 140}; modelo {mAP@50 0.91, precisão 0.94, recall 0.88}). Nada de reconhecimento facial, mapa de calor ou áudio.

## Assets
- Logo O-fechadura e monograma Λ: geometria SVG canônica embutida em `lk-loader.js` e nos topbars (máscaras `keyhole`/`lam`). Nunca distorcer/recolorir/sombrear.
- Ícones: SVG stroke 1.7, cantos retos (stroke-linecap square) — na implementação, usar lucide-react configurado nesse estilo (F1 já prevê lucide no lugar de emojis).

## Arquivos
Todos os `.dc.html` desta pasta + `support.js` (runtime de preview) + `lk-loader.js`. Os três `Handoff LOTE N.dc.html` documentam componentes EXISTENTE/ESTENDIDO/NOVO, estados e responsivo por lote. Prompts prontos por fase em `prompts/`.
