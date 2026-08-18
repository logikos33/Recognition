# D-045 · Canal 6 da RVB está fisicamente OK — transmite

**Seção:** Rodada de 04/08 — Live view fluido + canal 6 · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · verificado no box · ✅ vigente**

A suspeita de defeito físico/NVR no canal 6 foi descartada: uma única sondagem `ffmpeg` no box (canal 6 =
câmera `4e261bef…`) retornou exit 0, e a câmera aparece com imagem no soak das 8. A sondagem respeitou o
limite de **uma** tentativa (anti-lockout, D-09). Status: sem ação necessária.
