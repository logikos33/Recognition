# Task 061 — Tuning de Latência do Live View (HLS ~40s → alvo ≤3-4s)

**Status**: PENDING (polimento — NÃO bloqueia o gate develop→staging da 059)
**Risk**: P1-ALTO (user-facing; toca FFmpeg + player + config de câmera)
**Branch**: fix/task-061-hls-latency-tuning

## Contexto (medido em teste real — 2026-07-06)

Live view funciona (task-059 fechada), mas com **~40s de delay** (cronometrado). Config da câmera
Intelbras (teste): Stream Extra H.265, 704×576, 25fps, **Intervalo I = 50 (GOP 2s)**. Teste via
nuvem + túnel pinggy (free) — parte da latência é o caminho de teste, não a arquitetura final (edge
local não tem túnel).

40s é grande demais pra ser só GOP → suspeita principal: **config do HLS no backend** (segmentos
acumulando / player ancorado no início do playlist em vez do live edge) + **H.265** (suporte fraco no
browser, força buffering).

## Fixes (por camada)

### Câmera (grátis, maior impacto imediato)
- Substream (usado no live view, `subtype=1`): **H.265 → H.264** (compat browser/hls.js — H.265 quebra
  fora do Safari). Registrar como recomendação padrão de onboarding (task-046).
- **Intervalo I = FPS** (ex.: 25fps → I=25 = 1s GOP), pra permitir segmentos de 1s no stream-copy.

### FFmpeg (backend)
- **CPU (crítico): usar STREAM-COPY, não re-encode.** Reportado uso alto de CPU com 1 câmera → sinal
  de que o FFmpeg está transcodando. Com a câmera agora em **H.264** (browser-compatível), usar
  `-c:v copy` (+ `-an` ou `-c:a copy`) — só reempacota em `.ts`, CPU ~idle. Re-encode (libx264) só se
  a origem não for H.264; evitar no tier API. Isto é também o alavancador de escala (28× re-encode
  derreteria a API).
- `hls_time 1`, `hls_list_size 2-3`, `hls_flags delete_segments+omit_endlist` (confirmar que deleta).
- Low-latency: `-fflags nobuffer -flags low_delay` e `-probesize/-analyzeduration` baixos no input RTSP.
- Stream-copy corta segmento só em keyframe → depende do GOP curto da câmera (I-interval = fps).
- Medir CPU/câmera antes/depois (esperado: de re-encode → ~idle com copy).

### hls.js (frontend)
- `lowLatencyMode: true`, `liveSyncDurationCount: 2` (ou 1), ancorar no **live edge** ao carregar
  (não tocar do início do playlist), `maxLiveSyncPlaybackRate` ~1.05 pra recuperar atraso.

## Aceite

- Confirmar `#EXTINF` dos segmentos ~1s após o fix (hoje verificar valor atual).
- Delay medido **em ambiente local/edge (sem túnel)** ≤ 3-4s. Medir separado do caminho nuvem+pinggy
  pra não confundir latência de teste com latência de arquitetura.
- H.264 no substream servido ao browser; player ancora no live edge.
- Suíte verde. PR pra develop.

## Nota de arquitetura

- Latência sub-segundo (tempo real) = **WebRTC**, não HLS — fora de escopo aqui; encaixa na task-060
  (gateway/edge). HLS ~2-4s é adequado pra monitoramento de EPI.
- Medir sempre no caminho de produção (edge local) — o túnel pinggy free adiciona latência/throttle
  que não existe na RVB.

## Referências

- task-059 (live view), task-060 (streaming de escala/WebRTC), task-046 (onboarding — recomendar H.264),
  `docs/product/VMS_MONITORING_UX.md`
