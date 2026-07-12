# Task 068 — Detecção de stream travado/offline + backoff de polling + higiene de log

**Status**: PENDING (robustez + UX + custo; recomendado antes do go-live)
**Risk**: P1-ALTO (live view; toca lifecycle/watchdog e observabilidade)
**Branch**: fix/task-068-stream-stall-offline-detection

## Contexto (observado nos logs — 2026-07-07)

O frontend faz `GET /stream/stream.m3u8` a cada ~1s **indefinidamente**. Com o stream travado
(câmera desconectada / túnel caiu / FFmpeg estagnou), a playlist **não avança** → **304 por 60s+
seguidos, sem nenhum 200**. Três problemas:

1. **Sem detecção de stall/offline:** usuário vê frame congelado; falta estado "Câmera offline /
   reconectando" (SLC — Completo/Amável).
2. **Polling mantém stream morto vivo:** `serve_hls` renova o TTL a cada GET (GR-2), então o watchdog
   NUNCA marca inativo e NUNCA mata o FFmpeg morto. Liveness amarrada em "cliente pediu", não em
   "stream produzindo".
3. **Log poluído + desperdício:** 1 req/s pra sempre floods o INFO e gasta API/log storage.

## Fixes

### Detecção de stall
- Considerar o stream **travado** se a `#EXT-X-MEDIA-SEQUENCE`/nº de segmento **não avança** por N s
  (ex.: 10-15s). Ao detectar: marcar offline, tentar reconnect/restart do FFmpeg com backoff, e
  **parar de renovar o TTL** (deixar o watchdog limpar o processo morto).
- Basear a liveness no **avanço real de segmentos**, não só no request do cliente.

### UX (SLC)
- Player mostra **"Câmera offline / reconectando…"** (estado claro), não frame congelado. Se voltar,
  religa sozinho. Mensagem empática, não erro cru.

### Polling backoff (frontend)
- Backoff no intervalo de poll quando travado (ex.: 1s → 2s → 5s) em vez de martelar 1s.
- **Pausar o poll com a aba oculta** (Page Visibility API) e **parar no unmount** (liga com task-062).

### Higiene de log
- Requests de rotina do stream (`.m3u8`/`.ts`, 200/304) → nível **DEBUG** ou **excluídos do access log**
  do middleware. Manter em INFO só start/stop/erro do stream. Log tem que continuar legível.

## Aceite

- Câmera desconectada → UI mostra offline/reconectando em ≤N s; FFmpeg morto é limpo (watchdog dispara).
- Polling faz backoff quando travado e pausa com aba oculta; sem 1 req/s eterno.
- Reconexão automática quando o stream volta.
- Log não é mais inundado por 304 de rotina.
- Suíte verde. PR develop. Gate humano staging.

## Referências

- task-059/061 (live view/HLS), task-062 (lifecycle/watchdog), DESIGN_PRINCIPLES_SLC.md (estados
  offline/erro), WS11 (observability)
