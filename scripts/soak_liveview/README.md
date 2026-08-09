# Soak do live view — harness da caça ao congelamento (04/08)

Reproduz localmente, em minutos, o ciclo completo que em produção leva **1 hora**
para falhar: mint dos tokens de playback → consumo HLS → renovação proativa →
expiração → recuperação. Foi um soak mais curto que o TTL do token que deixou
três rodadas anteriores passarem "limpas" com o bug vivo — **o soak tem que
durar ≥ 3× o TTL do token de playback em vigor**.

## Peças

| Arquivo | Papel |
|---|---|
| `synthetic_edge.py` | Câmera edge sintética: 1 FFmpeg (lavfi testsrc) → HLS deslizante → espelho pro Redis (`epi:edge_hls:{camera_id}:*`) para N câmeras, com a disciplina do edge corrigido (segmentos antes da playlist). Sem NVR, sem enrollment. |
| `../../apps/frontend/src/test/e2e/soak-liveview.spec.ts` | O soak instrumentado no CLIENTE: `video.currentTime` 1×/s por player, status HTTP de todo request de `/stream/`, URL da página (detecção do `/login`). Aceites: nunca navega p/ login; zero 401; todo player avança com maior stall < `SOAK_MAX_STALL_S`. |

## Receita (local, macOS)

```bash
# 0. Pré: postgres e redis locais rodando; ffmpeg no PATH; npm install no frontend.
createdb recognition_soak

# 1. API com TTLs CURTOS (12 min de playback → soak de 40 min = 3,3× TTL)
cd <repo>
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES   # macOS: fork do gunicorn
export SERVICE_TYPE=api PORT=5001 \
  DATABASE_URL=postgresql://$USER@localhost:5432/recognition_soak \
  REDIS_URL=redis://localhost:6379/0 SEGMENTS_REDIS_URL=redis://localhost:6379/0 \
  JWT_SECRET_KEY=<32+ chars> SECRET_KEY=<32+ chars> \
  CAMERA_SECRET_KEY=<fernet key> \
  HLS_PLAYBACK_TOKEN_TTL=720 TENANT_CONTEXT_TTL_MINUTES=10 \
  ALLOW_EPHEMERAL_STORAGE=1
python3 railway_start.py           # roda as migrations e sobe o gunicorn

# 2. Seed + câmeras
SEED_DEV=1 SEED_ADMIN_PASSWORD='<senha>' DATABASE_URL=... python3 scripts/seed_dev.py
# criar N câmeras via POST /api/cameras {name, host, manufacturer, username, password}
# e guardar os UUIDs (o RTSP nunca é discado — o caminho edge-fed curto-circuita).

# 3. Câmera sintética
python3 scripts/soak_liveview/synthetic_edge.py \
  --redis redis://localhost:6379/0 --camera-ids "uuid1,uuid2,..."

# 4. Soak (o webServer do Playwright sobe o vite em :3001 sozinho)
cd apps/frontend
SOAK_PASSWORD='<senha>' SOAK_MINUTES=40 npx playwright test soak-liveview --timeout=0

# 5. (Recomendado) Injeção de falha nas janelas de renovação — simula a
#    cascata de SIGTERM dos deploys que matou a corrente de renovação em 04/08:
sleep 420 && pkill -n -f gunicorn   # mata o WORKER (o master respawna em ~5s)
```

## Interpretação

- A linha do tempo sai em `soak-liveview-timeline.jsonl` (`kind:sample` =
  amostras de vídeo; `kind:http` = requests de stream com token redigido).
- **Congelamento** = `currentTime` parado; o aceite falha se a maior janela
  parada passar de `SOAK_MAX_STALL_S` (45 s default — cobre a recuperação da
  injeção de falha; o bug original era stall TERMINAL + logout).
- **Logout** = qualquer amostra com página `/login` → falha imediata.
- Ausência de `.ts` no log stderr do servidor NÃO prova ausência de tráfego
  (WARNING+ vai pro stderr desde o #301) — por isso a medição é no cliente.

## Por que TTLs curtos são honestos

`HLS_PLAYBACK_TOKEN_TTL` e `TENANT_CONTEXT_TTL_MINUTES` são as MESMAS variáveis
lidas pelo código de produção; o frontend ancora renovação no `exp` real (da
URL/JWT), não em constantes espelhadas — então encurtar o TTL comprime o relógio
do cenário sem trocar nenhum caminho de código. ⛔ Não usar TTL curto como
"correção" em produção — nem TTL longo: o certo é renovar, e é isso que o soak
prova.

## Soak contra o DEV remoto (câmeras reais RVB)

Aprendizados da rodada D-74/D-78 (2026-08-09):

- As câmeras reais entregam **HEVC** no stream principal (D-79) — o Chromium bundled do Playwright NÃO
  decodifica (tráfego pleno, `currentTime` em 0). Rode com o Chrome de verdade, headed:
  `channel: 'chrome'`, `headless: false`, e `--autoplay-policy=no-user-gesture-required`.
- Aponte `baseURL` pro frontend DEV e desligue o `webServer` do playwright.config quando o alvo é remoto.
- Mantenha a máquina acordada (`caffeinate -dimsu npx playwright test ...`) — display/App Nap geram
  janelas de silêncio de HTTP que viram "stall" falso na métrica.
- Espectador = o próprio Playwright; sem ele o edge não transmite (LV-3) e não há tráfego pra medir.
- Stall SINCRONIZADO em todos os players + janela sem NENHUMA request no navegador + push contínuo no
  log do box = problema do caminho cliente↔Railway, não do sistema (ver D-78).
