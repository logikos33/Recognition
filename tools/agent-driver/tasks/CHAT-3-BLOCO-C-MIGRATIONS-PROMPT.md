# CHAT 3 / 3 — Bloco C (Onda 2): migrations

> **Como usar:** abra um chat NOVO do Claude Code e mande:
> *"Leia e execute `tools/agent-driver/tasks/CHAT-3-BLOCO-C-MIGRATIONS-PROMPT.md`."*
> **Cole junto o relatório do PORTÃO B** (CHAT 2).
> ⚠️ **Este é o bloco mais perigoso da fila** — mexe no caminho que já derrubou o startup da API uma vez, e o
> passo C5 toca banco de produção. Leia o C5 inteiro antes de começar.

```
[SESSÕES PARALELAS — leia antes de tudo]
Há OUTRA sessão do Code ativa em services/edge-sync-agent/**.
- VOCÊ é dona de: infra/migrations/** , railway_start.py , services/api/**
- NÃO TOQUE em: services/edge-sync-agent/**
- Antes de editar, confirme que a develop não mudou no arquivo desde sua cópia (git fetch + diff).
  Teste existente falhando de forma inesperada = sinal de colisão: PARE e reporte.
- ⛔ NUNCA rode `git clean` (nem -fd/-fdx). Já apagou ADR, runbooks e um .pptx nesta árvore.
```

> **Modelo: Sonnet 5.** · **Referências:** `docs/CADERNO_SOLUCOES_MUTIRAO.md` § D-04,
> `docs/REGISTRO_DIVIDA_TECNICA.md`. **Pré-requisito:** CHAT 1 e CHAT 2 concluídos.

## O problema

**Existem dois runners divergentes, e o que roda em produção é o pior dos dois:**

| | `infra/migrations/run_migrations.py` | `railway_start.py:55-89` ← **este é o de produção** |
|---|---|---|
| Tabela de controle | ✅ `schema_migrations` | ❌ **nenhuma** — reexecuta os 50+ SQLs a cada boot |
| Advisory lock | ❌ | ❌ |
| Falha aborta o boot? | — | ❌ **não** — loga o erro e **continua**; a API sobe com schema incompleto |
| `"already exists"` | marca como aplicada | trata como sucesso |
| Quem chama | **ninguém** | `railway_start.py:486` |

E o fallback de diretório (`:61-70`) tenta `infra/migrations/*.sql` e, se não achar, `migrations/*.sql` — **os dois
existem, com conteúdo diferente**. CWD diferente = aplica o conjunto errado, em silêncio.

Mais: **6 arquivos no prefixo `052`** (resolvidos por ordem alfabética, arbitrária em relação à intenção);
16 números ausentes (042–045, 053–064); `051:44` e `080:64` criam **ambos** `device_claim_codes.code_hash` e o
índice `idx_dcc_hash`.

**Precedente:** a ADR-0021 registra que uma colisão de numeração **já derrubou o startup da API**.

---

## C1 · Guard-rail de CI (faça primeiro — ~30 min, mata a classe do bug)

Três checks que teriam evitado o incidente:
- **prefixo duplicado** → falha o build (`sort | uniq -d` no prefixo numérico)
- existência de **dois diretórios** de migration → falha
- aplicar em banco limpo **2×** (idempotência) e **diffar o schema resultante**

Entregue isto **antes** de mexer no runner. É a rede que segura o resto do bloco.

## C2 · Unificar os runners + falha aborta o boot

Um runner só. **Migration que falha para o boot** — hoje a API sobe com schema incompleto, que é a pior das duas
falhas possíveis (silenciosa e progressiva).

Matar o fallback de diretório e **remover o `migrations/` da raiz** — **arquivar, não deletar**.

⚠️ A heurística que trata `"already exists"` / `"duplicate"` como sucesso **deve morrer junto**: ela mascara
divergência de schema (a tabela pode existir com colunas diferentes e você nunca saberia). Idempotência vem do
**ledger**, não da mensagem de erro. `IF NOT EXISTS` fica só como cinto de segurança secundário.

## C3 · Ledger de verdade

`public.schema_migrations (tenant_schema, version, checksum, installed_rank, installed_on, success)` com
**`UNIQUE (tenant_schema, version)`** — essa constraint sozinha teria matado o bug dos 6× `052`.

- `checksum` detecta edição de migration **já aplicada** (hoje isso passa despercebido)
- `installed_rank` guarda a ordem **real** de aplicação, que não é a ordem do nome
- `success` distingue "aplicada" de "falhou no meio"

## C4 · Advisory lock — atenção à armadilha

Use **`pg_advisory_xact_lock`**, **não** `pg_advisory_lock`.

⚠️ O lock de **sessão** vive na **conexão**: pegar numa conexão do pool e liberar em outra faz o unlock virar
**no-op silencioso**; a conexão volta ao pool ainda segurando o lock e **todo boot futuro trava para sempre**, sem
saída a não ser matar a sessão no servidor. A variante `_xact_` libera automaticamente no fim da transação.

Se por algum motivo precisar do lock de sessão: conexão **dedicada, fora do pool**, com `try/finally` e
`lock_timeout` — e nunca `pg_advisory_lock` sem timeout, que trava o boot indefinidamente.

*(DDL no Postgres é transacional, então `pg_advisory_xact_lock` + DDL na mesma transação é a combinação limpa.
Exceção: `CREATE INDEX CONCURRENTLY` não roda em transação — se houver alguma, trate à parte.)*

## C5 🔴 · BACKFILL antes do cutover — o passo que pode quebrar produção

**Leia isto duas vezes.** A `schema_migrations` chega **vazia** num banco que já tem tudo aplicado. Sem backfill, o
runner novo tentaria **reaplicar os 50+ SQLs** — e a única coisa que hoje segura isso é justamente a heurística
`"already exists"` que o C2 remove.

Ordem obrigatória, sem atalho:
1. **`INSERT`** de todas as versions já aplicadas, em **cada ambiente** (dev, staging, produção);
2. **Provar** que o runner novo, contra esse banco, aplica **zero** migration;
3. **Só então** o cutover.

Rodar o **harness 2×** (`services/api/tests/harness/migrations/`) — ele existe e é a rede de segurança.

Fechar junto a PEND registrada no README do harness: *"unificar o loop de apply do `railway_start` com o
`runner.py` do harness"*. Hoje o harness **espelha deliberadamente** o código de produção — unificar é o que faz o
teste passar a valer alguma coisa.

⚠️ **O backfill em produção é operação coordenada com o Vitor.** Não execute sozinho: prepare, mostre o script,
mostre o resultado em dev e staging, e **aguarde autorização** para produção.

---

## ⛔ Fora de escopo deste chat

**Não faça o CDRB** (baseline único + renumeração por timestamp). Exige congelamento de migrations e reconciliação
entre dev, staging e produção — é operação humana coordenada, não tarefa de sessão. **Deixe proposto em documento**
(`docs/`), com o procedimento e os riscos, para o Vitor agendar.

Também fora: credenciais/rotação (Onda 0) · arquitetura de vídeo (Onda 4) · cursores e `base.py` (Onda 5, 208
chamadores) · migração para Alembic/Atlas/dbmate (só faz sentido depois que o ledger existir — ver
`CADERNO_SOLUCOES_MUTIRAO.md` § D-04 para o comparativo).

## 🚪 PORTÃO C

- **Harness 2× verde**
- **Backfill provado**: runner novo aplica **zero** migration num banco já migrado — mostre a saída
- CI reprovando prefixo duplicado (demonstre criando um arquivo colidente de propósito e mostrando o build falhar)
- Diretório `migrations/` da raiz arquivado
- Migration que falha **aborta o boot** — demonstrado
- Proposta do CDRB escrita em `docs/`, não executada

**Live view continua funcionando** — verifique antes e depois.

Um PR por tema. `ruff check .` limpo · conventional commits. **Não promover para `staging`/`main`** — gate humano.

## Segurança

- Não expor em log/commit/PR: `DATABASE_URL`, JWT, tokens, senhas, chaves R2.
- Produção (host `interchange`): **somente leitura**, com a única exceção do backfill do C5 — que é **coordenado e
  autorizado pelo Vitor**, nunca autônomo.
- Migrations são **forward-only**: nada de `DROP`, `ALTER COLUMN TYPE`, `DELETE FROM`, `TRUNCATE`. Nunca editar
  migration já aplicada — criar uma nova para corrigir.
