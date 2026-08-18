# D-057 · Token de playback expirado ganha sinal próprio: 410 `playback_token_expired`

**Seção:** Rodada 4 — a caça ao congelamento (04/08, noite) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude → aceito · ✅ vigente · PR #306**

Expirar é evento NORMAL do ciclo de renovação — não pode ser indistinguível de "stream não existe".
`verify_playback_token_detailed()` passa a classificar `valid | expired | invalid` com a **assinatura
verificada ANTES da expiração**: só um token bem-assinado desta câmera ganha `expired` → **410** +
`error_code: playback_token_expired` + `Cache-Control: no-store`, log em INFO (rotina não polui o dump
stderr WARNING+). **C-01 preservado:** forjado/malformado/sem token → 404 idêntico a câmera inexistente; o
410 não é canal de enumeração porque a assinatura HMAC(`camera_id:exp`) não é forjável — apresentá-la
expirada prova autorização passada. Teste trava: `exp` passado + assinatura ruim → 404. Token vencido
também NÃO renova `epi:stream:*:active` (cliente preso em token morto não mantém o edge transmitindo).
⛔ TTL não mudou — token curto está certo; o que faltava era o sinal para renovar.
