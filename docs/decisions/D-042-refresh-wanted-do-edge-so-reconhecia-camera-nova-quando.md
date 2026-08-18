# D-042 · `_refresh_wanted` do edge só reconhecia câmera nova quando TODAS estavam ociosas

**Seção:** Rodada de 04/08 — Live view fluido + canal 6 · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude → aceito · ✅ vigente · PR #294**

Bug: a supressão do poll de `wanted` usava `any(transcoder rodando)` — com 1 de N câmeras já transmitindo,
o poll ficava suprimido, e uma câmera ociosa que ganhasse espectador durante a transmissão das outras
nunca subia até **todas** perderem espectador. Corrigido para `all(câmeras conhecidas transmitindo)`.

Nota operacional: o ciclo OTA reinicia só o `edge-sync-agent.service`, não o `edge-live-view.service` —
aplicar essa mudança no box exige `systemctl --user restart edge-live-view` manual. Dívida a resolver no
updater (ver D-46/D-47).
