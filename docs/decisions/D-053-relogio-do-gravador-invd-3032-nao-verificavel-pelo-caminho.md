# D-053 · Relógio do gravador (iNVD 3032) não verificável pelo caminho intelbras — ação do Vitor

**Seção:** 3ª rodada de 04/08 — "Live view fluido de verdade + causa do SIGTERM" (D-48..D-53) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude (achado) · 📌 ação do Vitor**

O box (Jetson) está saudável: `timedatectl` = `America/Sao_Paulo`, NTP ativo, clock sincronizado. Mas o
caminho servido usa `rtsp_timestamp_recorder_client.py` (protocol=intelbras), que formata timestamp como
wall-clock **ingênuo** sem ler o relógio do NVR. A leitura de clock via ONVIF `GetSystemDateAndTime` só
existe no `onvif_recorder_client.py` (e mesmo lá o `health()` não compara o horário). Logo o relógio do
iNVD 3032 (overlay `14:17:49`) **não é verificável nem reconciliável** pelo código atual — só existe como
OSD queimado no vídeo. Se o gravador estiver dessincronizado, a evidência em vídeo e o registro do sistema
não se cruzam. **Ação do Vitor:** conferir na UI web do iNVD 3032 o fuso configurado e o servidor NTP do
gravador; opcionalmente expor ONVIF e trocar para o caminho que lê `GetSystemDateAndTime`, adicionando
comparação NVR-clock × system-clock no `health()`.
