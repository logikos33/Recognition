# D-096 · Miniatura da triagem por snapshot ONVIF sob demanda — ativação temporária de draft REMOVIDA

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**12/08 · Claude · ✅ mergeado na develop (PR #363; filtro de treinamento no PR #362)**

A triagem (`/epi/cameras/triagem`) "resolvia" imagem de draft **ativando a câmera
temporariamente** — mexia no channel_map, ligava HLS e deixava estado sujo em falha. Removido.
No lugar, o caminho do D-85: **`GetSnapshotUri` ONVIF no iNVD**, executado no box, fallback de
1 frame RTSP (`RtspTimestampRecorderClient.get_snapshot`) — código estruturado para ser
reutilizado pela coleta de ~17 fotos/dia.

- **Fluxo:** `POST /api/cameras/{id}/snapshot/refresh` (JWT, cross-tenant 404, idempotente)
  → `edge_command capture_snapshot` → box captura **sequencial com delay 2s** (⛔ não satura o
  gravador) → `POST /api/v1/edge/cameras/{id}/snapshot` (device auth, escopo novo
  `snapshot:write`, teto 5MB) → R2 `snapshots/{tenant}/{camera}/{ts}.jpg` → cache Redis
  (frescor 10 min — re-render **nunca** bate no gravador) → `GET .../snapshot` com presigned
  15 min. Frontend: lazy-load por viewport, fila de concorrência 2, botão atualizar, falha
  **com motivo** (sem sinal / timeout / auth), nunca as 29 de uma vez.
- **Anti-lockout (D-09):** `RecorderAuthError` tipado; primeiro 401/403 abre **circuit
  breaker até restart** — nenhuma nova tentativa no gravador; canal vazio/timeout ≠ auth.
- **Decisão de escopo de device:** o bearer do edge passa a ser assinado com a **união**
  identity ∪ enum do código implantado. Racional: o servidor não persiste grants por device
  (o enroll devolve o enum inteiro; a autorização lê claims do token auto-assinado, ADR-0019)
  — o identity.json era só cache do enum da época do enrollment. Deploy propaga escopo novo
  **sem reenroll/revogação**. Ressalva registrada no código: se escopos virarem grant por
  device no servidor, revisitar. Paridade do espelho do enum trancada por teste.
- **Pendente de validação em campo:** `GetSnapshotUri` nunca exercitado contra o iNVD 3032
  real (protocolo em uso na RVB é `intelbras`/RTSP — o fallback é o caminho que roda primeiro).
