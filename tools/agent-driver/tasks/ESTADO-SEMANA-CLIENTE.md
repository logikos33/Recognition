# ESTADO — SEMANA DO CLIENTE (dia D: quarta 02/09)

> 1º ato de toda sessão: `git fetch` + ler este arquivo do `origin/develop`. Ele MANDA sobre o prompt.
> Pista: **semana do cliente** (tempo real + prontidão). A outra pista é a **migração do front**.
> Worktree: `mutirao/semana-cliente-tempo-real` (de `origin/develop`).

## Marcos

| marco | estado |
|---|---|
| **S0** · reconhecimento do terreno | ✅ 29/08 — box de pé, mecanismo do ao-vivo entendido, rotas mapeadas |
| **S1** · Caminho B — ausência AO VIVO no DEV | ⏳ desenho fechado, não implementado |
| **S2** · calibração pelos vereditos do Vitor | ⏳ bloqueado — depende das 121 revisadas |
| **S3** · prontidão 02/09 (bench, escopo, roteiro, backup) | ⏳ |
| **S4** · cenário / zonas visuais | ⏳ só se o reexport chegar |

## 🔴 Custo acumulado: **US$ 0,00** (teto RunPod desta missão US$ 2 — nenhum pod disparado)

---

## S0 · O TERRENO, MEDIDO (29/08, ~17:50 BRT)

### O box está de pé e ocioso — e isso muda o desenho do Caminho B

`ssh pandora@100.93.126.76` (Tailscale). **31 dias de uptime**, load 0,14 — praticamente ocioso.

| serviço (systemd --user) | estado | o que faz |
|---|---|---|
| `edge-live-view.service` | running | **RTSP → HLS → push pra nuvem** |
| `edge-frame-collector.service` | running | coleta motion-triggered, "Onda 2 shadow mode" |
| `edge-sync-agent.service` | running | identidade + evidence/discovery API + sync |
| `edge-monitoring-collector.service` | running | 7 camadas → ring buffer SQLite |
| `edge-telemetry-collector.service` | running | tegrastats → JSONL |

Uso de CPU dos processos: `app.main` 0,5% · `app.collector` 0,0% · `app.live_view` 4,0%.

### ⭐ O ao-vivo já existe, e é SOB DEMANDA — a nuvem não puxa, o box empurra

Prova nos dois lados:

- **Log do box** (`~/logs/edge-live-view.log`, ao vivo): `GET .../api/v1/edge/live-view/wanted → 200` a cada ~2,3 s, e **nada mais**.
- **Log da API DEV**: o mesmo poll, `bytes=57` — payload vazio. Ninguém está assistindo, então o box não transcodifica nada.
- **Código** (`services/edge-sync-agent/app/live_view/`): `hls_transcoder.py` · `live_view_loop.py` · `segment_pusher.py`. O device precisa do escopo `stream:write`.

**Consequência de desenho:** o Caminho B ⛔ NÃO precisa que a nuvem alcance a câmera (ela não alcança — MikroTik/WireGuard, ADR-0020). Precisa apenas **colocar as 14 câmeras na lista `wanted`** e consumir os segmentos que já chegam à nuvem. O caminho ao-vivo é o mesmo do live view humano — só que o consumidor passa a ser o pipeline, não o navegador.

### ⚠️ O box está 11 dias atrás da develop

`readlink ~/recognition/current` → release **`b8668b72`** (OTA nº 3, ~18/08).

Delta medido `app/` do box × `origin/develop`: falta **`detection_relay.py`** no box (ADR-0064, mergeado 23/08 no #529).

**Consequência:** ⛔ qualquer código novo que eu escreva em `services/edge-sync-agent` **NÃO roda no box sem OTA**. Se o Caminho B puder ser feito 100% do lado da nuvem, evitamos um OTA na véspera do dia do cliente — que é o que eu quero.

### Estado da outra pista (sincronização do dia)

A `develop` andou **9 commits durante o meu primeiro levantamento** (#556→#563, thread do vigia de proveniência), e o DEV entrou em deploy às 20:48Z com `230f7382`. As duas pistas estão de fato convivendo.

- Sessão par `frontend-migration-logikos-bd4acf-26` — contatada, sincronização pedida (o que está em voo, admin/usuários no front novo, dono da aba de escopo).
- Deploys do DEV são **automáticos por merge na develop** — não existe "não deployar" sem "não mergear". O congelamento de terça 18h é, na prática, **congelamento de MERGE**.

### Contrato de rotas — o front novo vive sob `/novo` (medido em `RotasNovas.tsx`)

Existe HOJE no front novo: `/novo/epi/dashboard` · `/novo/epi/live` · `/novo/epi/eventos` ·
`/novo/epi/eventos/:id` · `/novo/epi/verificacao` · `/novo/epi/acoes` · `/novo/epi/cameras` ·
`/novo/epi/cameras/:cameraId/operations` · `/novo/epi/relatorios` · `/novo/quality/*` ·
`/novo/carga` · `/novo/modules`.

⛔ **NÃO existe tela de admin/usuários no front novo.** Logo o passo de cadastro ao vivo do dia D
cai no front **ANTIGO**, salvo se a outra pista provar uma tela nova até terça.

---

## ⏭️ PRÓXIMO PASSO
1. Fechar os 3 inventários em curso (pipeline de ausência · prontidão 02/09 · calibração).
2. Decidir onde o pipeline ao vivo roda: nuvem consumindo segmento empurrado (preferido, sem OTA) vs box.
3. Roteiro do dia D com URL exata por passo → vira o contrato do congelamento.
