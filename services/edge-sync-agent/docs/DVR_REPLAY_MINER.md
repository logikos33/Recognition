# DVR Replay Miner (iNVD 3032) — runbook

Minerador de gravação histórica: puxa footage JÁ GRAVADA do gravador do site
(não live), por canal + janela de tempo, gateia por pessoa, recorta, filtra
(blur + quase-duplicata) e sobe cada recorte como `training_frame`
(`source='nvr'`, tag automática no servidor — ver
`services/api/app/api/v1/edge/routes.py`).

Código: `app/collector/replay_miner.py`. Testes: `tests/test_replay_miner.py`
(`pytest tests/test_replay_miner.py -v`, sem rede/ffmpeg/modelo real).

⚠️ **Este runbook descreve como RODAR no pandora (Jetson, na LAN do
gravador). NÃO rode a partir de uma máquina fora da VLAN do gravador — risco
de lockout anti-brute-force (ver seção Anti-lockout).**

## O que ele reusa (não reinventa)

- `RecorderClient.stream_clip()` (`app/recorder_client.py`,
  `app/rtsp_timestamp_recorder_client.py`) — mesmo contrato que a evidence
  API já usa para puxar clipe gravado.
- `PersonDetector`/`crop_person` (`app/collector/person_detector.py`) — mesmo
  gate YOLOX-nano/Apache-2.0 do coletor ao vivo.
- `upload_frame()` (`app/collector/frame_uploader.py`) → `POST
  /api/v1/edge/frames` — a MESMA rota do coletor ao vivo; o servidor já tagga
  `source='nvr'` sozinho, nada a mudar aqui.
- `load_counts`/`save_counts` (`app/collector/collector_state.py`) — reusado
  para persistir a cota por canal entre restarts (arquivo separado do
  coletor ao vivo: `COLLECTOR_STATE_PATH` != replay miner's `state_path`).
- `recorder_factory.build_recorder_client_from_env()` +
  `validate_onvif_boot_or_raise()` — MESMA construção/validação de boot que
  `main.py`/`app/collector/__main__.py` já usam.
- `is_auth_failure_message()` (`app/recorder_client.py`) — mesma heurística
  de 401/403 que `snapshot_executor.py` já usa para o breaker.

## URL de playback do iNVD 3032 (Dahua/Intelbras dialect)

```
rtsp://{user}:{pass}@{host}:{port}/cam/playback?channel={N}&starttime={YYYY_MM_DD_HH_MM_SS}&endtime={YYYY_MM_DD_HH_MM_SS}
```

Gerada por `RtspTimestampRecorderClient._build_playback_url` — timestamp
Dahua-dialect (`2012_09_15_12_37_05`), **NÃO** ISO 8601. Mesma
limitação documentada em `rtsp_timestamp_recorder_client.py`: não há índice
de timeline real neste fallback — "existe gravação nessa janela?" só se sabe
tentando tocar (`stream_clip`); janela vazia levanta `RecorderError` comum,
**não** é falha de autenticação.

## Como rodar (pandora)

```bash
cd /home/pandora/recognition/services/edge-sync-agent   # caminho real da release no box
export RECORDER_PROTOCOL=intelbras   # ou o que já está configurado em produção
export RECORDER_HOST=... RECORDER_PORT=554
export RECORDER_USERNAME=... RECORDER_PASSWORD=...     # NUNCA em argv, NUNCA logado
export EDGE_API_URL=https://api-v3-production-2b22.up.railway.app
export RECORDER_CLOUD_ID=<uuid de public.recorders>

# 1) DRY-RUN primeiro, sempre — não toca o gravador:
python3 -m app.collector.replay_miner

# 2) Campanha real: escrever um script curto que:
#    - constrói o RecorderClient (build_recorder_client_from_env + validate_onvif_boot_or_raise)
#    - monta camera_by_channel a partir do channel_map real do box
#    - build_sampling_plan(camera_by_channel, days=[...])
#    - ReplayMiner(...).mine(plan)
#    (nenhum entrypoint automático de "rodar de verdade" existe por
#    desenho — a campanha real é um passo humano deliberado, com CONFIRM,
#    não um cron.)
```

**Gate de confirmação:** não existe flag "--yes-i-am-sure" no módulo — a
ausência de um `main()` que já mina de verdade é intencional (a função
`main()` só roda o dry-run). Ligar a mineração real exige escrever/adaptar um
script curto no pandora, sinal de que é uma decisão humana explícita a cada
campanha, não um botão.

## Anti-lockout — garantias

- Uma ÚNICA credencial (`RECORDER_USERNAME`/`RECORDER_PASSWORD`), validada
  UMA VEZ no boot via `validate_onvif_boot_or_raise` (no-op para o protocolo
  RTSP fallback usado na RVB — o boot check estruturado só existe pro
  backend ONVIF; ver docstring da função).
- Qualquer 401/403 vindo de `stream_clip()` (detectado no texto do stderr do
  ffmpeg, mesma heurística de `snapshot_executor.py`) dispara
  `ReplayMiner.circuit_open = True` e **aborta a run inteira** — nenhuma task
  restante do plano é tentada, nenhum retry, nenhuma troca de credencial.
  Só um restart do processo (com credencial corrigida por um humano) religa.
- Janela vazia (sem gravação) **não** é tratada como falha de auth — é
  logada e a mineração segue pro próximo pull.
- Pacing de 3-5s (`pacing_s`, default 4s) entre TROCAS de canal — acesso
  sequencial, nunca paralelo.

## Reserva de disco

`has_disk_reserve(min_free_gb=8.0)` — mesmo teto do resto do edge
(`monitoring/store.py`). Este módulo não escreve nada em disco por desenho
(clipe decodificado só em memória, ADR-0033/0045); o guard existe para
abortar a campanha se o RESTO do box (buffer.db, staging de OTA, logs) já
tiver comido a reserva.

## Política por canal (decisão Vitor, 15/08 — ver `replay_miner.py`)

| Canal(is) | Política | Nota |
|---|---|---|
| 1 (máx. prioridade), 4, 11, 12, 19, 23, 28 | `full` | mineração completa |
| 8 | `ceiling` | teto de campanha (60 crops) — já concentrado (194 frames, 82% Botas) |
| 10 | `absence` | fonte de exemplos de AUSÊNCIA de EPI |
| 13, 14, 17, 18, 22, 25 | `excluded` | não extrai nada |
| 3, 27 | `quality_only` | módulo Qualidade — fora do dataset EPI |
| qualquer outro | `reduced` | teto de 1 crop/janela — não zera |

Tabela em `_CHANNEL_TABLE`/`policy_for_channel()` — **substitui** qualquer
ranking automático por volume já coletado.

## Limitações conhecidas (não verificadas sem hardware)

- `stream_clip()`/`_extract_frames_from_clip` nunca foram exercitados contra
  um DVR real nesta sessão (mesma pendência documentada em
  `rtsp_clip_stream.py`) — os testes provam a plumbing (Popen fake), não o
  comportamento real do ffmpeg contra o iNVD 3032.
- Limiar de blur (`_DEFAULT_BLUR_VARIANCE_MIN = 3000.0`) calibrado só contra
  fixtures sintéticos (checkerboard/gradiente/blur gaussiano) — precisa
  recalibração com recortes reais da RVB antes de confiar cegamente no
  descarte.
- Teto de concentração do canal 8 é uma cota de QUANTIDADE (60 crops),
  não uma fração real "40-50% de qualquer classe no dataset todo" — o miner
  não sabe a classe EPI do recorte (isso só existe depois da
  anotação/classificação). Ver comentário `ponytail:` em `ChannelRule` para
  o caminho de upgrade.
- A campanha real (rodar contra o gravador de verdade) é responsabilidade do
  Vitor, no pandora, dentro da VLAN — não foi executada nesta sessão.
