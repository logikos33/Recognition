# D-074 · 🔴 Causa medida do congelamento cíclico do live view: uploader em rodízio (banda nunca foi o problema)

**Seção:** Rodada 08/08 — causa medida do congelamento cíclico + edge sai de caixa preta (D-74..D-77) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**08/08 · Claude**

- Uploader sequencial single-thread: `services/edge-sync-agent/app/live_view/live_view_loop.py:138-141`
  (for câmera a câmera), POSTs síncronos bloqueantes (:198, :226) num `httpx.Client()` compartilhado
  (:87), timeout 10s/request (`segment_pusher.py:24`).
- Ciclo medido no Railway (POST /segment, 01:21:24→01:21:50Z): as 8 câmeras visitadas em rodízio, ciclo
  ≈19s; um POST de 0,770s (câmera `2a683620`) contra 0,03s das demais.
- Segmento vivia 3s no disco (`hls_time 1` × `hls_list_size 3` + `delete_segments`) → ~16 de cada 19
  segmentos apagados antes de qualquer tentativa de envio. **Perda por projeto, não por congestionamento.**
- Rede medida no box: 37 Mbps entrando do gravador, 14 Mbps saindo pra nuvem; link RVB 726 Mbps down /
  401 Mbps up (speedtest com serviço parado) — uso de 3,5% da subida. **A internet da RVB tem 11× mais
  banda do que o sistema precisa.**
- Correção: push paralelo por câmera com teto configurável (`LIVE_VIEW_MAX_PARALLEL_PUSHES`, default 8),
  isolamento de câmera lenta, janela `hls_time 2` × `list_size 10` (20s de vida). Hipóteses mortas nesta
  rodada: banda da RVB, CPU do box (~4% em 2 dias), psycogreen sozinho ([[D-61]]).
