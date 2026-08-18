# D-076 · Edge era caixa preta: journald volátil e ilegível — log em arquivo pela unit

**Seção:** Rodada 08/08 — causa medida do congelamento cíclico + edge sai de caixa preta (D-74..D-77) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**08/08 · Claude**

- Achado: `/var/log/journal` ausente (`Storage=auto` → volátil em `/run/log/journal`, dir
  `root:systemd-journal`, `pandora` sem leitura) → `journalctl --user` vazio. Sem sudo não conserta o
  journald.
- Correção sem sudo: `StandardOutput`/`StandardError=append:%h/logs/edge-live-view.log` +
  `edge-log-rotate.timer` (copytruncate, gatilho 50MB). Comandos sudo pro journal persistente guardados
  no runbook (`docs/runbooks/edge-sync-agent-deploy.md` §Logs do edge) — decisão do Vitor: rodar quando
  quiser. Telemetria remota continua desligada (tema separado,
  `docs/edge/DIAGNOSTICO_OBSERVABILIDADE_2026-07-21.md`).
