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

---

## S1 · CAMINHO B — o desenho, e por que o diff é pequeno

`inference_loop` (`services/api/app/infrastructure/queue/tasks/inference.py:1030`) **já é** o
pipeline inteiro que a missão descreve, e já roda na nuvem:

| etapa da missão | onde já existe |
|---|---|
| detector por câmera | `_get_detector_for_camera` (932) → `_resolve_camera_model` (749), cascata WS-A6 sobre `model_deployments` |
| escopo de classes | `_no_escopo_da_camera` (883) |
| polaridade (ADR-0065) | `_polaridade_do_tenant` (104) · `_polaridade_da_camera` (142) |
| portões / persistência temporal (ADR-0067) | `_regras_de_persistencia` (171) · `_persistencia_satisfeita` (225) |
| violação | `_has_violation` (300) |
| alerta + evidência | `_save_alert` (554) |
| parar quando ninguém quer | `_is_stream_active` (93), lê `epi:stream:{cam}:active` |

**A única amarra ao RTSP é uma linha:** `cap = cv2.VideoCapture(rtsp_url)` (1069).

### O diff do Caminho B

1. **Trocar a fonte de frame**: em vez de `VideoCapture(rtsp_url)`, ler o `.ts` mais recente de
   `epi:edge_hls:{camera_id}:*` (binário, `get_segments_redis_binary()`) e decodificar dele.
   O `epi:stream:{cam}:active` que já governa o loop é **a mesma chave** que faz o box empurrar —
   um gatilho serve aos dois.
2. **Keepalive** das 14 câmeras: manter `epi:stream:{cam}:active` vivo (é o que o live view humano
   já faz; a chave tem TTL e já houve bug de expiração — `stream_handlers.py:44`).
3. **Badge + latência**: carimbar procedência "AO VIVO" e medir instante-do-segmento → evento.

⛔ Zero código no `services/edge-sync-agent` ⇒ **zero OTA no box na véspera do dia D**.
E de quebra fecha o elo do #519 pelo lado certo: a nuvem deixa de precisar de RTSP.

### ⚠️ Riscos deste desenho (declarados, não resolvidos)
- Segmento tem **TTL ~20s** — consumidor lento perde frame. Cadência de 1 frame/2-3s cabe, mas sem folga grande.
- 14 câmeras × ~0,4 fps = ~5-6 inferências/s de RF-DETR em CPU. **Projeção ainda NÃO medida** — é o gate do "CPU aguenta vs pod RunPod (teto US$ 2)".
- `_HLS_SEGMENT_TTL` e o custo de decodificar `.ts` por segmento ainda não medidos.

---

## S3 · Prontidão — o que já está PROVADO por código

### ✅ Salvar escopo por câmera reflete no pipeline NA HORA (mecanismo provado)

Cadeia completa, lida ponta a ponta:

1. `POST /api/cameras/<id>/model-config` publica no canal
   (`services/api/app/api/v1/cameras/model_config_handlers.py:86` — `r.publish(f"camera:model_change:{camera_id}", "1")`).
2. `inference_loop` assina esse canal (`inference.py:989`) e drena a cada volta (`1003`).
3. `_invalidate_camera_detector` (921) faz `pop` da entrada inteira do cache.
4. O escopo mora **na mesma entrada** (`_camera_detectors[cam]["classes"]`, lido em 883) — logo
   invalidar o modelo invalida o escopo junto. ⛔ Não há cache separado de escopo para ficar velho.

Falta a prova AO VIVO (a matriz do Paulo salva na tela e o alerta muda na hora) — depende do S1
estar de pé, então é a mesma evidência.

---

## ⏭️ PRÓXIMO PASSO
1. Medir a projeção de CPU (decodificação `.ts` + RF-DETR) → decide nuvem vs pod.
2. Implementar a troca de fonte de frame + keepalive + badge/latência.
3. Bench de usuários e roteiro do dia D com URL exata por passo → contrato do congelamento.

## 📓 Nota de método
Três agentes de inventário (pipeline · prontidão · calibração) rodaram ~7 min e ~570k tokens
**e voltaram sem relatório** ("Idle." / "Aguardando." / "Sem ação pendente."). O levantamento
acima foi feito à mão. Registrado para não repetir a aposta.
