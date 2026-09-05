# Backup do Postgres — conferir, restaurar, reverter

> Escrito em **2026-09-05**, com o que foi **medido** naquela noite. Antes disto o
> único doc de reversão do repo era `docs/ROLLBACK.md`, de **10/04/2026**: aponta
> uma tag de abril, descreve um incidente encerrado e oferece
> `git push origin staging --force` como "opção 3". ⛔ **Não use aquele arquivo.**

---

## 1. Há backup? (30 segundos, sem credencial)

```bash
curl -s https://api-v3-desenvolvimento.up.railway.app/health/backup | python3 -m json.tool
```

A rota é pública de propósito — é sonda de infra e o corpo não revela conteúdo,
só instante, idade e contagem. **O código HTTP é a resposta:**

| HTTP | Significado |
|---|---|
| **200** | Backup mais novo com menos de 26h. É o único estado bom. |
| **503** | Sem backup, backup velho, ou **falha ao ler o storage**. Fail closed: "não consegui verificar" nunca devolve 200. |

Campos: `idade_horas` (do mais novo), `idade_maxima_horas` (26), `total`
(quantos objetos na série automática), `mais_novo` (ISO-8601 UTC).

<details><summary>Como isto se parecia quebrado (05/09/2026, DEV)</summary>

```json
{"idade_horas": 270.8, "idade_maxima_horas": 26,
 "mais_novo": "2026-08-25T11:21:36+00:00", "saudavel": false, "total": 1}
```
Onze dias, um arquivo só. A rota estava certa; o mundo é que estava errado.
</details>

### 1.1 Se der 503: é o agendador ou é a tarefa?

Essa é a pergunta que custa tempo, então responda nesta ordem.

**a) O agendador existe?** MEDIDO em 05/09: não existe serviço `SERVICE_TYPE=beat`
em nenhum ambiente — o beat roda **embutido no `celery-worker`** (`-B`).

```bash
railway logs -s celery-worker | grep -i "beat"
# esperado no boot:  "Beat EMBUTIDO neste worker (-B). Schedule: ['backup-postgres', ...]"
# alarme:            "CELERY_BEAT_EMBEDDED=0 — este worker NÃO agenda nada."
```

Sem essa linha, **nada** do `SAFE_BEAT_SCHEDULE` dispara — não só o backup:
compliance, baseline CEP, shift-reports, drift e a reconciliação de pods RunPod
(que é o que impede pod de GPU órfão queimando dinheiro) morrem junto.

**b) A tarefa rodou e falhou?**

```bash
railway logs -s celery-worker | grep -E "backup_(ok|pg_dump_falhou|drill_reprovou|sem_pg_dump|pequeno_demais)"
```

| Log | Causa | Conserto |
|---|---|---|
| `backup_sem_pg_dump` | `pg_dump` não existe na imagem do worker (era o caso até 05/09) | `services/api/Dockerfile.worker` — `postgresql-client-18` via PGDG. **NÃO** é `nixpacks.toml`: nixpacks não builda serviço nenhum neste projeto (worker → `worker-railway.toml` → `Dockerfile.worker`; API → `services/api/railway.toml`). Confirme com `railway ssh -s celery-worker -- sh -lc 'pg_dump --version'` — tem de responder 18.x, porque o servidor é 18.6 e pg_dump mais velho que o servidor aborta. |
| `backup_pg_dump_falhou` | credencial/rede/versão do servidor | ver stderr truncado no log |
| `backup_drill_reprovou` | subiu, mas o objeto **não é restaurável** | ⚠️ trate como "sem backup" |
| `backup_ok` | tem backup íntegro | — |

⚠️ `backup_drill_reprovou` **não apaga** a chave ruim: ela fica no R2 para
inspeção. Apagar a evidência de um backup ruim seria o pior desfecho.

**c) Disparar um backup fora de hora** (não espera 03:00/15:00 UTC):

```bash
railway run -s celery-worker python3 -c \
 "from app.infrastructure.queue.celery_app import celery; \
  print(celery.send_task('tasks.backup.backup_database', queue='reports'))"
```

### 1.2 Quando o backup roda

`crontab`, **03:00 e 15:00 UTC** (00:00 e 12:00 em Brasília) — hora de parede,
não intervalo. Intervalo aqui era armadilha: o estado do scheduler vive em
`/tmp` e zera a cada deploy, e o DEV redeploya sozinho a cada merge na develop.
Uma entrada "a cada 12h" nunca vencia num dia de trabalho.

---

## 2. Restaurar

> ⛔ **Nunca restaure por cima de um banco vivo.** Restaure num banco novo,
> confira, e só então decida. Um restore por cima é irreversível — e este
> documento não autoriza `DROP` de nada.

**Pré-requisito:** credencial R2 **somente-leitura** — `docs/runbooks/R2_RO_TOKEN_PROVISION.md`.
⛔ Não reutilize `R2_KEY`/`R2_SECRET` (são read-write).

```bash
# 1. Achar o objeto. Série automática: backups/postgres/auto/<ISO>.sql.gz
export AWS_ACCESS_KEY_ID="$R2_RO_ACCESS_KEY" AWS_SECRET_ACCESS_KEY="$R2_RO_SECRET"
aws s3 ls "s3://$R2_BUCKET/backups/postgres/auto/" --endpoint-url "$R2_ENDPOINT" | tail -5

# 2. Baixar
aws s3 cp "s3://$R2_BUCKET/backups/postgres/auto/2026-09-05T030000Z.sql.gz" . \
  --endpoint-url "$R2_ENDPOINT"

# 3. Conferir ANTES de restaurar — mesmos marcadores do drill automático
gunzip -c 2026-09-05T030000Z.sql.gz | tail -3 | grep "PostgreSQL database dump complete" \
  && echo "rodapé OK: pg_dump terminou"
gunzip -c 2026-09-05T030000Z.sql.gz | grep -c "CREATE TABLE public.\(alerts\|cameras\)"
# esperado: 2

# 4. Restaurar num Postgres DESCARTÁVEL (docker local, não Railway)
docker run -d --name pg-restore -e POSTGRES_PASSWORD=local -p 5433:5432 postgres:18
gunzip -c 2026-09-05T030000Z.sql.gz | \
  PGPASSWORD=local psql -h localhost -p 5433 -U postgres -d postgres
```

⛔ **Segredo nunca em `argv`.** `psql 'postgres://user:senha@host/db'` deixa a
senha visível em `ps aux` e em qualquer coletor de processo. Use `PGPASSWORD`
no environment — é o que `tasks/backup.py` faz para o `pg_dump`.

**Promover a restauração para o DEV é ato humano do Vitor** e não está descrito
aqui de propósito: exige decidir o que fazer com o dado escrito **depois** do
backup, e essa decisão não é de nenhum agente.

---

## 3. Reverter um deploy no DEV

**O DEV deploya sozinho a cada merge na `develop`.** Isso muda o que "rollback"
significa:

| O que você quer | O que fazer | Dura quanto |
|---|---|---|
| Parar o sangramento **agora** | Railway → `API-V3` → Deployments → deployment anterior → **Redeploy** | ⚠️ **Até o próximo merge na develop**, que sobrescreve. É torniquete, não conserto. |
| Reverter de verdade | `git revert <sha>` numa branch nova → PR → merge na develop | Permanente. O merge é que deploya. |

```bash
# reverter de verdade — worktree próprio, nunca checkout compartilhado
git worktree add -b v1/reverte-<algo> /Users/vitoremanuel/Logikos-mutirao/wt-reverte origin/develop
cd /Users/vitoremanuel/Logikos-mutirao/wt-reverte
git revert --no-edit <sha-que-quebrou>
git push -u origin v1/reverte-<algo> && gh pr create --base develop
```

⛔ **`git push --force`** — nem no DEV, nem na staging, nem em lugar nenhum.
É o que `docs/ROLLBACK.md` sugere e é o motivo de este arquivo existir.
Reescrever o histórico de uma branch que outros agentes têm em worktree
transforma um bug num incidente.

⚠️ **Reverter código não desfaz migration.** Migrations são forward-only
(`CLAUDE.md`): se o merge revertido rodou uma migration, a coluna/tabela
continua lá. Corrigir dado é migration **nova**, nunca `DROP`.

---

## 4. Produção não tem esta rota

MEDIDO em 05/09: `GET /health/backup` em produção devolve **HTTP 200
`{"status":"API online"}`** — o catch-all, não o endpoint. A `staging`
(= produção) não tem `tasks/backup.py` nem a rota; ambos vivem só na `develop`.

**Produção não tem backup automático e não tem como saber que não tem.**
Sai desse estado com a promoção `develop → staging`, que é gate humano.
