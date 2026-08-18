# D-043 · Limite de segmentos HLS isolado do blocklist de JWT — `SEGMENTS_REDIS_URL` setada

**Seção:** Rodada de 04/08 — Live view fluido + canal 6 · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude → aceito · ✅ vigente**

No DEV, `SEGMENTS_REDIS_URL=${Redis.REDIS_URL}/1` (DB 1) separa o keyspace dos segmentos
(`epi:edge_hls:*`) do `revoked_jti:*` do blocklist de JWT — verificado que os segmentos passaram a gravar
no DB 1. Política da instância ajustada para `volatile-ttl` + `maxmemory 512mb` (**nunca** `allkeys-lru`,
que despejaria tokens revogados sob pressão de memória — reabriria um buraco de segurança).

Ressalva: o Redis do Railway roda sem arquivo de config, então `CONFIG SET` é runtime — não sobrevive a
restart do serviço. Durabilizar via `startCommand` do serviço Redis é follow-up.
Runbook: `docs/runbooks/REDIS_SEGMENTS_SEPARATION.md`.
