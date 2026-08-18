# D-010 · Capacidade do Orin só vale medida sob carga real

**Seção:** Infraestrutura e custo · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**03/08 · Claude → aceito · 🔄 em execução**

A primeira medição rodou com a câmera **ociosa** (sem tráfego RTSP) — mediu custo parado.
O número 1,1–1,8 pp GPU/câmera veio de 2 câmeras + streams sintéticos e **não pode ser extrapolado**
para 8. Rampa de +2 por degrau, **medindo cada degrau** com tráfego real.
