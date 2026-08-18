# D-079 · Stream principal das câmeras RVB é HEVC (H.265) — navegador sem decode de HW vê grade preta

**Seção:** Rodada 08/08 — causa medida do congelamento cíclico + edge sai de caixa preta (D-74..D-77) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**09/08 · Claude**

- Medido no NVR (canal 8, `subtype=0`): **hevc (Main), 1920x1080, 30 fps**. Com `-c:v copy` o HEVC
  atravessa o pipeline inteiro até o MSE do navegador.
- Chrome com decode por hardware (macOS VideoToolbox, Windows moderno) toca; **Chromium puro, Firefox e
  Linux sem VAAPI não tocam** — tráfego HLS integral com `currentTime` parado em 0 (grade preta sem
  erro). Explica também por que o harness headless não serve de espectador aqui.
- Reforça a decisão pendente do `subtype=1` (substream costuma ser H.264, universal) — além do custo de
  egress, há compatibilidade de navegador em jogo. Decisão segue com o Vitor (fora desta rodada).
