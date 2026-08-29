# Runbook — Sinais de degradação (fallbacks sobreviventes)

**Origem:** mutirão de health honesto (itens 2.2/2.3). Ao remover o fallback silencioso do
worker (gevent → sync, item 2.2), ficou claro que o sistema tem OUTROS fallbacks legítimos —
cada um precisa de um jeito de ser detectado, senão vira a mesma armadilha: sobe, health 200,
ninguém percebe que está degradado até o incidente.

Este documento lista os fallbacks que **sobrevivem de propósito** (cumprem contrato, não
degradam silenciosamente) e o sinal que cada um emite. Não é uma lista de bugs — é o oposto:
são os pontos onde o sistema decide reduzir garantia de forma consciente, e como saber quando
isso está acontecendo.

---

## Tabela de sinais

| Fallback | Onde | Sinal | Como observar |
|---|---|---|---|
| **Storage local (sem R2)** | `services/api/app/infrastructure/storage/local_storage.py` (`get_storage`) | Fora do Railway: `logger.warning("storage_local_fallback: ...")`. Dentro do Railway sem credenciais completas: **levanta `StorageError`** (não sobe silencioso) — request que dependia de storage falha alto (500), não grava em disco efêmero por engano. Config parcial (1-2 de 3 credenciais R2) também é erro, em qualquer ambiente. | `grep "storage_local_fallback"` nos logs; ou `GET /api/v1/storage/health` (`checked: "config"`, `r2_configured: bool`); ou `GET /readyz` → `invariants.storage_backend.ok` (ver abaixo) |
| **Worker gunicorn (gevent ausente)** | `railway_start.py` (`start_api`) | **Removido no item 2.2.** Não há mais fallback para `sync` — gevent ausente agora **derruba o boot** (`ImportError` não capturado). O sinal é o próprio processo não subir. | Deploy falha / crash-loop no Railway; logs mostram `ImportError: geventwebsocket...` antes de qualquer log de app |
| **RAG do EPI Assistant (retrieval falha)** | `services/api/app/domain/services/assistant_service.py` (`retrieve_context`) | Falha na busca de contexto (embedding/pgvector) → `logger.warning("rag_retrieval_failed: %s", exc)` e retorna lista vazia. O assistente responde SEM contexto de documentação (degrada qualidade da resposta, não derruba o chat — aceitável por não ser um fluxo de segurança/safety). | `grep "rag_retrieval_failed"` nos logs |
| **`/readyz` — invariantes de config** | `services/api/app/api/v1/health/readiness.py` | `worker_class` (gevent ausente com `SERVICE_TYPE=api`) e `storage_backend` (local sem `ALLOW_EPHEMERAL_STORAGE=1`) reprovam **duro** (503), sem retry — são determinísticos, não há "sorte" possível. | `GET /readyz` → `invariants.worker_class.ok` / `invariants.storage_backend.ok` |
| **`/readyz` — dependências transitórias** | idem | DB/Redis só reprovam após `FAILURE_THRESHOLD` (3) falhas consecutivas do refresher de fundo (retry com backoff) — uma piscada de rede não derruba a promoção de um deploy saudável. | `GET /readyz` → `dependencies.database.consecutive_failures` / `dependencies.redis.consecutive_failures` |
| **`/readyz` — cache stale (refresher morto)** | idem | Se o greenlet/thread de fundo parar de atualizar o cache por mais de `STALE_AFTER_SECONDS` (30s), o handler **recusa servir o último valor conhecido** — 503 com `stale: true`, mesmo que o conteúdo cacheado dissesse "tudo bem". Fail closed: nunca um "ready" congelado mentiroso. | `GET /readyz` → `stale: true` + `age_seconds` |
| **Health do worker Celery** | `railway_start.py` (`start_celery_worker`) | Antes: `{"status":"ok"}` hardcoded, sempre 200. Agora: checa broker (Redis `PING`) + o worker responde a `celery.control.inspect(timeout=2).ping()` (broadcast via broker), cacheado 10s. Falha em qualquer um dos dois → 503 com `detail` do que falhou. | `GET :$PORT/` no serviço `worker` → `status: "down"` + `detail` |

---

## Watchdogs: quem vigia o quê

Um sinal só serve se alguém o lê. Em **29/08/2026** a API do DEV rodou horas um
build de `railway up` — upload do laptop de alguém — enquanto a develop tinha
outro código. O sinal existia: o `/livez` devolvia `commit: "unknown"`, que a
**D-156** define como a marca de deploy sem proveniência. Ninguém estava lendo.

Hoje há **dois** vigias, com escopos que não se sobrepõem. **Não duplicar** —
se um alarme novo couber num dos dois, ele entra ali.

| vigia | onde vive | frequência | o que pergunta | o que faz quando dá ruim |
|---|---|---|---|---|
| **Uptime / restauro** | tarefa agendada do **Cowork** (fora deste repositório) | 5×/dia | *o serviço está de pé?* — `/livez` responde | dispara o playbook de restauro |
| **Proveniência** | `.github/workflows/proveniencia-dev.yml` (neste repositório) | a cada 15 min | *o serviço está rodando o código da develop?* — `/livez.commit` == HEAD | reprova o job, com o motivo e a referência à D-156 |

> 🔴 **O vigia de proveniência ainda NÃO está ligado.** O GitHub só dispara
> `schedule` e `workflow_dispatch` a partir da **branch padrão**, que aqui é
> `main` — o arquivo está na `develop`. Enquanto ele não chegar em `main`, o
> agendamento não roda: nem de hora em hora, nem sob demanda. (É por isso que o
> `security-scan.yml`, que está em `main`, dispara.)
>
> **Ação, e ela é humana:** levar `.github/workflows/proveniencia-dev.yml` até
> `main` no próximo `develop → staging → main`. Até lá, a checagem existe e é
> testada, mas ninguém a executa — que é a mesma situação de 29/08 com outro
> nome. Rodar à mão enquanto isso:
>
> ```bash
> python3 scripts/checa_proveniencia.py \
>   --url https://api-v3-desenvolvimento.up.railway.app/livez
> ```

**A divisão é deliberada.** São perguntas diferentes sobre o mesmo endpoint:
o primeiro pergunta se há alguém em casa; o segundo, se é a pessoa certa. Um
serviço pode estar 100% no ar (uptime verde) servindo código que ninguém sabe
de onde veio — foi exatamente o caso de 29/08.

**Por que a proveniência mora no repositório e o uptime não.** A checagem de
proveniência precisa comparar com o HEAD da develop; ela pertence a quem tem o
histórico. Já o restauro precisa rodar mesmo quando o repositório e o CI estão
indisponíveis — por isso vive fora.

### A carência, e por que ela não é frouxidão

O vigia de proveniência só alerta quando a divergência persiste **além de 30
minutos** contados do commit. Um deploy legítimo leva minutos, e durante ele o
serviço ainda responde o commit anterior: alertar aí geraria ruído e treinaria
todo mundo a ignorar — **que é exatamente como o alarme de 29/08 morreu**. A
lógica é testada (`tests/test_checa_proveniencia.py`), inclusive nos dois lados
da borda, e o workflow roda esses testes antes de confiar na checagem.

### O que ainda não tem vigia

- **Worker Celery em dia.** O `SKIPPED` do Railway é benigno quando nada mudou
  nos caminhos observados, mas ninguém confere se o último build bem-sucedido
  ainda corresponde ao backend da develop. Hoje isso é conferido à mão
  (`git log <sha-do-último-SUCCESS>..origin/develop -- services/api requirements
  infra/migrations`).
- **Frontend.** O mesmo raciocínio de proveniência vale para o serviço
  `Frontend`, que hoje não é checado por ninguém.

---

## O que NÃO tem sinal ainda (pendência)

**Railway não monitora continuamente.** O healthcheck (`/health` hoje, `/readyz` depois do
rollout abaixo) só é chamado **na promoção do deploy** — do boot até o container ficar
saudável uma vez. Depois disso, ninguém bate nele de novo automaticamente. Isso significa:

- Se uma dependência cair *depois* de um deploy já promovido (ex.: Redis cai 3 dias depois),
  `/readyz` vai honestamente reportar `503` — mas **nada vai ler essa resposta**, porque não
  há chamador. O sinal existe; falta o observador.
- **Pendência:** um monitor externo (ex.: um cron/serviço separado, ou um provedor de
  uptime) batendo em `/readyz` e `/status` periodicamente, alertando (Slack/e-mail/PagerDuty)
  quando vir `503` ou `stale: true`. Sem isso, os sinais deste documento só ajudam quem já
  está olhando ativamente (debug manual), não substituem alarme.
- Beat (`start_celery_beat` em `railway_start.py`) ainda serve um health hardcoded
  (`{"status":"ok","service":"celery-beat"}`) — não foi tocado neste mutirão (fora do escopo
  dos itens 2.2/2.3). Mesma lacuna do worker antes deste PR: sobe, health 200, sem checar
  nada de fato.

---

## Rollout do `/readyz` (pós-merge)

`/health` continua exatamente como está (compatibilidade — é o que o healthcheck do Railway
usa hoje). `/readyz` é aditivo. Para ativar como gate de promoção:

1. Deploy deste PR em `staging` (Railway auto-deploy).
2. Confirmar manualmente: `curl https://api-v3-production-2b22.up.railway.app/readyz` retorna
   `200` com `ready: true` em condições normais.
3. No dashboard Railway do serviço `api-v3`: trocar o **Healthcheck Path** de `/health` para
   `/readyz`.
4. Repetir para qualquer outro serviço que sirva este blueprint (não há hoje — só a API usa
   este Flask app).
5. Acompanhar o próximo deploy de perto: se `/readyz` reprovar por engano (falso positivo),
   reverter o healthcheck path para `/health` imediatamente e investigar antes de tentar de
   novo.
