# D-157 · `/livez` passa a dizer qual commit está servindo

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente

Não havia como perguntar à API que código ela roda. Isso mordeu **duas vezes numa semana**: um
`railway up` sobrescreveu um deploy por git e ninguém conseguiu provar o que estava no ar.

`GET /livez` agora devolve `commit`, lido de `RAILWAY_GIT_COMMIT_SHA` no import
(`services/api/app/api/v1/health/routes.py`). Sem autenticação de propósito — **SHA de commit não é
segredo**, e a pergunta "o que está no ar?" precisa ser respondível **mesmo com o banco fora** (por isso
`/livez`, que nunca toca dependência, e não `/health`).

🔴 **`"unknown"` não é degradação silenciosa — é o sinal.** Deploy por git sempre traz o SHA; upload
local (`railway up`) nunca. Ver `commit: "unknown"` é a denúncia automática de um deploy sem
proveniência, exatamente o caso de D-156.
