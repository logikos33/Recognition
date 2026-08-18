# D-027 · Rate limit em buckets dedicados

**Seção:** Contrato e jurídico · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · ✅ vigente · conclui D-24**

O bucket único de 300/min por IP (`tenant-api-global`) inviabilizava 8 câmeras (~720 req/min) e barrava até
`OPTIONS` de preflight. Separado (PR #291) em: OPTIONS 2000/min/IP; vídeo `.m3u8`/`.ts` 240/min por **token
de playback** + piso 6000/min/IP; API geral 300/min/usuário + piso 900/min/IP sempre ativo. **Não afrouxou
segurança:** login (10/min/IP), register/recuperação (5–10/h) e `progress-callback` (60/min) intocados e
estritos. Chave é "usuário **E** IP", nunca "em vez de". Validado no DEV: zero 429 no caminho de vídeo;
login barra a partir do 11º (10×401 → 429). Ver [[D-32]] sobre a granularidade real da chave por-IP.
