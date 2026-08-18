# D-101 · Repowise só self-hosted local; hosted/prose/telemetria proibidos sem aceite

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**12/08 · Claude · ⏸ adiada (indexação pós-1º modelo, em worktree limpa)**

Investigado o **Repowise** (`repowise-dev/repowise`, `pip install repowise` v0.41.0) — indexa o repo em
camadas (grafo/git/wiki/decisões/saúde) e expõe por MCP (11 tools: `get_why`, `get_overview`,
`get_dead_code`, `get_risk`, `get_health`, `search_codebase`…). **Egress verificado no `--help` da CLI
real (C-04), não em doc de marketing.** A ferramenta puxa ~90 deps, incl. clientes de LLM/embedding
(`openai`/`anthropic`/`google-genai`/`litellm`) e tem **modo hosted** (Postgres+R2 em repowise.dev) que
**sobe código proprietário** — ⛔ proibido sem aceite do Vitor. **Os defaults são footgun:** `init` roda
`--prose` (manda trechos de código a um LLM) **sempre que houver API key no ambiente**; a **telemetria é
opt-out (ligada por padrão)**. **Receita segura, obrigatória:** `repowise telemetry disable` →
`init --no-prose --mode fast` **sem nenhuma API key no ambiente** (determinístico, *"no model and no
key"*, zero egress de código) → busca semântica só com `--embedder ollama|mock` (nunca os de API) →
`.repowise/` no `.gitignore` (o `mcp` carrega `<repo>/.repowise/.env` com chaves).

🔴 **Risco C-04 estrutural:** um índice gerado e cacheado corre o mesmo risco que originou a C-04 (o
`CLAUDE.md` que descrevia `backend/`+13 microserviços inexistentes). Se o hook de reindex não estiver
ligado, o índice **envelhece calado** e vira "fonte confiável e desatualizada" — agora com aparência de
autoridade. Reindex é por git-hook/watch/manual; `status` mostra sync, mas staleness por timestamp não
foi confirmado. Custo fixo: 11 tools MCP no prompt de toda sessão (~1,5–3k tokens estimados; perfil
`--tools lean` = 6). ⚠️ Em rodada curta pode custar mais do que economiza → ferramenta de investigação,
não de toda sessão.

**Decisão (Vitor, 12/08):** indexar **depois do primeiro modelo**, em worktree limpa de `origin/develop`,
com a receita acima — não neste ciclo, para não atrasar treino/propagação/monitoramento. **`get_why` a
validar** nos 3 casos de resposta conhecida (401/superadmin restaura backup = corrida #306–310/D-56; bbox
`pointerEvents:'none'` = cicatriz, não preferência; playlist só publica pós-`.ts` = corrida #330) —
reportar a **resposta literal**; o achado-chave é se ele **inventa** razão plausível vs. diz "não sei".

**Regra desta rodada (vale para as duas ferramentas):** **regra do projeto vence regra de ferramenta,
sempre.** Em conflito: reportar, não resolver sozinho. Nenhuma credencial em índice, log ou config
commitada.
