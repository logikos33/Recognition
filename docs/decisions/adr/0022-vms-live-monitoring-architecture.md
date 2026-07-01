# ADR-0022 — VMS Live Monitoring Architecture

## Status: Accepted (2026-07-01)

## Contexto

O produto evoluiu de monitoramento frame-a-frame para um VMS (Video Management System)
ao vivo com grade de câmeras simultâneas. Esse cenário levanta desafios de escala:

- Múltiplas câmeras transmitindo vídeo ao mesmo tempo para o browser
- Overlays de detecção YOLOv8 em tempo real sobre cada feed
- Grade com até 16 câmeras visíveis simultaneamente (e dezenas cadastradas)
- Conectividade mista: câmeras no edge (rede local) e cloud (Railway)
- Backpressure: browser não pode consumir todos os eventos em alta frequência

A abordagem ingênua — stream HLS + WebSocket por câmera sem virtualização —
gera gargalos de CPU/memória no cliente com mais de 4 câmeras abertas.

## Decisão

### 1. Substream HLS/WebRTC do edge para cloud

- O edge (mediamtx ou ffmpeg local) entrega substream de baixa resolução (360p, 5 FPS)
  via HLS para o cloud (Railway CDN / R2).
- O browser consome o HLS do cloud, nunca diretamente da câmera.
- WebRTC é considerado fallback para latência < 1s quando edge suporta; HLS é padrão.

### 2. Eventos e overlays via Redis → WebSocket

- Inference-service publica detecções em `Redis PUBLISH detections:{tenant_id}:{camera_id}`.
- `ws-gateway` subscreve e faz fan-out via Socket.IO room `monitoring:{tenant_id}`.
- Frontend recebe um único WebSocket multiplexado; demultiplexa por `camera_id` no cliente.
- Formato de evento: `{ camera_id, timestamp_ms, boxes: [{class, conf, x1,y1,x2,y2}] }`.

### 3. Virtualização do grid no React

- Grid implementado com janela virtual (react-window ou similar):
  apenas as câmeras visíveis na viewport renderizam o `<video>` + canvas overlay.
  Câmeras fora da viewport ficam como placeholder estático.
- Máximo de streams HLS ativos simultaneamente: 9 (3×3 grid visível).
  Câmeras além desse limite são carregadas on-demand ao rolar.

### 4. Throttle/debounce de eventos no cliente

- Eventos de detecção são enfileirados por câmera com debounce de 200ms.
  O render do canvas é agendado via `requestAnimationFrame`.
- Taxa máxima de re-render por câmera: 5 FPS (alinhado ao inference-service).
- Se a fila cresce além de 10 eventos pendentes por câmera, os mais antigos são descartados
  (backpressure de interface — preferir evento recente a atrasar exibição).

### 5. Backpressure no WebSocket

- `ws-gateway` implementa slow-consumer detection: se o cliente não confirma
  (ou a fila Socket.IO cresce além de 50 mensagens), o gateway reduz a taxa de emissão
  para aquele socket (rate-limit adaptativo, mínimo 1 evento/s por câmera).
- Evento `monitoring:backpressure` notifica o frontend para exibir indicador de carga.

## Consequências

- Latência de exibição: ~2-4s (HLS) + ~200ms (overlay). Aceitável para monitoramento.
- CPU do browser estabilizada: virtualização limita renders simultâneos.
- Escalabilidade: novos tenants apenas adicionam rooms Redis; sem overhead no frontend.
- Dependência de `ws-gateway` como único ponto de fan-out — precisa de HA no Railway.
- Câmeras que não entregam substream HLS (câmeras antigas sem suporte) mostram
  placeholder com snapshot estático (última imagem capturada pelo scheduler).
