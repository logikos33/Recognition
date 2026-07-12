# ADR-0039 — TrainingCompute: abstração de provedor de treino (Vast.ai / Edge / Local)

**Status:** Aceita (2026-07-12) · **Estende:** ADR-0038 (Vast.ai provisioning real), ADR-0037
(contrato de API) · **Implementado em:** PR-5 (`feat/tp5-compute-providers`).

## Contexto

`tasks/training.py::dispatch_training` escolhia o backend de treino via um `if/elif/else` direto
sobre env vars (`VAST_API_KEY` → `ULTRALYTICS_HUB_API_KEY` → simulação). Isso funcionava, mas
misturava a DECISÃO de onde treinar com a lógica de CADA backend, e não deixava espaço óbvio pra um
provedor novo (treino no edge, Jetson do cliente) sem inflar ainda mais o `if/elif`.

## Decisão

### Interface `TrainingCompute`

Uma classe por provedor, um método (`dispatch(job_id, dataset_version_id, model_size, epochs, imgsz,
batch, update_fn, tenant_id=None) -> dict`), retorno no MESMO shape que os dispatchers síncronos já
usavam: `{"model_path", "metrics", "source", "status"?}`. `status` ausente == `"completed"`
(retrocompat); `"running"` sinaliza dispatch assíncrono (hoje só `EdgeProvider` — ver pendência
abaixo).

- **`VastAiProvider`** — wrapper fino sobre `_dispatch_vast_ai` (ADR-0038, já validado em produção
  contra a API REST real). Zero lógica nova; só delega.
- **`LocalProvider`** — wrapper fino sobre `_simulate_training` (fallback funcional sem GPU, ~20s).
  Validado rodando o corpo real da função (só `time.sleep` acelerado no teste) — é o único dos 3
  provedores que roda de ponta a ponta neste ambiente de dev sem depender de credencial externa.
- **`EdgeProvider`** — **BLOQUEADO-HARDWARE**, ver seção dedicada abaixo.
- **`get_training_compute(tenant_id) -> TrainingCompute`** — factory com a precedência:
  1. `resolve_vast_api_key(tenant_id)` resolve uma chave (integration store do tenant → env
     `VAST_API_KEY`) → `VastAiProvider`.
  2. Feature flag `tenants.feature_flags.training_compute_target == "edge"` **e** o tenant tem ≥1
     `edge_sites` cadastrado → `EdgeProvider`. Sem site cadastrado, cai pra local com warning (nunca
     falha o job por causa de configuração incompleta).
  3. Default → `LocalProvider`.

O caminho Ultralytics Hub (`_dispatch_hub`) **não foi tocado nem envolvido na abstração** — segue como
branch separada em `dispatch_training` (fora do escopo deste ADR; é um fallback terciário/legado, sem
pedido explícito pra virar um provider formal).

### `compute_target` reusa `training_jobs.gpu_provider` (migration 097) — zero migration nova

Achado de grounding (mesmo padrão do PR-4: checar o schema real antes de assumir que precisa de coluna
nova): `training_jobs.gpu_provider VARCHAR(20)` **já existe** desde a migration 097, **já é gravado**
hoje (`'vast_ai'` em `_run_vast_remote_training`) e **não tem CHECK constraint** restringindo valores
— extender o enum (`app.constants.GpuProvider`) com `EDGE = "edge"` é um code change, não uma
migration. `compute_target` como conceito É esta coluna; não criamos uma segunda.

### Bug achado construindo a abstração: gate do Vast.ai não era tenant-aware

`dispatch_training` decidia usar Vast.ai com `os.environ.get("VAST_API_KEY", "")` — um check de env
puro — enquanto o próprio docstring do módulo já alegava "VAST_API_KEY resolvível — integration store
do tenant > env" (e `_dispatch_vast_ai` internamente JÁ fazia essa resolução correta via
`_get_vast_context`/`resolve_vast_api_key`, só que tarde demais: o gate externo decidia primeiro se
sequer chamava `_dispatch_vast_ai`). Resultado: um tenant com chave Vast.ai configurada SÓ no
integration store (sem `VAST_API_KEY` no ambiente) nunca disparava o dispatch real — caía direto pra
Hub/simulação, silenciosamente. Corrigido: o gate agora usa `resolve_vast_api_key(tenant_id)` (mesma
função, já existente, já testada) antes de decidir. Teste falha-antes/passa-depois em
`test_training_dispatch_task.py::test_tenant_scoped_vast_key_triggers_dispatch_without_env_var`.

## EdgeProvider — BLOQUEADO-HARDWARE (não alegar E2E)

**O que existe e foi construído nesta PR:**
- `EdgeProvider.dispatch()` enfileira um `edge_command` (`command_type="start_training"`, mesma
  tabela/repository já usados por `update_camera_config` — `app/api/v1/cameras/config_handler.py`,
  `EdgeCommandRepository`) pro site mais recente do tenant, com o payload do job (job_id,
  dataset_version_id, model_size, epochs, imgsz, batch). Fail-loud: se o enqueue falhar, a exceção
  propaga — nunca finge que um treino começou quando o enqueue não aconteceu.
- Testado inteiramente com mock (`EdgeCommandRepository`/`EdgeSiteRepository` mockados) —
  `tests/unit/infrastructure/test_training_compute.py::TestEdgeProvider`.

**O que NÃO existe e é bloqueado por hardware:**
- O `edge-sync-agent` (`services/edge-sync-agent/app/command_poller.py`) hoje só sabe processar
  `update_camera_config` — não há handler pra `start_training`, nem um script de treino real
  equivalente ao `remote_train.py` do Vast.ai (ADR-0038) pra rodar num Jetson.
- Não existe callback de conclusão do lado do edge (o `dispatch_training` deixa o job em `'running'`
  e retorna sem criar `trained_models` — ver contrato `status="running"` acima; nada completa esse
  job hoje).
- **Nunca validado contra hardware real.** Ver issue de rastreio "Validação de hardware: treino real
  no edge-sync-agent (Jetson)" — mesmo padrão da issue de validação de hardware NVR/DVR (#131).

**Por que seguir mesmo assim**: o pedido era desenhar + testar com mock a abstração pra permitir
plugar o provider real quando o hardware/handler existir, sem re-arquitetar `dispatch_training` outra
vez — não implementar treino real no Jetson (que exigiria hardware físico pra validar de verdade, e
"NÃO alegar E2E" foi explícito).

## Caminho Vast.ai/R2 real: construído, não E2E (paralelo, não bloqueia)

`VastAiProvider` e o gate corrigido estão prontos e cobertos por teste unitário, mas o dispatch REST
real contra a API Vast.ai **não foi exercitado E2E nesta sessão** — falta `VAST_API_KEY` (não
disponível no Railway dev) e o token R2-dev segue com o mesmo problema de escopo de bucket já
reportado (`epi-monitor-dev` fora do escopo do token atual). Isso não bloqueia esta PR — é o mesmo
estado documentado desde o fechamento da Fase A.

## Consequências

- Novo provider (real edge training, ou um segundo provedor cloud) implementa `TrainingCompute` e
  entra na factory — `dispatch_training` não precisa mudar de novo.
- `compute_target`/`gpu_provider` continua sendo a fonte de verdade de "onde este job rodou/vai
  rodar" — sem duplicar o conceito em uma coluna nova.
- EdgeProvider em produção hoje enfileiraria o comando com sucesso (a tabela/repository são reais),
  mas o job ficaria preso em `'running'` pra sempre — nada no `edge-sync-agent` processa
  `start_training` nem completa o ciclo. Opt-in explícito por flag (`training_compute_target=edge`),
  nunca default, exatamente por causa dessa lacuna.
