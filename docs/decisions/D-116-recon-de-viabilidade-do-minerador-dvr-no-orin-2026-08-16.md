# D-116 · Recon de viabilidade do minerador DVR no Orin (2026-08-16) — corrente pronta, faltam config e deploy

**Seção:** Rodada RunPod 10/08 (PR #343 — renumerada de D-85..D-88 → D-106..D-109) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

> ⚠️ Renumerado **D-107→D-116** na consolidação do merge #384 (D-107 já em uso na develop).

**Feito.** SSH read-only no pandora + probe que não imprime credencial/host/URL. **A corrente mecânica está PRONTA:**
`recorder_factory.build_recorder_client_from_env()` resolve para o `RtspTimestampRecorderClient` **real**
(playback RTSP `/cam/playback?starttime=…&endtime=…`, dialeto Intelbras), **deployado** em
`~/recognition/current`; **DVR TCP-alcançável** na :554; `yolox_nano.onnx` presente; disco 56 GB livres
(reserva intacta); identidade do device (`DEVICE_ID`/`ENROLLMENT_TOKEN`/chave) e credencial do DVR
(`RECORDER_HOST/USERNAME/PASSWORD`) presentes no env (Vitor já provisionou).

🔴 **Dois bloqueios impedem o lote 1 como especificado (canal 10 primeiro):**
1. **`RECORDER_CHANNEL_MAP` só tem o canal 1** (`{"eb15…":1}`) — **canal 10 (única fonte de AUSÊNCIA) e os
   demais canais aprovados não estão registrados como câmeras do gravador.** Sem `camera_id` mapeado, o
   minerador não tem como pedir playback do canal 10.
2. **`replay_miner.py` (orquestração desta rodada) não está no box** — vive só na PR #384 (não mergeada).
   O box tem o *client*, não o *minerador*. Precisa entrar por OTA (após merge) para rodar de verdade.

**Decisão — não puxei imagem real nesta sessão.** (a) Canal 10 é inalcançável (bloqueio 1), então o
pedido central do prompt — qualidade real da ausência — não teria resposta mesmo puxando; (b) primeiro
run real de playback num device de produção que a RVB usa pra live-view, com risco de vazar credencial no
comando ffmpeg, pede a porta deliberada do Vitor (`CONFIRM_MINE=1`), não improviso autônomo. Regra da
casa: na dúvida entre agir e reportar, **reportar**.

**Veredito de ausência (bloco 4, com dado).** O dry-run projeta **~209 crops de ausência no total** (canal
10, 8 dias × 2 turnos). A ausência se reparte em ≥4 classes (*sem protetor*, *sem máscara*, *sem óculos*,
*sem botas*). ⇒ **A meta de ≥100 imagens POR classe de ausência NÃO é alcançável só pelo canal 10** — 209
÷ 4 ≈ 52/classe no teto otimista. Ou se mapeiam mais áreas de convivência, ou a ausência precisa de fonte
além do DVR. **Confirmação empírica fica pendente do lote 1 real.**

**Para o Vitor rodar o lote 1 (canal 10) com segurança:** (1) registrar canal 10 (e os aprovados 8/11/12/19/23/28)
como câmeras do gravador → `RECORDER_CHANNEL_MAP` no DEV/env; (2) subir o `replay_miner` por OTA (merge #384);
(3) rodar no pandora com `CONFIRM_MINE=1` — anti-lockout e reserva de disco já embutidos.
