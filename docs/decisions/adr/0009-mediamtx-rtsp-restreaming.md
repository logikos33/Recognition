# ADR 0009 — MediaMTX como Proxy RTSP para Streaming de Câmeras no Edge

## Status

Aceito

## Data

2026-05-27

## Contexto

No modo edge, múltiplas câmeras IP (Intelbras, Hikvision, Generic ONVIF) precisam ter seus streams RTSP consumidos pelo engine de inferência (DeepStream ou Ultralytics). Duas abordagens foram avaliadas:

- **FFmpeg → HLS → Redis**: pipeline do `camera-gateway` deprecado. Transcodifica RTSP para HLS com FFmpeg, serve segmentos `.ts` e playlist `.m3u8`, frontend consome via hls.js. Introduz latência adicional (segmentos de 1-3s) e um intermediário desnecessário para inferência.
- **MediaMTX como proxy RTSP**: MediaMTX (anteriormente rtsp-simple-server) atua como proxy e re-streamer RTSP leve. DeepStream lê os streams diretamente via elemento GStreamer `nvurisrcbin` a partir das URLs RTSP do MediaMTX. Sem transcodificação intermediária.

O `camera-gateway` foi arquivado (ver histórico de commits). A lógica de reconexão e health check implementada nele serve como referência de padrões, não como dependência ativa.

## Decisão

Usar **MediaMTX como proxy/re-streamer RTSP** no edge box. DeepStream consome os streams diretamente via `nvurisrcbin` apontando para as URLs RTSP do MediaMTX (`rtsp://localhost:8554/{camera_id}`).

O pipeline FFmpeg→HLS não é usado no modo edge. No modo `cloud_only`, o streaming HLS para o frontend é servido diretamente pela API usando FFmpeg sob demanda, sem MediaMTX.

## Consequências

- Latência mínima no edge: DeepStream lê RTSP nativo sem etapa de transcodificação intermediária.
- MediaMTX gerencia reconexão automática de streams RTSP perdidos e health monitoring das câmeras.
- DeepStream não precisa gerenciar reconexão de câmeras diretamente: MediaMTX abstrai a conectividade com a câmera física.
- Dependência adicional no edge box: MediaMTX deve ser instalado e configurado (`mediamtx.yml`) como serviço systemd no edge box.
- Padrões de reconexão do `camera-gateway` arquivado (exponential backoff, max retries, logging estruturado) devem ser consultados ao configurar MediaMTX e o edge-sync-agent.
- No modo `cloud_only`, MediaMTX não é necessário: câmeras são acessadas diretamente pelo worker Celery via RTSP URL configurada na tabela `ip_cameras`.
