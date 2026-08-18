# D-077 · Os 8 ffmpeg 24h: o sob-demanda JÁ existe — há espectador contínuo

**Seção:** Rodada 08/08 — causa medida do congelamento cíclico + edge sai de caixa preta (D-74..D-77) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**08/08 · Claude**

- LV-3 funciona: ffmpeg para quando `epi:stream:{camera_id}:active` expira — TTL `HLS_VIEWER_TTL` default
  90s (`services/api/app/api/v1/cameras/stream_handlers.py:50`), renovado a cada fetch do player (:483).
  Logo 8 ffmpeg contínuos ⇒ espectador ~contínuo (provável: monitor do embarque RVB com a grade aberta).
- Ingestão 37 Mbps é LAN local (custo ~zero; CPU do serviço ~4%); o custo real (upload pra nuvem) já é
  sob demanda. Partida a frio estimada em 4-6s (probesize 32 + primeiro segmento preso ao GOP + settle 1s
  + push + gate da playlist). **Decisão: manter como está.**
- Decisões da mesma conversa (2026-08-08, Vitor): MediaMTX pro argv do ffmpeg **ADIADO** (redação de log
  já estanca o vazamento; mexer no caminho de captura de 8 câmeras estáveis não vale o risco agora);
  rotação da credencial segue **ADIADA**; troca pra `subtype=1` é decisão de custo separada, fora desta
  rodada.
