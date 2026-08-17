# Rodada consolidação + pôr o modelo para trabalhar — realidade e bloqueios

- **Tipo:** Registro de rodada → decisões D-116..D-119
- **Data:** 2026-08-17 · **Escopo:** somente DEV · **Módulo:** EPI · **Tenant:** RVB
- **Árvore de trabalho:** clone limpo de `origin/develop` em **`/private/tmp/recognition-clean-develop`** — HEAD `713a3cb2` (merge #354), **111 arquivos de migration, nº máx `122`** (a árvore errada do iCloud tinha 12). Todo subagente recebeu caminho absoluto.
- **Garantias:** zero código de produto alterado · **nenhum segredo impresso** (nenhum foi lido/gerado) · nada minerado · não toca `staging`/`main`/`interchange` · nenhum PR fechado · nenhum `--force`/`squash`.

---

## 0 · Divergências prompt × repo (segui o repo)

| Prompt | Repo/GitHub (verificado) | Segui |
|---|---|---|
| "mergear tudo" (exceto #375/#293/#259) | 🔴 **Todo PR aberto está VERMELHO** no check pré-existente `SCA (npm audit) (landing)` (falha idêntica em #385/#343/#387 — dep da landing, alheia aos diffs). Regra "CI vermelho PARE" → **não mergeei nada.** `develop` é **branch não-protegida** (sem check obrigatório) — GitHub deixaria, mas a disciplina do prompt não | repo |
| #384 é mergeável (aba Classificar) | 🔴 **#384 CONFLITA** (`DIRTY`/`CONFLICTING`) e toca `versioning_v2.py` + `test_coco_supercategory.py` — exatamente o arquivo que o prompt avisa que reverte o #378. Não mergeável sem resolver conflito no arquivo delicado → **PARE** | repo |
| Registrar "a partir de D-112" | D-112..D-115 **já usadas** pela rodada de mineração (PR #386). Esta rodada começa em **D-116** | repo |
| "aba Classificar já existe" (bloco 3) | A aba Classificar vive no **#384 não-mergeado**; **não está no DEV** hoje | repo |

---

## 1 · As 4 correções sobrevivem em `develop` (prova `file:line`)

| PR | O quê | Prova em `/private/tmp/recognition-clean-develop` |
|---|---|---|
| **#378** | supercategory → `module_code` (raiz do CUDA assert) | `services/api/app/infrastructure/queue/tasks/versioning_v2.py:402` `"supercategory": module_code` (threaded em :69,:89,:95,:101) |
| **#381** | migrations 118–122 | `infra/migrations/118_camera_fps_quality.sql` … `122_model_scenario_config.sql` (5 presentes) |
| **#382** | link `job_id[:8]` + alerta-não-mata | `services/api/app/infrastructure/queue/tasks/gpu_reconciler.py:161` `_load_active_job_id_prefixes`; docstring :21-22 "ALERTA (log), NÃO termina" |
| **#376** | gate de docs (procedência) | job "Docs gate (procedência — ADRs, citações, taxonomia RVB)" em `.github/workflows/ci.yml` (passou em #343/#387) |

**As correções que importam já estão em develop.** Os merges pendentes são docs/tooling — não afetam o que roda no DEV.

---

## 2 · Merges — o que foi decidido, por PR

| PR | Tipo | Decisão | Motivo |
|---|---|---|---|
| #384 `classificacao-rapida-dvr` | feat (Classificar + minerador) | ⛔ **não mergear** — recomendar rebase | CONFLITA + toca supercategory; risco de reverter #378 |
| #375 `treino1-contagem-classes` | feat (modelo + métrica) | ⛔ **não mergear** — extrair + recomendar fechar | (exceção do prompt) conflita `versioning_v2.py` |
| #293 `cameras-ao-vivo` | docs (D-33..D-36) | ⛔ extrair + recomendar fechar | D-33..D-36 já estão em develop; trabalho foi operacional (dados), não código |
| #259 `docs-observabilidade` | docs (mapa consumo) | ⛔ extrair + recomendar fechar | investigação read-only que empacou por falta de fonte; achado útil abaixo |
| #343 `docs-registro-runpod` | docs (D-85..D-88) | ⏸️ mergear quando CI verde | vermelho só no npm-audit-landing pré-existente |
| #385 `analysis/aws-ppe-lessons` | docs (D-107..D-111) | ⏸️ mergear quando CI verde | idem |
| #386 `mineracao/lote1-realidade` | docs (D-112..D-115) | ⏸️ mergear quando CI verde (rebaser p/ develop) | idem; hoje aponta p/ #385 |
| #387 `r2-ro-verifier` | feat (verificador R2) | ⛔ não mergear (outra sessão, draft) — recomendar | é o tool que destrava o bloco 2 (ver §3) |

**Valor extraído dos que fecham:**
- **#375:** métrica por classe no worker (migration 098 dormente → suporte/P/R/F1/confusão/procedência) + **3 bugfixes de export/executor**. 🔴 Reextrair esses num branch limpo **sobre develop atual** (que já tem o #378), nunca mergear o #375 como está. Entrada **D-102** do #375 para o REGISTRO.
- **#293:** cadastro das 8 câmeras RVB no DEV já foi feito (operacional); D-33..D-36 já em develop.
- **#259:** achado `edge/routes.py:586` — `data = file.read()` lê o corpo inteiro **antes** da validação de 5 MB (`:589`) → o teto não protege memória. Vale como issue.

---

## 3 · O modelo `8e8fedf7` — avaliação BLOQUEADA + desenho do ordenador

**Não avaliei o modelo — bloqueado em credenciais.** Rodá-lo contra os 377 frames de verdade humana exige: **(1)** baixar o ONNX 108 MB do **R2** (sem credencial R2), **(2)** os próprios 377 frames (no R2), **(3)** as anotações-verdade (no **DEV DB**, sem acesso). Nenhum dado saiu; nada foi baixado. ⚠️ Não confirmei sequer a linha `trained_models 8e8fedf7` (sem DB) — assumo a presença do prompt.

🔴 **#387 (`r2-ro-verifier`) é literalmente o verificador R2 read-only + runbook de provisionamento** — a ferramenta que destrava exatamente isto. Passo do Vitor: provisionar **R2 read-only, só bucket DEV** + **DEV DB read-only** (senha vazada — rotacionar).

### Desenho do ORDENADOR (pronto para quando destravar) — ⛔ jamais rotulador

**Já provado que rotular com saída de modelo falha:** SAM+DINOv2 → 1005 propostas → 100% rejeitadas. Então o modelo **só escolhe a ORDEM da fila**, o humano decide tudo.

1. **Batch inference** (job worker, no DEV) roda o ONNX sobre os frames não-anotados → por frame, um **score de ordenação** = maior confiança de detecção (ou nº de detecções acima de um limiar baixo).
2. **Persistir só o score**, nunca rótulo: coluna nullable `model_order_score` em `training_frames` (ou metadado em `pre_annotations` **sem** popular `annotations`). ⛔ Zero proposta, zero caixa pré-preenchida.
3. **Fila existente** (`GET /api/training/videos/<id>/frames` / triagem) ganha `order_by=model_score` opcional — onde dispara ao topo, onde não dispara ao fim.
4. **Medir o ganho:** quantos frames o Vitor rola para achar 50 anotáveis, **ordem aleatória vs ordem-do-modelo**. Se o ganho for pequeno (< ~1,5×), **DIGA e desligue** — não force.
5. **Bloco 3 (laço de revisão) — DESCOPADO** nesta rodada (prioridade era DEV testável). Quando vier: registrar o **desfecho** (confirmou/corrigiu/falso-positivo) **estendendo** o `curation_status` existente (`'excluida'`/`'duvida'`, migration 110) + um `model_agreed` nullable — ⛔ **sem tela nova**. Falso-positivo = exemplo negativo (só entra no treino via `humana`, nunca a saída do modelo sozinha).

---

## 4 · DEV no ar — o que dá para fazer hoje

| Alvo | Estado |
|---|---|
| API `https://api-v3-desenvolvimento.up.railway.app` | ✅ `/health` `{"checks":{"database":true,"redis":true},"status":"healthy"}`; `/livez` `/healthz` `/api/health` = 200 |
| Frontend `https://frontend-desenvolvimento-be93.up.railway.app` | ✅ 200 |
| Migrations | ✅ implícito (DB check healthy; Railway roda no boot; código até `122`) |
| **aba Classificar** | 🔴 **indisponível** — vive no #384 não-mergeado/conflitante |

**O Vitor consegue hoje:** logar (com conta DEV), navegar o frontend, usar a anotação existente (`SearchFindingsPanel`, desenho de caixa). **Não consegue:** a aba Classificar (bloqueada no #384) nem o modelo ordenando a fila (bloqueado em R2/DB).

---

## 5 · O que ficou bloqueado — passo exato do Vitor

1. 🔴 **Merges:** bumpar a dep vulnerável da **landing** (ou marcar `SCA (npm audit) (landing)` como advisory) → aí #343/#385/#386 mergeiam com CI verde.
2. 🔴 **aba Classificar no DEV:** rebase do **#384** sobre develop atual **preservando** `"supercategory": module_code` (§1) → resolver o conflito de `versioning_v2.py` → merge.
3. 🔴 **Avaliar o modelo + ordenador:** provisionar **R2 read-only (bucket DEV)** + **DEV DB read-only** (rotacionar a senha vazada). #387 já é o verificador.
4. **#375/#293/#259:** fechar (ato do Vitor) após reextrair o valor do #375 num branch limpo.
5. Pendências herdadas: mapear `RECORDER_CHANNEL_MAP`, provisionar o beat, extrair a gravação de 31/07, **apagar o checkout do iCloud** (enganou o subagente).

---

## Apêndice — método e segredos

Clone limpo declarado no topo. Verificações `gh`/`git`/`curl` read-only. **Nenhum segredo impresso, lido ou gerado.** Um subagente da rodada anterior leu a árvore errada (iCloud, 12 migrations) e foi descartado — por isso todo caminho aqui é absoluto e a contagem de migrations foi conferida (111 arquivos, nº máx 122).
