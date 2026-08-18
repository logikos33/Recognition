# D-160 · Padrão de requisição ao DVR: clipe por segmento, não frame a frame

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente — medido no código antes de qualquer lote

`replay_miner.py:336-395`: puxa **um clipe** (MP4 fragmentado, `ffmpeg -c copy`) e decodifica para JPEG
**em memória**, num segundo estágio. **Não é uma requisição por frame** — 5.000 requisições contra o DVR
seria risco de lockout; extração local não é.

O disjuntor anti-lockout **já existe**: falha de autenticação detectada no stderr do ffmpeg abre
`circuit_open` e **encerra a run inteira, sem retry** (`replay_miner.py:25`). ⛔ Nada a construir aqui.
