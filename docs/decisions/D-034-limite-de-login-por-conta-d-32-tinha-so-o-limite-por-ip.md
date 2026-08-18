# D-034 · Limite de login por CONTA (D-32 tinha só o limite por IP)

**Seção:** Contrato e jurídico · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · ✅ implementada**

D-32 registrou que o limite por IP fica fraco atrás do ProxyFix (`x_for=1` acumula por conexão, não por
cliente real) — brute-force distribuído por várias conexões escapa. Correção complementar (sem mexer em
`x_for` nem no limiter por IP, que segue como defesa em profundidade): contador de falhas **por conta**
(`login_fail:{email normalizado}`) em Redis, `app/core/login_account_limiter.py`. Teto 10 falhas / janela 15
min (`LOGIN_ACCOUNT_MAX_FAILURES` / `LOGIN_ACCOUNT_WINDOW_SECONDS`, env-configuráveis). Sucesso reseta o
contador (OWASP). Fail-open: Redis indisponível nunca bloqueia nem derruba o login (mesma filosofia de
`request_metrics.py`/`session_service.py`) — disponibilidade de login vence rigor do contador quando a
infra de contagem está fora. Mensagem ao usuário é genérica (não revela que a conta específica está
bloqueada, evita enumeração). Teste reproduz o cenário exato do D-32 (15 falhas para a mesma conta, cada
uma de um IP/conexão distinto) e prova que quem dispara o 429 a partir da 11ª é o limite por conta, não o
por IP.
