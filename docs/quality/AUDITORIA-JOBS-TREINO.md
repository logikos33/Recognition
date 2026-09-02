# Auditoria retroativa — quem disparou treino, e quanto custou

> Read-only. Banco: **DEV** (`training_jobs`/`trained_models`, schema `public`). Consulta em
> 2026-09-02. Nenhuma linha alterada. Achado motivador:
> `POST /api/training/jobs` (`services/api/app/api/v1/training/routes.py:213-217`) tem só
> `@limiter.limit` + `@jwt_required()` — **zero `@require_training_role`** — confirmado lendo o
> arquivo nesta sessão. Esta auditoria mede o que esse gap já produziu em dados reais, não o que
> ele poderia produzir.

## Resposta direta à pergunta do Vitor

**Sim.** 39 dos 40 `training_jobs` já registrados foram disparados por um ator com `role='admin'`
— não `superadmin`. Só 1 job (o primeiro, 2026-07-02) partiu de superadmin. `admin` é papel
**atribuível por tenant** (é o próprio motivo do achado original: `training:write` e
`models:approve` incluem `admin`, só `training:approve` é superadmin-only) — ou seja, o gate que
falta hoje já foi exercitado 39 vezes por exatamente o papel que a regra do produto proíbe.

Dessas 39, **38 rodaram no tenant real da RVB** (`rvb`, id `63c219d8-…82e2`) e **produziram um
modelo que está ativo agora** (seção 4). O ator identificado nessas 38 é conta de uso
interno-Logikos (`vitor@logikosvision.com.br`, `claude-ops@recognition.dev`) com `role=admin`
atribuído no tenant RVB para operação/teste em DEV — não uma conta de funcionário da RVB. Isso não
muda a exposição: o gate de permissão não distingue quem segura a credencial `admin`, só o papel;
se a RVB atribuir `admin` a um funcionário próprio (o produto permite isso — é o modelo de
papéis por tenant), esse funcionário dispara o mesmo treino pago, hoje, sem qualquer bloqueio.

## 1. Proveniência do ator — a coluna existe e está 100% preenchida

| Pergunta | Resposta medida |
|---|---|
| Existe coluna de ator? | `training_jobs.user_id UUID NOT NULL REFERENCES users(id)` desde a criação da tabela (migration `003_training.sql`) |
| Está preenchida? | **Sim, em 40/40 jobs** (`count(*) filter (where user_id is null) = 0`) |
| Dá pra saber o papel **na época**? | **Não.** `users.role` é o papel **atual**, sem histórico (não existe `role_history`/`audit_log` de mudança de papel no schema — migrations `052_custom_roles.sql`/`120_custom_roles.sql` adicionam papéis customizados, não versionam o campo). O papel reportado abaixo é o de **hoje**; se algum desses 4 usuários já teve o papel trocado, o histórico real diverge disso. |
| Overrides pontuais (`user_permission_overrides`) contam? | Não cruzados — não há timestamp de concessão/revogação do override, então não dá pra saber se um override estava ativo no instante do job. Risco residual não medido, não inventado. |

**Não é o achado desta rodada** (ao contrário do que o contrato temia) — proveniência de ator
existe e está completa. O achado é o que a seção seguinte mostra: o ator gravado, no papel atual
que ele tem, **não deveria ter conseguido** disparar o job.

## 2. Todos os 40 jobs

| quando | ator | papel atual | tenant | status | custo USD | pod RunPod |
|---|---|---|---|---|---|---|
| 2026-07-02 00:43 | vitor@devlogikos.com | **superadmin** | default | stopped | — | — |
| 2026-07-12 17:53 | e2e-fase-a@validation.local | admin | e2e-fase-a-validation (fixture CI) | completed | — (local_mps) | — |
| 2026-08-13 00:15 → 19:17 (7×) | vitor@logikosvision.com.br | admin | **rvb** | 6 failed, 1 sem pod | — | 5 de 7 |
| 2026-08-14 19:28 | vitor@logikosvision.com.br | admin | rvb | completed | 0.22 | 63armpim… |
| 2026-08-18 01:00 → 09:32 (8×) | claude-ops@recognition.dev | admin | rvb | failed | — | 8/8 |
| 2026-08-18 10:27, 11:38 | claude-ops@recognition.dev | admin | rvb | completed | 0.33, 0.33 | 2 |
| 2026-08-20 03:06 → 13:04 (5×) | claude-ops@recognition.dev | admin | rvb | pending | — | — |
| 2026-08-20 14:03 → 23:54 (4×) | claude-ops@recognition.dev | admin | rvb | 2 failed, 1 completed, 1 stopped | 0.33, 0.33, 1.10, — | 3 |
| 2026-08-21 00:10 → 13:44 (3×) | claude-ops@recognition.dev | admin | rvb | completed | 0.15, 0.061, 0.0609 | 3 |
| 2026-08-24 21:40, 22:06 | claude-ops@recognition.dev | admin | rvb | failed, completed | —, 0.0778 | 0, 1 |
| 2026-08-25 03:20 (×2), 03:21, 06:45 | vitor@logikosvision.com.br | admin | rvb | failed, completed×3 | —, 0.7084, 1.70, 0.0412 | 0, 3 |

**n = 40** (`select count(*) from public.training_jobs`). Lista linha-a-linha completa (job id,
timestamps, pod id) reproduzível com a query em `scripts/` desta sessão — omitida aqui por
espaço, disponível sob pedido.

## 3. Cruzamento com a matriz de papéis — quantos, quando, quanto custaram

| role do ator | n jobs | tenant(s) | custo confirmado (`actual_usd`) | custo só-estimado (`estimated_usd`, sem billing real) | sem registro de custo* |
|---|---|---|---|---|---|
| **superadmin** | 1 | default | $0 (nunca chegou a rodar no RunPod) | — | — |
| **admin** (papel de tenant) | **39** | rvb (38) + e2e-fase-a (1, local_mps/$0) | **6 jobs → $1,10** | **7 jobs → $4,34 (ESTIMATIVA)** | **19 jobs `runpod` sem `metrics.gpu_cost`** |

\* Dos 19 jobs `runpod` de ator `admin` sem custo gravado, **15 têm `gpu_instance_ref` (pod real
criado)** e 4 não chegaram a criar pod. Ou seja: em 15 desses runs a GPU paga **rodou de fato**
(billing real do RunPod existe na conta), mas o valor nunca foi persistido em `training_jobs` —
provavelmente falha antes do watchdog consultar o billing (`runpod_runner.py`, `_watch`). O custo
real desses 15 **não está nesta base** — não dá pra estimar sem consultar o billing do RunPod
diretamente (fora do escopo read-only-DB deste contrato).

**Total visível no banco atribuível a `admin` (não-superadmin): $5,44** ($1,10 confirmado +
$4,34 estimado) **+ custo real desconhecido de 15 pods RunPod adicionais que rodaram sem deixar
valor gravado.** $5,44 é piso, não teto.

Nenhum job partiu de papel `operator`/`trainer`/`viewer` nestes 40 — só `admin` e `superadmin`
aparecem como ator.

## 4. Artefato em produção com proveniência de papel indevido

```
trained_models.id = 8b3bd146-1e05-45d9-a7c8-520a4f629862
  job_id       = 0307e2b1-9e5b-4fa6-a2d5-6fed12233619  (tenant rvb, ator admin=vitor@logikosvision.com.br)
  module_code  = epi
  is_active    = TRUE   ← É O MODELO ATIVO HOJE PARA O MÓDULO EPI DA RVB (nesta base DEV)
  origin       = runpod
  framework    = rfdetr
  map50 / precision / recall = 0 / 0 / 0   (métricas zeradas — ver nota)
  tem ONNX no R2 = sim · tem weights key   = não
  created_at   = 2026-08-25 07:54:55
```

**Este é o único modelo `is_active=TRUE` no tenant RVB** entre os 11 `trained_models` gravados a
partir desses jobs — nenhum outro dos 10 restantes está ativo. Ou seja: o modelo **em uso agora**
para EPI na RVB (ao menos nesta base DEV) veio de um job cujo disparo não deveria ter passado pelo
gate que falta.

Nota à parte, não é o foco desta auditoria mas registrado porque apareceu: `map50=precision=recall=0`
no modelo ativo — vale conferir se essas métricas foram de fato calculadas/persistidas no fluxo
RunPod, ou se ficaram zeradas por outro motivo. Não investigado aqui (fora do escopo desta
auditoria de proveniência).

**Ativação em si não tem ator gravado**: `trained_models` não tem coluna `activated_by`/
`updated_by` — `model_registry_repository.py::activate_for_tenant_module` faz
`UPDATE trained_models SET is_active = TRUE/FALSE` sem gravar quem chamou. Não dá pra confirmar
se a ativação (ação separada, gate `models:approve` = superadmin+admin) foi feita por admin ou
superadmin — mesma classe de lacuna de proveniência da seção 1, só que na tabela de modelos.

## Consequência

- O gap "`training:approve`-only deveria valer para `training:write` de fato disparar treino" não
  é uma preocupação teórica: **já foi exercitado 39 vezes em DEV, gerou gasto real de GPU
  (piso $5,44 confirmado/estimado + custo real desconhecido de 15 pods), e o artefato de uma dessas
  execuções está ativo em produção do módulo EPI da RVB agora.**
- Corrigir o gate (`@require_training_role("approve")` em `POST /api/training/jobs`, conforme já
  decidido no contrato original) impede recorrência — não desfaz o já ocorrido.
- Este documento não conserta nada nem escreve no banco (contrato read-only). Decisão sobre
  invalidar/retreinar o modelo `8b3bd146` é do Vitor.
