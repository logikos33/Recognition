# D-068 · Causa da parada da coleta PROVADA: meta 17 da encenação + parada invisível — e coleta religada em alta

**Seção:** Rodada 06/08 — pipeline de treino (varredura R2, coleta, bloqueadores da anotação) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**06/08 · Claude**

Evidência colhida no box + DB DEV (a medição vence):
- **Env efetivo do processo** (`/proc/<pid>/environ`): `COLLECTOR_TARGET_FRAMES_PER_CAMERA=17`
  — a meta da encenação de 31/07, nunca elevada. O histograma do banco fecha a conta:
  662 frames em 31/07, **1 em 02/08 + 16 em 03/08 = exatamente 17** após o restart de
  02/08 06:30, zero desde 03/08 08:48. O coletor **fez o que mandaram**.
- **Parada invisível**: journald do usuário retém **0 B** no box — o
  `collector_target_reached` era gritado para o vazio. Corrigido com drop-in
  systemd (`StandardOutput=append:~/recognition/logs/frame-collector.log`).
- **Agravante (dívida OTA em ação)**: o processo rodava a release `5e32dd0`
  **de um diretório já deletado** — o OTA só recicla `edge-sync-agent`
  (`ota/__main__.py:44`), nunca o coletor. Fix em PR próprio.
- **Surpresa boa**: `RECORDER_STREAM_SUBTYPE=0` — a captura **já estava no stream
  principal** (1080p); os 17 frames pós-restart devem confirmar na triagem. A
  migration de subtype-por-câmera do plano ficou desnecessária por ora.

**Religada em 06/08 20:13**: meta 500/câmera, release atual (`e1811d1`), log em
arquivo, e — pela primeira vez — **as 8 câmeras no channel map** (`cameras=8`,
o processo antigo era anterior ao cadastro das 8 e só coletava a câmera 1).
