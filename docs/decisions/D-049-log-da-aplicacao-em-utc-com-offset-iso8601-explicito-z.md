# D-049 · Log da aplicação em UTC com offset ISO8601 explícito (Z)

**Seção:** 3ª rodada de 04/08 — "Live view fluido de verdade + causa do SIGTERM" (D-48..D-53) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude → aceito · ✅ vigente · PR #301**

O log da app marcava `2026-08-04 18:32:09,482` sem declarar fuso e em hora **local** do processo, enquanto
Railway/Postgres/gunicorn declaram UTC. Num sistema de segurança o carimbo de tempo é evidência; ambíguo
vale menos. Correção escopada no `JsonFormatter` (classe) e no formatter texto (instância) —
`converter = time.gmtime` + `Z` literal (`%s.%03dZ` no JSON, `%Y-%m-%dT%H:%M:%SZ` no texto). **Sem**
monkeypatch global de `logging.Formatter.converter`. O access log consolidado (A6) herda o mesmo formatter,
então um fix cobre os dois. Regra que fica: **guardar/logar em UTC, exibir em local**.
