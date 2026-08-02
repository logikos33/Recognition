# Caderno de soluções — mutirão de dívida técnica

**Data:** 2026-08-02 · **Método:** pesquisa de prática de mercado (2025-2026) + verificação no código real
**Antecede:** `docs/REGISTRO_DIVIDA_TECNICA.md` (o levantamento) · **Este documento:** a solução de cada item

> ⛔ **Nada aqui foi implementado.** É plano. A implementação é o mutirão, em ondas, na ordem do fim do documento.

---

## 0. O que a pesquisa CORRIGIU no levantamento anterior

Três itens mudaram de veredito. Vale ler antes de tudo — dois deles eram alarme meu, um estava subestimado.

### ❌ Alarme falso: vazamento de `search_path` entre tenants — **JÁ CORRIGIDO**
A pesquisa apontou que `SET search_path` é estado de **sessão** e que, num pool compartilhado, o tenant B pode
herdar o schema do tenant A. É o vetor mais grave que existe neste tipo de arquitetura.

**No código: já está fechado.** `services/api/app/infrastructure/database/connection.py:119-135` faz `conn.reset()`
(que emite `RESET ALL`) antes de devolver ao pool, e **descarta** a conexão se o reset falhar. Corrigido pelo commit
`c2c00d48`. Existem 3 testes unitários e um teste de integração (`test_camera_create_search_path.py`) que **envenena
a conexão de propósito** e prova que o INSERT ainda pousa no schema certo.

**O que resta (não é o vazamento, é a margem):** 14 repositories não qualificam `public.` nas tabelas — 91 queries
dependem exclusivamente do reset. Hoje funciona; se alguém remover o `reset()` por performance, vaza. Qualificar
`public.` tira a segurança do caminho crítico. **Prioridade média, não urgente.**

### ⬇️ Superestimado por mim: vazamento de cursor
Li o código-fonte C do psycopg2 via pesquisa. `cursor_dealloc` libera a memória **imediatamente** em CPython
(refcounting); o que ele *não* faz é enviar o `CLOSE` SQL — **mas isso só importa para cursores nomeados
(server-side)**, e o projeto tem **zero** ocorrências de `cursor(name=...)`.

**Tradução:** o vazamento prático hoje é ~nulo. Continua valendo corrigir (é bug de contrato, e vira vazamento real
no dia em que alguém paginar um relatório com cursor nomeado), mas **desce de P1 para higiene**. Eu havia ligado
isso ao crescimento de RAM — provavelmente não é a causa.

### ⬆️ Subestimado: o runner de migrations em produção
Aqui está o incêndio de verdade, e ele é pior do que o registro anterior dizia.

**Existem DOIS runners divergentes, e o que roda em produção é o pior:**

| | `infra/migrations/run_migrations.py` | `railway_start.py:55-89` ← **este é o de produção** |
|---|---|---|
| Tabela de controle | ✅ `schema_migrations` | ❌ **nenhuma** — reexecuta os 50+ SQLs a cada boot |
| Advisory lock | ❌ | ❌ |
| Falha aborta o boot? | — | ❌ **não** — loga o erro e **continua**; a API sobe com schema incompleto |
| "already exists" | marca como aplicada | trata como sucesso |
| Quem chama | **ninguém** | `railway_start.py:486` |

E o fallback de diretório (`:61-70`) tenta `infra/migrations/*.sql` e, se não achar, `migrations/*.sql` — **os dois
existem com conteúdo diferente**. Se o CWD mudar, aplica o conjunto errado, em silêncio.

---

## 1. O tema que unifica quase tudo: **falha silenciosa**

Ao consolidar, um padrão apareceu. A maioria dos itens graves não é "o sistema quebra" — é **"o sistema quebra e
não avisa"**. Sete instâncias da mesma classe de bug:

| # | Onde | O que acontece sem sinal |
|---|---|---|
| 1 | `railway_start.py:78-88` | migration falha → loga erro → **API sobe com schema incompleto** |
| 2 | `local_storage.py:109-127` | R2 ausente → grava em disco efêmero → **201 Created** → some no redeploy |
| 3 | `railway_start.py:151-159` | gevent ausente → worker `sync` → **WebSocket morto, health 200** |
| 4 | `health/routes.py:41` | Redis morto → **`status: degraded` com HTTP 200** → Railway não tira de rotação |
| 5 | `railway_start.py:456-466` | health do worker Celery é **`{"status":"ok"}` hardcoded** — não verifica nada |
| 6 | coletor no edge | config fora de faixa → **zero frame, zero erro** (3 ocorrências já) |
| 7 | CI | testes de integração provavelmente **skipados** (falta `INTEGRATION_DATABASE_URL`) |
| 8 | `assistant_service.py:53` | `AttributeError` engolido por `except Exception` → **RAG retorna `[]` para sempre** |

**A regra que resolve os oito** (Jim Shore, *Fail Fast*, IEEE Software; Amazon Builders' Library):

> **Fail-fast em configuração — no boot, antes de aceitar tráfego. Fail-soft em dependência de runtime — sempre
> com métrica e alerta.**

Um fallback só é legítimo se o modo degradado **ainda cumpre o contrato prometido**. Cache fora → lê do banco:
legítimo. R2 fora → grava em disco efêmero e responde 201: **ilegítimo**, porque 201 promete durabilidade.

**Isso deve ser a espinha dorsal do mutirão**, não uma lista de bugs soltos.

---

## 2. Soluções, item a item

### D-01 · Credencial vazada que se auto-restaura
**Fonte:** [GitHub — Removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) · [OWASP ASVS 6.3.2](https://github.com/OWASP/ASVS/blob/master/5.0/en/0x15-V6-Authentication.md)

**Ordem correta (a ordem importa):**
1. **Remover o `ON CONFLICT DO UPDATE SET password_hash` da `027_superadmin_vitor.sql`.** Enquanto existir, tudo
   abaixo é revertido no próximo deploy. **Este é o passo 1 absoluto.**
2. Rotacionar: senha do superadmin, **`JWT_SECRET_KEY`**, e qualquer token que tenha passado pelo repo.
3. Rotacionar a `SECRET_KEY` **invalida 100% dos JWT emitidos** — custo zero, efeito imediato. É a resposta certa
   em incidente. Todo mundo faz login de novo.
4. Auditar log de acesso (Railway + tabela de auditoria). Repo público + senha em claro = assumir tentativa.
5. Remover o bloco "🔑 Acesso padrão" da tela de login e a credencial de `auth/routes.py:90` e `smoke_test.sh:19`.
6. **Só então** decidir sobre reescrever histórico.

**Sobre reescrever o histórico — a recomendação do GitHub é NÃO, se der para rotacionar.** Texto oficial: rotacionar
*"may be sufficient to solve your problem. Going through the extra steps to rewrite the history may not be
warranted."* E o rewrite **não resolve de verdade**: sobrevivem forks (você não controla), *cached views* por SHA,
`refs/pull/*` (read-only, o force-push falha neles de propósito), e há risco de recontaminação por quem tem clone
antigo. Como o que vazou é hash bcrypt (não token vivo), o valor marginal é baixo e o custo é alto.
**Decisão sugerida: rotacionar, tornar privado, e não reescrever.**

**Onde o bootstrap de admin deve viver:** não em migration. Padrão substituto — **comando CLI idempotente**
(`flask bootstrap-superadmin --email=...`), rodado uma vez via `railway run` ou Pre-Deploy Command, que cria a conta
**sem senha utilizável** (`password_hash = NULL`, `must_reset = true`) e **imprime na saída do comando** um link de
convite de uso único com validade curta. Assim o dia zero não depende de e-mail funcionando.

**Regra de seed que fecha a classe do bug:** `ON CONFLICT DO NOTHING` para tudo que o operador pode editar
(credencial, config de tenant). `DO UPDATE` **só** para catálogo/lookup que o repositório possui. Nunca `DO UPDATE`
em `password_hash`, `email` ou `is_active`.

**Detecção contínua (custo zero):** GitHub push protection (gratuito em repo público) + **gitleaks em pre-commit e
CI com regra custom** para os *seus* padrões (`senha:`, `password_hash =` em `.sql`). O push protection do GitHub
**não pegaria** `-- senha: ...` num comentário SQL — só detecta padrões de provedores conhecidos. O gitleaks com
regra própria é o que cobre o caso real.

---

### D-02 · Senha de tenant derivável do slug
**Fonte:** [OWASP ASVS 6.4.1](https://github.com/OWASP/ASVS/blob/master/5.0/en/0x15-V6-Authentication.md) · [Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)

**Solução: não gerar senha nenhuma.** Criar o admin com `password_hash = NULL` + `status = 'pending_activation'`,
gerar token `secrets.token_urlsafe(32)`, **guardar só o hash** do token, e entregar o link **out-of-band** por
e-mail. A resposta HTTP devolve `{"invite_sent_to": "a***@dominio.com"}` — nunca a senha.

**Devolver senha em resposta de API é inaceitável** por razões concretas, não teóricas: a resposta entra em log de
aplicação, log de gateway, APM, e no log do Railway. E quem chama a API passa a conhecer a senha do cliente —
quebra não-repúdio.

**ASVS 6.4.6 fecha o desenho:** mesmo o superadmin deve **disparar** o reset, não **escolher** a senha do usuário.

⚠️ **Todos os tenants já criados com o padrão antigo estão comprometidos.** Rotacionar todos, não só corrigir a
linha. É uma linha de código (`secrets.token_urlsafe(12)` já é usado em `routes.py:753` e `:992`) e uma operação de
dados.

---

### D-03 · Fallback silencioso de storage
**Fonte:** [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) · [12-factor III](https://12factor.net/config) · [Railway volumes](https://docs.railway.com/volumes)

**Solução em três camadas:**
1. **Validação no boot** (`pydantic-settings`): se `DEPLOYMENT_MODE=production`, as vars de R2 são **obrigatórias**;
   faltando qualquer uma, o processo **não sobe** (`SystemExit(78)` = `EX_CONFIG`) com mensagem que diz exatamente
   o que falta e o que aconteceria (perda de arquivo no redeploy).
2. **Inverter o default**: modo efêmero passa a exigir `ALLOW_EPHEMERAL_STORAGE=1` explícito, **proibido em
   production** pelo validator. Default perigoso é a raiz do problema.
3. **Preflight que testa de verdade**: `head_bucket` no boot. Env var presente e credencial expirada passa em
   qualquer validação de schema — só a chamada real prova.

**Raio de alcance:** `get_storage()` tem **11 call sites**, e 18 pontos de escrita de arquivo. Mas a correção toca
**1 função**, e os testes já mockam `get_storage` inteiro. **Risco baixo.**

⚠️ Inconsistência a resolver junto: 5 tasks de quality importam `R2Storage` **direto** e estouram se R2 faltar —
comportamento oposto ao fallback. Escolher um.

---

### D-04 · Migrations (o item de maior risco não resolvido)
**Fonte:** [Flyway schema history](https://documentation.red-gate.com/flyway/flyway-concepts/migrations/flyway-schema-history-table) · [Atlas — directory integrity](https://atlasgo.io/concepts/migration-directory-integrity) · [advisory lock: sessão vs transação](https://www.ines-panker.com/2024/12/17/advisory-locks.html)

**Fase 0 (30 min, hoje) — guard-rail de CI.** Três checks que teriam evitado o incidente:
- prefixo duplicado → falha o build (`sort | uniq -d`)
- existência de **dois** diretórios de migration → falha
- aplicar em banco limpo **2×** (idempotência) e diffar o schema resultante

**Fase 1 — tirar migration do boot.** O padrão é passo **separado** de deploy (Pre-Deploy Command do Railway), não
o processo web. Se mantiver no boot, o mínimo é **`pg_advisory_xact_lock`** (não `pg_advisory_lock`).

> ⚠️ **Armadilha documentada e grave:** `pg_advisory_lock` é lock de **sessão**, vive na conexão. Pegar numa conexão
> do pool e liberar em outra faz o unlock virar no-op — a conexão volta ao pool segurando o lock e **todo boot
> futuro trava para sempre**. Use a versão `_xact_` (liberada no fim da transação) ou conexão dedicada com
> `try/finally` + `lock_timeout`.

**Fase 1b — ledger de verdade.** `public.schema_migrations (tenant_schema, version, checksum, installed_rank,
installed_on, success)` com **`UNIQUE (tenant_schema, version)`** — essa constraint sozinha teria matado o bug dos
6× `052`. O checksum detecta edição de migration já aplicada.

⚠️ **Cutover exige backfill.** Trocar o loop do `railway_start.py` pelo runner com ledger significa que a
`schema_migrations` chega **vazia** num banco que já tem tudo aplicado → ele tentaria reaplicar os 50+ SQLs. É
preciso `INSERT` de todas as versions já aplicadas **antes** do cutover. O harness em CI é a rede de segurança.

**Fase 2 — CDRB** (Create, Delete, Rename, Baseline): gerar um baseline único de `pg_dump --schema-only` do estado
atual, arquivar as antigas fora do `locations`, **matar o diretório duplicado da raiz**, marcar o baseline como já
aplicado nos ambientes existentes, e daí em diante numerar por **timestamp** (`20260802T1430_nome.sql`).

**Não adotar Alembic.** Sem ORM, o benefício principal (autogenerate) não se aplica — pagaria a complexidade sem a
contrapartida. Se um dia a dor persistir: **Atlas** (resolve colisão em CI *e* multi-tenant nativamente) ou
**dbmate** (SQL puro, simplicidade).

**Não usar `IF NOT EXISTS` como substituto de ledger.** Ele esconde divergência: a tabela pode existir com colunas
diferentes e você nunca saberá.

---

### D-05 / D-06 · Cursor e fronteira transacional
**Fonte:** [psycopg2 — with statement](https://www.psycopg.org/docs/usage.html#with) · [psycopg2 pool.py](https://github.com/psycopg/psycopg2/blob/master/lib/pool.py)

**Cursor (rebaixado a higiene):** adotar `with conn.cursor() as cur:`. O `__exit__` chama `close()` e **nada mais** —
não commita, não faz rollback, não devolve a conexão. Retorna `None`, logo **não engole exceção**.

**Transação (este importa):** `_execute_mutation` promete commitar e não chama `conn.commit()`. Hoje funciona porque
o padrão do pool salva; **qualquer método com 2+ statements não é atômico**, e no dia em que alguém mexer no
autocommit, todos os writes desse método passam a ser descartados **em silêncio** (o `putconn` faz rollback).

Solução: fronteira explícita com `with conn:` (que em psycopg2 **abre transação mesmo em conexão autocommit — a
partir da 2.9**). Parar de alternar `autocommit` em runtime.

⚠️ **Pin obrigatório:** `requirements/base.txt:14` tem `psycopg2-binary>=2.9.0` — **piso, não pin**. O padrão
`with conn:` depende de ≥2.9. Fixar versão exata.

**Raio de alcance: ALTO** — `base.py` tem **208 chamadas em 29 arquivos**, 30 classes herdam dele. Adicionar `with`
no cursor é seguro; **mudar semântica de commit não é.** Fazer em PR isolado, com o harness rodando.

---

### D-07 · Fallback do gunicorn e health check que mente
**Fonte:** [Amazon Builders' Library — Implementing health checks](https://aws.amazon.com/builders-library/implementing-health-checks/) · [Railway healthchecks](https://docs.railway.com/deployments/healthchecks)

**Correção trivial:** **deletar o `except ImportError`**. O gunicorn já falha sozinho se não conseguir importar a
worker class — o `try/except` é exatamente o código que *remove* essa garantia.

**Health check em três endpoints, não um:**

| | escopo | reação | regra |
|---|---|---|---|
| `/livez` | processo vivo | **reiniciar** | **nunca** toca em DB/R2 |
| `/readyz` | dependências + invariantes (worker class correta, storage = R2) | **tirar do LB** | resultado **cacheado**, checado em greenlet de fundo |
| `/status` | diagnóstico rico | humano | nunca consumido por automação |

O antipadrão que a AWS ataca: **checar dependência no liveness**. Banco tosse 10s → processo reinicia → tempestade
de cold start sobre um banco já sofrendo.

⚠️ **Particularidade do Railway que muda a estratégia:** a doc diz que o healthcheck **não é usado para
monitoramento contínuo — só na promoção do deploy**. Duas consequências: (a) o `/readyz` é a **única** barreira
automática contra promover um deploy degradado, então precisa reprovar `worker_class=sync` e `storage=local`;
(b) depois do deploy **ninguém está olhando** — precisa de monitor externo batendo no `/readyz`.

Corrigir junto: `health/routes.py:41` retorna **200 com Redis morto**; e o health do worker Celery
(`railway_start.py:456-466`) é `{"status":"ok"}` **hardcoded**.

⚠️ Cuidado: fazer o `/health` retornar 503 com Redis fora **muda comportamento de deploy** — se o Redis for flaky,
derruba a app. Colocar isso no `/readyz`, não no `/livez`.

---

### D-09 · Vídeo em escala — a pesquisa apontou caminho melhor que o meu
**Fonte:** [R2 pricing (28/05/2026)](https://developers.cloudflare.com/r2/pricing/) · [AWS IVS pricing (13/05/2026)](https://aws.amazon.com/ivs/pricing/) · [MediaMTX](https://github.com/bluenviron/mediamtx) · [Visylix — HLS vs WebRTC para segurança](https://visylix.com/blog/hls-vs-webrtc-streaming-protocol-security)

Eu havia sugerido "edge escreve direto no R2". **Os números apontam melhor.**

**Cenário 28 câmeras:** 14 segmentos/s = **36,3 M PUT/mês**, ~10 TB/mês de ingest.

| arquitetura | custo/mês | latência |
|---|---|---|
| **Hoje (Flask no caminho)** | ~$898 de egress em cloud padrão + CPU + acoplamento de deploy | 8–12 s |
| **R2 + CDN + Worker** | ~$170–200 (egress **$0** — vantagem estrutural da R2) | 8–12 s |
| **MediaMTX numa VM** | **~$40–50** (VM 4 vCPU/8 GB), **$0 por operação** | **<1 s** (WebRTC) |
| Cloudflare Stream Live c/ gravação | **$6.048** | — |
| AWS IVS | **$4.032–40.320** (cobra por input-hora **mesmo sem espectador**) | — |

**Recomendação: híbrido.** MediaMTX numa VM para o **ao vivo** (Jetson publica SRT/WHIP, operador consome WebRTC,
sub-1s) + segmentos HLS para R2 apenas para **replay/evidência**, com lifecycle. Isso mata os ~$160/mês de Classe A
*e* derruba a latência de 10 s para <1 s.

**Isto responde sua pergunta de latência de ontem, e melhor do que eu respondi.** Eu disse que HLS já é lento
(6–10 s) e o R2 seria ruído — verdade, mas a conclusão certa não era "aceite os 10 s": é que **existe caminho para
sub-1s mais barato que o atual**. A literatura de CFTV é explícita: HLS serve para revisão de evidência e
video-wall; **é errado para resposta de operador ao vivo e controle PTZ**.

**A pergunta de produto que decide:** o operador só *observa*, ou *age* (PTZ, intervenção)? Se só observa,
8–12 s é aceitável e R2+CDN basta. Se age, WebRTC. **Responder antes de escolher a stack.**

**Alavanca imediata se ficar em R2:** segmento de **4 s em vez de 2 s** corta Classe A de ~$159 para ~$77/mês
(latência sobe ~2 s). E **não faça PUT do manifesto a cada segmento** — dobra a conta.

⚠️ **Nunca usar Infrequent Access para segmento ao vivo**: mínimo de 30 dias de cobrança + operação Classe A por
transição, para objetos que deveriam sumir em 2 minutos.
⚠️ Lifecycle da R2 tem granularidade **em dias** e expiração preguiçosa (até ~48 h). Para janela de minutos, deletar
explicitamente (`DeleteObject` é **grátis**) e usar lifecycle só como rede de segurança.

---

### D-10 · Config sem validação de faixa
`pydantic-settings` com `Field(ge=..., le=...)` e `model_validator(mode="after")` para obrigatoriedade condicional.
Vantagem sobre `os.environ.get()` + `if`: agrega **todos** os erros numa `ValidationError` (você descobre as três
variáveis faltando de uma vez, não uma por deploy).

⚠️ **Migração big-bang é arriscada:** há **157 ocorrências** de `os.environ` em `services/api/app/`, e só 35 estão
no `config.py` — que é usado em **apenas 2 lugares**. Tasks Celery leem env em *import time*. Fazer incremental,
começando pelas críticas (R2, DB, worker class, faixas do coletor).

---

### D-11 · Recuperação de senha
**Fonte:** [OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)

Token opaco `secrets.token_urlsafe(32)`, **só o hash no banco**, uso único, **15 min a 1 h**.
Resposta **idêntica em conteúdo, status e tempo** para e-mail existente e inexistente (a assimetria de tempo é o
vazamento mais comum — enfileirar o envio resolve os dois problemas). Rate limit **por conta** (3/h) e por IP.
**Não logar automaticamente** após o reset (OWASP é explícito). **Invalidar sessões** no reset.
**Nunca** enviar a senha no e-mail.

**Não usar JWT como token de reset** — você perde uso-único de graça e ganha superfície de ataque.

⚠️ **Host Header Injection:** não montar a URL do link a partir do header `Host`. Base URL fixa em config. É vetor
de account takeover clássico.

**Provedor de e-mail:** **Resend** (free 3.000/mês cobre reset + convite com folga; melhor DX). Se entregabilidade
virar problema medido, **Postmark** ($15/mês) — separa obrigatoriamente stream transacional de broadcast, então
reset nunca fica atrás de fila de marketing. **Evitar SES** até ter volume: o "barato" se paga em horas de
engenharia (sandbox, bounce via SNS, sem templates).
Obrigatório: SPF + DKIM (≥1024 bits) + DMARC (`p=none` → ler relatórios → `p=quarantine`), em **subdomínio
dedicado**.

---

### D-18 · `develop` 184 commits à frente de produção
🔍 Confirmar com refs atualizadas. Se procede, é dívida de **processo**, não de código: três semanas de trabalho
validado em DEV que não chegou à produção. Quanto maior o lote, mais arriscada a promoção — e a janela de
`develop→staging` já foi bloqueada por conflito real uma vez (`HANDOFF_CONTINUIDADE.md:135`).

### D-22 a D-26 · Docs e processo
Recriar ADR-0057 (destruída por `git clean`) e as citadas-mas-inexistentes (0037, 0038, 0054). Criar
`docs/security/credentials-inventory.md`. Corrigir o CLAUDE.md (diz `eventlet`, é gevent). **Passe de reconciliação
de docs** — documento que descreve sistema que não existe mais gera tarefa fantasma, e já gerou nesta análise.

---

## 3. O mutirão — ondas propostas

> **Princípio de ordenação:** primeiro o que impede que as outras correções persistam; depois o que faz o sistema
> **avisar** quando quebra; depois o estrutural; por último a higiene.

### 🔴 Onda 0 — Contenção (horas · faça antes de qualquer outra coisa)
1. Remover `ON CONFLICT DO UPDATE password_hash` da `027` — **sem isso, nenhuma rotação persiste**
2. Rotacionar senha do superadmin + `JWT_SECRET_KEY` (invalida todos os tokens) + senhas dos tenants do padrão antigo
3. Remover credencial da tela de login, do Swagger (`auth/routes.py:90`) e do `smoke_test.sh:19`
4. **Verificar as envs de R2 em produção** — antes da encenação do lote 1, senão o dataset pode evaporar
5. Ligar push protection + gitleaks pre-commit com regra custom

### 🟠 Onda 1 — "O sistema tem que avisar quando quebra" (o tema)
Os 8 casos de falha silenciosa da seção 1. Todos pequenos, todos da mesma família:
6. Migration que falha **aborta o boot** (`railway_start.py:78-88`)
7. `get_storage()` fail-fast em produção + inverter o default + `head_bucket` no preflight
8. **Deletar** o `except ImportError` do worker (`railway_start.py:151-159`)
9. `/livez` + `/readyz` separados; Redis morto → 503 no `readyz`; health do worker deixa de ser hardcoded
10. Validação de faixa da config do coletor (fecha a família de 3 bugs já vistos)
11. **Confirmar se os testes de integração rodam em CI** — se estão skipados, a rede de segurança não está plugada
12. Fechar o `assistant_service.py:53` (RAG morto em silêncio)

### 🟡 Onda 2 — Migrations (estrutural, exige cuidado)
13. Guard-rail de CI: prefixo duplicado, diretório duplicado, idempotência 2×
14. Unificar os dois runners; ledger com `UNIQUE (tenant_schema, version)` + checksum; `pg_advisory_xact_lock`
15. **Backfill** da `schema_migrations` antes do cutover
16. CDRB: baseline, arquivar antigas, matar `migrations/` da raiz, timestamp daí em diante

### 🟢 Onda 3 — Identidade e acesso
17. Senha de tenant → convite com token (e rotacionar os tenants já criados)
18. Fluxo de recuperação de senha + provedor de e-mail
19. `token_version` no usuário (revogar tudo sem introduzir dependência nova)

### 🔵 Onda 4 — Escala de vídeo (**depende do mapa de consumo**)
20. Rodar o `MAPA-CONSUMO-API-LIVEVIEW-PROMPT.md` primeiro — medir antes de decidir
21. Responder a pergunta de produto: operador **observa** ou **age**?
22. Correções rápidas: guarda de câmera edge no `start_stream`, intervalo de poll, idempotência do `useLiveView`
23. Decidir MediaMTX vs R2+CDN com os números na mão

### ⚪ Onda 5 — Higiene
24. `with conn.cursor()` nos 6 métodos + pin exato do psycopg2
25. Qualificar `public.` nos 14 repositories (tira a segurança do caminho crítico)
26. Recriar ADRs destruídas, corrigir CLAUDE.md, passe de reconciliação de docs
27. `TODO-WS1` (modais), 17 `any`, limpeza do módulo `fueling` legado

---

## 4. Regras do mutirão (aprendidas do jeito difícil)

- **Uma sessão mergeia.** A colisão de 31/jul quase sobrescreveu uma correção de auth. Usar
  `tools/agent-driver/CABECALHO_SESSOES_PARALELAS.md`.
- **Achado fora do escopo vira relatório**, não código.
- **Teste inesperado falhando = sinal de colisão.** Parar e reportar, não "resolver o conflito".
- ⛔ **Nunca `git clean`** — já apagou ADR, runbooks e um .pptx nesta árvore.
- **Uma onda por vez.** Onda 2 (migrations) e Onda 1 (item 6, migration aborta o boot) tocam o mesmo arquivo —
  **não paralelizar essas duas**.
- **Verificação proporcional ao risco**: `base.py` tem 208 chamadores; migration em produção não tem rollback.
  Esses dois pedem harness + revisão humana. O resto, teste da área.
