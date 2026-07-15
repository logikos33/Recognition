# ADR-0048 — Anotação self-hosted: ferramenta própria já satisfaz o requisito LGPD (supersede parcial ADR-0047)

**Status:** Aceito · **Data:** 2026-07-15 · **Autores:** Vitor Emanuel (Logikos) — investigação e proposta por sessão Claude Code (task-085)
**Relaciona:** ADR-0047 (supersede parcial — ver Decisão), ADR-0008 (supersede — anotação), ADR-0031 (training studio), ADR-0037 (contrato de API de treino), docs/security/LGPD_PRIVACIDADE_CFTV.md

## Contexto

ADR-0047 decidiu "anotação self-hosted (CVAT ou Label Studio, on-prem)" para que imagem de trabalhador
(dado pessoal, LGPD) não saísse do controle da Logikos/cliente. A task-085 foi aberta para *escolher e
integrar* CVAT ou Label Studio ao versionamento de dataset atual.

Investigação de código (C-04) antes de implementar mostrou que **o requisito já está satisfeito por uma
ferramenta própria**, construída nas Fases 1/2 do training studio, muito antes da ADR-0047:

- `apps/frontend/src/components/AnnotationInterface.jsx` (+ wrapper `pages/AnnotationPage.tsx`) — anotador de
  bounding box → classe, servido dentro da própria infra do Recognition (Railway). Nenhuma chamada de rede
  para SaaS de anotação de terceiro existe nesse caminho.
- `frame_annotations` (`infra/migrations/003_training.sql`, proveniência `source/created_by/reviewed_by` desde
  `095_annotations_provenance.sql`) persiste as anotações; `build_dataset_version_v2`
  (`services/api/app/infrastructure/queue/tasks/versioning_v2.py`), disparado via
  `POST /datasets/<id>/versions`, exporta COCO por split e sobe para R2
  (`{R2Prefix.DATASET_EXPORTS}/{tenant_id}/{dataset_id}/{version}/...`); `DatasetRepository.create_version_v2`
  grava `coco_r2_key`.
- Destino de imagem é sempre Cloudflare R2 (`R2Storage`,
  `https://{account_id}.r2.cloudflarestorage.com`) ou disco local (`LocalStorage`) — nunca um provedor
  terceiro. Grep completo em `services/api/app` e `apps/frontend/src` por `roboflow.com|cvat|label-?studio`
  não encontrou nenhuma integração real, só as menções de planejamento na própria task-085/ADR-0047.
- O único uso real de Roboflow no repo (`training/vast/provision_and_train.sh`, fallback legado de treino
  Vast.ai) **baixa** um dataset público (`roboflow-100/hard-hat-workers`, CC BY 4.0) — não envia imagem de
  cliente para lá, e está fora do caminho anotação→dataset.

`AnnotationInterface.jsx` está marcado CONGELADO (contrato Fase 1/Fase 2, ver `apps/frontend/AGENTS.md` e
`apps/frontend/src/components/AGENTS.md`), mas o freeze é contra refactor/estilo cosmético — não bloqueou
correções funcionais reais (`ecc02e3`, já mergeada; `05d0b9e`, pendente de merge em branch separada). Não há
bug ativo bloqueante no caminho de anotação→dataset, nem lacuna de capability (ex. polígono/segmentação,
QA multi-anotador em escala) documentada em nenhum outro lugar do repo que justifique trocar de ferramenta.

Subir CVAT ou Label Studio como infraestrutura nova (serviço Docker/Railway adicional, armazenamento
persistente, rede, manutenção) tem custo real e não teria contrapartida — o requisito de "dado não sai do
controle da Logikos/cliente" já é cumprido pela ferramenta própria + R2, que é infra da própria Logikos.

## Decisão

- **Supersede parcialmente a ADR-0047**: o ponto "Anotação self-hosted (CVAT ou Label Studio, on-prem)" é
  substituído por "anotação self-hosted = a ferramenta própria (`AnnotationInterface.jsx` +
  `versioning_v2.py` + R2) já em produção, sem necessidade de infra de terceiro". Os demais pontos da
  ADR-0047 (RF-DETR no pipeline de treino — task-086; zero-shot Apache no edge para onboarding — task-098)
  **permanecem válidos e não são afetados**.
- **Supersede a ADR-0008** no ponto "Roboflow para anotação e versionamento de dataset" — essa parte já
  havia sido substituída na prática pela ferramenta própria antes mesmo desta ADR; aqui isso é formalizado.
  A parte de treino da ADR-0008 (Colab) segue como está até ser revisitada por task-086/ADR de treino RF-DETR.
- **Não implementar CVAT/Label Studio.** Nenhuma infraestrutura nova de anotação é adotada nesta decisão.
- Interpretação de "self-hosted"/"on-prem" no contexto deste produto: significa **sob controle direto da
  Logikos** (primeira parte, sem intermediário terceiro/DPA), não necessariamente hardware fisicamente
  on-premises — a mesma leitura já usada pela ADR-0028 (evidência cloud-first em R2, não em disco local do
  cliente).

## Alternativas consideradas

- **Integrar CVAT on-prem** — feature completa (polígono, multi-anotador, QA de fila), mas exige subir e
  manter um serviço novo (banco próprio, storage, autenticação) sem nenhuma lacuna concreta hoje que a
  justifique. Custo de infra/manutenção não compensado.
- **Integrar Label Studio on-prem** — mais leve que CVAT, mesma objeção: nenhuma lacuna concreta hoje.
- **Manter e evoluir a ferramenta própria (escolhida)** — zero infra nova, já cumpre o essencial
  (bbox → classe → COCO versionado → R2, sem terceiro). Se no futuro surgir necessidade real de
  polígono/segmentação ou QA multi-anotador em escala (ex. módulo Qualidade pedir instance segmentation),
  reavaliar nessa ocasião com requisito concreto em mãos — não especular agora.

## Consequências

- Positivas: zero custo de infraestrutura nova; requisito LGPD já satisfeito e agora documentado
  explicitamente; task-085 fecha sem código de infra novo pendente de revisão de custo.
- Negativas / trade-offs: a ferramenta própria não tem polígono/segmentação nem fluxo formal de
  QA multi-anotador (o dado de proveniência `created_by`/`reviewed_by` existe no banco mas não é
  exposto na UI) — aceitável hoje porque nenhum caso de uso ativo do produto exige isso; registrado aqui
  como débito conhecido, não como bloqueio.
- Impacto em: nenhuma migration necessária (dado de proveniência já existe desde 095); nenhum contrato
  FE↔BE alterado; segurança/LGPD — fecha a lacuna documental em
  `docs/security/LGPD_PRIVACIDADE_CFTV.md` (seção 3) confirmando que imagens de anotação/treino não saem
  para terceiro.

## Notas

- Investigação completa (arquivo por arquivo, commit por commit) registrada em
  `tools/agent-driver/tasks/task-085-annotation-self-hosted.md`, seção "Status (2026-07-15)".
- Se no futuro uma necessidade concreta de CVAT/Label Studio surgir, abrir nova ADR com o requisito
  específico — não reabrir esta.
