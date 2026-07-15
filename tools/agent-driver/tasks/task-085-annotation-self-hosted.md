---
title: "Treino LGPD-clean: anotação self-hosted (CVAT/Label Studio) integrada ao dataset"
pr_title: "feat(training): anotação self-hosted on-prem (sem enviar imagem a terceiro)"
commit_message: "feat(training): integração de anotação self-hosted para datasets"
eval: default
risk: security
depende_de: ADR-0047
bloco: 3 (Treino LGPD-clean)
---

# Task 085 — Anotação self-hosted

## Objetivo
Anotar datasets sem mandar imagem de trabalhador pra SaaS (LGPD). CVAT ou Label Studio on-prem.

## Escopo
- Escolher CVAT vs Label Studio; integração import/export COCO com o versionamento de dataset atual.
- Fluxo: frames (câmera/NVR/upload) → anotação on-prem → dataset versionado.

## Aceite
- [x] Ciclo de anotação → dataset COCO versionado sem terceiro; documentado.

## Checkpoint
- STOP-for-review. Coerente com docs/security/LGPD_PRIVACIDADE_CFTV.md.

## Status (2026-07-15)

**Investigação C-04 — o que já existia:**

- **Já existe ferramenta de anotação própria, self-hosted por construção**:
  `apps/frontend/src/components/AnnotationInterface.jsx` (bbox → classe,
  wrapper de validação em `pages/AnnotationPage.tsx`). Roda dentro da própria
  infra do Recognition (Railway) — nenhuma imagem de trabalhador sai para
  SaaS de terceiro em nenhum ponto do fluxo.
- **Fluxo completo frame → anotação → dataset COCO versionado já existe e
  funciona**: `frame_annotations` (`infra/migrations/003_training.sql`,
  colunas de proveniência `source/created_by/reviewed_by` desde
  `095_annotations_provenance.sql`) → endpoints em
  `services/api/app/api/v1/training/annotation_handlers.py` →
  `build_dataset_version_v2`
  (`services/api/app/infrastructure/queue/tasks/versioning_v2.py`), disparado
  manualmente via `POST /datasets/<id>/versions`
  (`services/api/app/api/v1/datasets/routes.py`) → export COCO por split →
  upload para R2 (`{R2Prefix.DATASET_EXPORTS}/{tenant_id}/{dataset_id}/{version}/...`)
  → `DatasetRepository.create_version_v2` grava `coco_r2_key`.
- **Destino da imagem é sempre R2 (Cloudflare, infra própria/controlada) ou
  disco local — nunca terceiro.** `get_storage(tenant_id)` resolve
  `R2Storage` (`https://{account_id}.r2.cloudflarestorage.com`) com fallback
  para `LocalStorage`. Grep por `roboflow.com|cvat|label-?studio` em todo
  `services/api/app` e `apps/frontend/src` não retorna nenhuma integração
  real — só as menções de planejamento nesta própria task e na ADR-0047.
- **Único uso real de Roboflow no repo é fora deste fluxo**:
  `training/vast/provision_and_train.sh` (fallback legado de treino
  Vast.ai) *baixa* um dataset público (`roboflow-100/hard-hat-workers`,
  CC BY 4.0) — não envia imagem de cliente para lá. Não faz parte do
  caminho anotação→dataset.
- **`AnnotationInterface.jsx` está marcado CONGELADO** (3 lugares:
  `apps/frontend/src/components/AGENTS.md`, `apps/frontend/AGENTS.md`,
  `apps/frontend/src/pages/AnnotationPage.tsx`), mas o freeze é contra
  refactor/estilo cosmético, não contra bugfix funcional — dois dos três
  últimos commits no arquivo são correções funcionais reais (uma já
  mergeada: `ecc02e3`, perda silenciosa de anotação; outra pendente de
  merge em branch separada: `05d0b9e`, persistência do nome da classe).
  Não há bug ativo bloqueante no caminho de anotação→dataset.
- Testes cobrindo o pipeline (`versioning_v2`, `dataset_repository`,
  `datasets/routes`, `classes/routes`) já existem e são atuais
  (`services/api/tests/unit/infrastructure/test_versioning_v2.py`,
  `test_dataset_repository_v2.py`, `test_versioning_dataset_versions.py`,
  `services/api/tests/unit/api/test_datasets_routes.py`).

**Conclusão:** o requisito LGPD do ADR-0047 ("anotação self-hosted, dado não
sai do controle da Logikos/cliente") **já está satisfeito** pela ferramenta
própria + pipeline de versionamento existentes. Não há motivo concreto
(bug bloqueante, lacuna de capability documentada em algum outro doc, ou
pedido explícito) que justifique subir CVAT ou Label Studio como
infraestrutura nova — seria custo/superfície de infra adicional sem ganho
correspondente. Ver ADR-0048, que registra essa reavaliação e supersede
parcialmente a ADR-0047 apenas no ponto "CVAT/Label Studio"; RF-DETR
(task-086) e zero-shot no onboarding (task-098) da mesma ADR continuam
válidos e fora de escopo aqui.

**Gap documental fechado nesta task:** `docs/security/LGPD_PRIVACIDADE_CFTV.md`
não mencionava onde as imagens de anotação/treino ficam armazenadas —
adicionada nota confirmando R2/self-hosted, sem terceiro (seção 3).

**Premissa da spec que se mostrou incorreta:** o texto "CVAT ou Label
Studio on-prem" presumia que não havia ferramenta própria de anotação.
Havia — construída para as Fases 1/2 do treino e já em uso por
`AnnotationInterface.jsx` + `versioning_v2.py`. Nenhuma infraestrutura nova
foi implementada nesta task (decisão de infra nova exige aprovação humana
antes de virar código rodando, conforme escopo desta task).
