# D-183 · O `commit: unknown` era o próprio CI, ⛔ não um invasor

**Data:** 2026-08-18 · **Status:** ✅ vigente · **Risco:** RSK-001 (abaixo)

**A hipótese que caiu.** Registrei em #425 que um `railway up` de outra sessão havia sobrescrito o
deploy por git. ⚠️ **Estava errado**, e a correção importa porque a ação recomendada em cima dela era
rotacionar o `RAILWAY_TOKEN` — o que teria **quebrado o deploy do próprio projeto** sem trancar
ninguém.

**O que os metadados dizem.** Dez de dez deployments sem proveniência batem com um run do workflow
`Deploy → Railway Desenvolvimento`, 15-25 s depois:

| run do CI | deployment |
|---|---|
| 20:08:56 · 20:12:18 · 20:12:47 · 20:12:50 · 20:13:44 | 20:09:17 · 20:12:32 · 20:12:57 · 20:13:00 · 20:13:54 |
| 20:14:03 · 20:14:47 · 20:16:46 · 20:35:18 · **20:53:05** | 20:14:15 · 20:15:04 · 20:17:03 · 20:35:32 · **20:53:31** |

⛔ Nenhum sobrou sem run correspondente.

**A causa: dois deployers no mesmo serviço.**

| deployer | proveniência |
|---|---|
| integração nativa do Railway (`source: repo logikos33/Recognition, branch develop`) | ✅ `commitHash` + `branch` |
| workflow do repositório (`railway up --detach --ci`) | ⛔ upload local, sem `RAILWAY_GIT_COMMIT_SHA` |

`commit: unknown` **é o CI vencendo a corrida contra a integração nativa**. Mesma forma de [[D-181]] e
do inventário §5: **dois escritores, sem dono**.

**Correção do horário que eu afirmei:** o deploy por git do #469 (`6730144`) foi criado às 20:39:38 e
ainda promovia quando li `unknown` às 20:40 — quem servia era o deploy do CI das 20:35:32. A
sobreposição real foi às **20:53:31**. Direção certa, ⛔ agente e horário errados.

**Decisão.** Tirar o job de `railway up` e deixar a integração nativa — **exatamente o que já foi feito
para o Frontend**, com o motivo escrito no cabeçalho do próprio workflow. ⚠️ **Bloqueado pelo #475:**
`workflow_run` executa a definição de `main`, então a correção feita na `develop` ⛔ não vale até
promover.

## RSK-001 · Rotação do `RAILWAY_TOKEN` — ⛔ NÃO ROTACIONAR

| | |
|---|---|
| **Hipótese inicial** | token vazado; `railway up` de terceiro |
| **Verificado** | ⛔ falso — 10/10 correlacionam com o CI do próprio repo |
| **Efeito da rotação hoje** | quebra o job de deploy do repositório; ⛔ não tranca invasor (não há) |
| **Efeito colateral** | `commit: unknown` sumiria — por **quebrar** o segundo deployer, ⛔ não por consertá-lo, deixando workflow vermelho permanente |
| **Recomendação** | ⛔ não rotacionar. Remover o job (#425) e destravar o #475 |
| **Quando reavaliar** | se aparecer deployment sem proveniência **sem** run de CI correspondente — aí é vazamento de verdade e vira incidente |

⚠️ **O gatilho de reavaliação é o que fica.** A detecção já existe (`/livez` + `list-deployments`); o
que faltava era o critério. **Deployment sem proveniência E sem run de CI no mesmo minuto = incidente
de segurança.** Com run correspondente = o desenho atual, ruidoso e conhecido.
