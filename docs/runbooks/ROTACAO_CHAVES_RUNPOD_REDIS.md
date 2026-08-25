# Runbook — rotação de chaves RunPod e Redis (env Desenvolvimento)

**Preparado em 2026-08-25.** O Vitor gira as chaves nos painéis; este runbook é
o que fazer depois, e como provar que tudo voltou são.

> ⛔ **Nenhum valor de chave entra em transcrição, log, commit ou mensagem.**
> Este documento tem só NOMES de variáveis e SERVIÇOS.

---

## 1 · Mapa: o que existe hoje, e onde

Levantado com `railway variables --json` no env **Desenvolvimento**, sem
imprimir valores.

### RunPod

| serviço | variável | rotacionar? |
|---|---|---|
| `API-V3` | `RUNPOD_API_KEY` | ✅ **sim** |
| `celery-worker` | `RUNPOD_API_KEY` | ✅ **sim** |
| `API-V3` / `celery-worker` | `RUNPOD_CLOUD_TYPE`, `RUNPOD_GPU_TYPE`, `RUNPOD_CONTAINER_DISK_GB` | ❌ configuração, não segredo |
| `celery-worker` | `RUNPOD_MAX_USD_TRAIN`, `RUNPOD_TIMEOUT_SECONDS_TRAIN` | ❌ teto de custo, não segredo |

**Duas cópias da mesma chave.** Trocar uma só deixa o outro serviço com a chave
morta, e o sintoma aparece tarde — só quando alguém dispara treino pelo serviço
esquecido.

### Redis

| serviço | variável | banco | rotacionar? |
|---|---|---|---|
| `API-V3` | `REDIS_URL` | `0` | ✅ **sim** |
| `API-V3` | **`SEGMENTS_REDIS_URL`** | **`/1`** | ✅ **sim — a que esquecem** |
| `celery-worker` | `REDIS_URL` | `0` | ✅ **sim** |
| `Frontend` | `REDIS_URL` | `0` | ✅ sim (ver nota) |

🔴 **`SEGMENTS_REDIS_URL` é o pega-ratão.** Existe só na `API-V3`, aponta para o
**banco 1** do mesmo Redis e alimenta os segmentos do live view. Uma rotação que
troque só `REDIS_URL` deixa o live view quebrado com a API "saudável" — falha
que não aparece no `/health`.

**Nota sobre o Frontend:** ele tem `REDIS_URL` e é um build estático. Provável
herança de env copiada. **Não remover nesta rotação** (mudança fora de escopo
com deploy junto); só atualizar. Registrado como dívida a limpar depois.

São **valores literais**, não referências `${{Redis.REDIS_URL}}` — o Railway não
propaga sozinho. Se o plugin Redis for recriado, as quatro variáveis têm de ser
reescritas à mão.

---

## 2 · Ordem de operação

**Redis primeiro, RunPod depois.** Redis derruba serviço se ficar inconsistente;
RunPod só afeta treino, que ninguém está usando no momento da troca.

E **antes de tudo**: confirmar que nenhuma tarefa Celery está em voo. Deploy
durante treino custa o registro do treino inteiro — o callback final do pod é
best-effort **sem retry** (#517).

```bash
railway run --service celery-worker -- python -c "
from app.infrastructure.queue.celery_app import celery
i = celery.control.inspect()
print('ativas:', i.active())
print('reservadas:', i.reserved())
"
```

---

## 3 · Aplicar

⚠️ **`--skip-deploys` em TODAS as chamadas.** No env Desenvolvimento, setar
variável sem ele dispara rebuild do source linkado e o serviço cai. Sobe-se
depois, de propósito e uma vez só.

```bash
# Redis — 4 variáveis, 3 serviços
railway variables --skip-deploys -s API-V3        --set "REDIS_URL=<nova>"
railway variables --skip-deploys -s API-V3        --set "SEGMENTS_REDIS_URL=<nova>/1"
railway variables --skip-deploys -s celery-worker --set "REDIS_URL=<nova>"
railway variables --skip-deploys -s Frontend      --set "REDIS_URL=<nova>"

# RunPod — 1 variável, 2 serviços
railway variables --skip-deploys -s API-V3        --set "RUNPOD_API_KEY=<nova>"
railway variables --skip-deploys -s celery-worker --set "RUNPOD_API_KEY=<nova>"

# Subir, na ordem em que as dependências ficam prontas
railway redeploy -s API-V3 -y
railway redeploy -s celery-worker -y
railway redeploy -s Frontend -y
```

> `<nova>` é substituído no momento da execução, do gerenciador de senhas do
> Vitor direto para o terminal. Não passa por aqui, nem por mim.

---

## 4 · Provar que voltou são

Rodar as quatro, **nesta ordem**. Cada uma cobre uma coisa que as outras não
cobrem.

### 4.1 A API está de pé e falando com o Redis

```bash
curl -sS https://<api-dev>/readyz | jq
```
`readyz` cobre banco **e** Redis; `livez` sozinho **não serve** — responde 200
mesmo com o Redis morto.

⚠️ **Mas `readyz` NÃO é imediato, e isso muda como usá-lo.** Ele não toca a
dependência: lê um cache mantido por um refresher de fundo, e dependência
transitória (DB, Redis) **só reprova depois de falhas CONSECUTIVAS**, com
backoff. Logo depois da rotação ele pode responder 200 por alguns ciclos mesmo
com a URL errada.

Por isso: **esperar ~60s e consultar duas vezes**, e nunca tratar um único 200
como prova. A prova forte de Redis é a sonda §4.2, que abre conexão de verdade.

### 4.2 Os segmentos do live view (o banco `/1`)

```bash
railway run --service API-V3 -- python -c "
import os, redis
r = redis.from_url(os.environ['SEGMENTS_REDIS_URL'])
r.ping(); print('segmentos ok, db =', r.connection_pool.connection_kwargs.get('db'))
"
```
Tem de imprimir `db = 1`. Se imprimir `0`, a nova URL perdeu o sufixo `/1` e o
live view vai falhar **sem** o `/readyz` reclamar.

### 4.3 O worker consome fila

```bash
railway run --service celery-worker -- python -c "
from app.infrastructure.queue.celery_app import celery
print(celery.control.inspect().active_queues())
"
```
Tem de listar `extraction, quality, versioning, inference, training, reports,
quality_cep`. Lista vazia = worker sem broker.

### 4.4 A chave RunPod é válida

```bash
railway run --service celery-worker -- python -c "
from app.infrastructure.gpu.runpod_client import RunPodClient
print('pods:', len(RunPodClient().list_pods()))
"
```
**Sem criar pod nenhum.** `list_pods` autentica e devolve a lista — 0 pods é
resposta válida e esperada. 401 significa chave errada em algum serviço.

### 4.5 O backup continua funcionando

```bash
curl -sS https://<api-dev>/health/backup | jq
```
`saudavel: true`. Este endpoint só depende do R2, mas se ele quebrar depois de
uma rotação de Redis é sinal de que a variável errada foi tocada.

---

## 5 · Se algo falhar

**Não reverter às cegas.** A chave antiga foi revogada no painel — voltar a
variável para o valor anterior devolve uma chave morta e troca um problema por
outro mais difícil de ler.

O caminho é: identificar QUAL das seis variáveis está errada (as sondas de §4
apontam a camada), corrigir só ela, redeployar só o serviço dela.

| sonda que falhou | variável suspeita |
|---|---|
| `/readyz` degradado | `REDIS_URL` da `API-V3` |
| `db = 0` em vez de `1` | `SEGMENTS_REDIS_URL` (sufixo `/1` perdido) |
| `active_queues()` vazio | `REDIS_URL` do `celery-worker` |
| 401 no RunPod | `RUNPOD_API_KEY` — conferir os **dois** serviços |
| `/health/backup` 503 | variável de R2 tocada por engano |

---

## 6 · Depois

- [ ] Confirmar no painel do RunPod que a chave antiga foi **revogada**, não só
      substituída — chave rotacionada que continua válida não é rotação.
- [ ] Dívida: `REDIS_URL` no `Frontend` (build estático não precisa).
- [ ] Dívida: as quatro variáveis de Redis serem literais. Referência
      `${{Redis.REDIS_URL}}` faria a próxima rotação ser automática, mas mudar
      isso agora acrescenta risco no meio de uma rotação — fica para depois.
