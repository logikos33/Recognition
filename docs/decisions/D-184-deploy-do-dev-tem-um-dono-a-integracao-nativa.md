# D-184 · O deploy do DEV passa a ter UM dono: a integração nativa

**Data:** 2026-08-18 · **Status:** ✅ vigente · **Executa:** [[D-183]] · **Issue:** #425

**O problema.** Dois deployers no mesmo serviço, correndo a cada merge:

| deployer | proveniência | resultado |
|---|---|---|
| integração nativa do Railway | ✅ `commitHash` + `branch` | `/livez` diz qual commit está no ar |
| `railway up` do workflow | ⛔ upload local, sem `RAILWAY_GIT_COMMIT_SHA` | `/livez` diz `unknown` |

Quem chega por último vence, e o CI costuma chegar por último — foi assim que o DEV passou ~40 min
servindo `commit: unknown` numa semana de piloto.

**Decisão: o dono é a integração nativa.** O workflow inteiro sai.

**Verificado antes de remover** (`get-service-config`, ⛔ não presumido):

| serviço | `source` |
|---|---|
| API-V3 | `repo logikos33/Recognition`, branch `develop`, root `""` |
| Frontend | `repo logikos33/Recognition`, branch `develop`, root `apps/frontend` |

Os dois já deployam sozinhos. O workflow era **redundante nos dois jobs**, ⛔ não só no do Frontend.

**Precedente no próprio arquivo.** O cabeçalho já dizia, sobre o Frontend: *"era redundante E quebrado
— o serviço Frontend do Railway já auto-deploya de develop"*. A mesma conclusão nunca foi aplicada à
API-V3, que estava na mesma situação.

**O que se perde: nada que segurasse alguma coisa.** O único passo além do `railway up` era um smoke
test escrito como `curl … || echo "::warning::"` — ⛔ nunca reprovava. Era decoração, e some como
decoração.

⚠️ **Isto ⛔ não tem efeito até chegar em `main`.** `workflow_run` executa a definição da branch
default ([[#475]]), então o workflow removido aqui **continua rodando a partir de `main`** — e o
`commit: unknown` continua oscilando até a promoção. **Enquanto isso, a prova do que está no ar é
ancestralidade contra o commit SERVINDO, ⛔ não contra a `develop`.**

**Descartado:** trocar `railway up` por um deploy com `RAILWAY_GIT_COMMIT_SHA` explícito. Consertaria a
proveniência e ⛔ manteria os dois deployers — dois escritores continuam sendo dois escritores, ainda
que ambos honestos. O padrão de [[D-181]] e do inventário §5 é **escolher um dono**, não fazer os dois
mentirem menos.
