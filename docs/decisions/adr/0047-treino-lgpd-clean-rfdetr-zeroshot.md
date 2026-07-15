# ADR-0047 — Pipeline de treino LGPD-clean (anotação self-hosted + RF-DETR) + zero-shot no onboarding

**Status:** Aceito. **Parcialmente superseded by ADR-0048** (2026-07-15) no ponto "anotação self-hosted
(CVAT ou Label Studio, on-prem)" — investigação da task-085 confirmou que a ferramenta própria de
anotação já em produção satisfaz o requisito sem infra de terceiro. Os demais pontos desta ADR (RF-DETR
no treino, zero-shot no onboarding) continuam válidos. · **Data:** 2026-07-14 · **Autores:** Vitor Emanuel (Logikos)
**Estende:** ADR-0031 (training studio), ADR-0039 (compute providers) · **Relaciona:** ADR-0044, ADR-0048, docs/security/LGPD_PRIVACIDADE_CFTV.md

## Contexto
RF-DETR é Apache e **open-source** — não exige a nuvem do Roboflow. Imagem de trabalhador é dado pessoal
(LGPD): mandar pra SaaS de terceiro cria exposição e exige DPA. A pré-anotação foi removida (flag OFF); o Jetson
traz zero-shot/VLM que pode ressuscitá-la para bootstrap de dataset.

## Decisão
- **Anotação self-hosted** (CVAT ou Label Studio, on-prem) — dado não sai do controle da Logikos/cliente.
- Treino **RF-DETR** no pipeline atual (Vast.ai/local) → export ONNX → registry. **Roboflow cloud = opcional**,
  atrás de flag, só com DPA + anonimização.
- **Zero-shot (Apache — ex. OWL-ViT/NanoOWL, licença a validar)** no edge para **pré-rotular** frames de cliente
  novo → humano revisa → treina o modelo custom. É onboarding/pré-anotação, **não** serving de produção.

## Consequências
- Integração de anotação self-hosted (task-085) + treino RF-DETR (task-086) + zero-shot onboarding (task-098).
- Sem envio obrigatório de imagem a terceiro → coerente com o RIPD.

## Adendo — Zero-shot onboarding: licença, onde vive o código, decisão de transporte (2026-07-15)

**Licença — verificada, não presumida (task-098):**
- **NanoOWL** (github.com/NVIDIA-AI-IOT/nanoowl) — Apache-2.0, confirmado via metadado de licença do
  repositório no GitHub (`license.spdx_id: "Apache-2.0"`, API pública do GitHub) e via leitura direta
  da página do repositório.
- **OWL-ViT** (pesos `google/owlvit-base-patch32`, os que o NanoOWL otimiza via TensorRT) — Apache-2.0,
  confirmado no front-matter YAML do próprio model card (`license: apache-2.0`) e no campo
  `cardData.license` da API pública do Hugging Face — fonte primária, não terceiro.
- Ambas verificações feitas na sessão de implementação (2026-07-15); ver PR da task-098 para os comandos
  exatos. **Se outro checkpoint/variante for usado no futuro (ex. OWLv2, outro tamanho), reverificar a
  licença daquele artefato específico** — não presumir que herda a licença do `owlvit-base-patch32`.

**Onde o código vive:** `services/edge-sync-agent/app/zero_shot_detector.py` (interface `ZeroShotDetector`,
`typing.Protocol`, mesmo padrão de `recorder_client.py::RecorderClient` das tasks 090/091 — default
`NotConfiguredZeroShotDetector` falha alto, `StubZeroShotDetector` determinístico para teste,
`OwlVitZeroShotDetector` real com import tardio do `nanoowl`) e
`zero_shot_pre_annotation.py` (conversão pro formato `pre_annotations` já consumido por
`annotation_service.get_frame_annotations`, gate de feature flag, orquestração de lote, CLI). Vive no
**edge** (roda no Jetson durante onboarding), não no monolito cloud — é lógica que precisa do hardware do
site, não de um microserviço cloud.

**Por que NÃO foi integrado em `services/api/app/domain/services/pre_annotation/` (o `PreAnnotationBackend`
usado pelo botão "pré-anotar" do AnnotationInterface):** aquela interface é um proxy HTTP **síncrono**
por-frame (`predict_and_store(frame_id, module_code) -> int`, resposta imediata — é assim que
`DinoSamHttpBackend` fala com o `pre-annotation-service`). O edge só é alcançável pelo cloud via
**polling** (`config_poller.py` a cada 5 min, `command_poller.py` a cada 1 min — ver AGENT.md de
`services/edge-sync-agent`), então uma chamada síncrona cloud→edge→cloud dentro de uma única request HTTP
não é viável com a arquitetura de polling que existe hoje. Forçar isso no formato síncrono seria um design
ruim disfarçado de integração completa. A decisão: zero-shot de onboarding é um **lote sob demanda**,
rodado pelo operador (Logikos, "treina o inicial" — ver ADR-0031 "Quem treina: híbrido"), não uma chamada
disparada pela factory cloud. `factory.py` documenta isso explicitmente: `pre_annotation_backend: "zero_shot"`
resolve para `None` propositalmente (comportamento correto, não lacuna) — ver teste
`test_zero_shot_backend_name_intentionally_returns_none`.

**Flag reaproveitada, não duplicada:** os nomes `pre_annotation_enabled` / `pre_annotation_backend` são os
mesmos da ADR-0031 (adendo 2026-07-12). Como não há pacote de lógica compartilhado entre
`services/edge-sync-agent` e `services/api` (só `shared/python/recognition_shared`, DTOs Pydantic, sem
lógica — mesma constatação já registrada na task-091), as constantes são duplicadas por convenção em
`zero_shot_pre_annotation.py`, com comentário cruzado apontando pra `factory.py` como fonte da verdade do
nome. `is_zero_shot_enabled(feature_flags)` exige **ambos** os campos (`pre_annotation_enabled: true` E
`pre_annotation_backend: "zero_shot"`) — sem fallback de env var (diferente da `factory.py` cloud, que cai
pra `PRE_ANNOTATION_ENABLED` do ambiente): o processo do edge não tem noção de "default do tenant atual",
só o que o operador de onboarding passa explicitamente pra aquela rodada.

**Formato de saída:** cada detecção vira `{"bbox": {"cx","cy","w","h"}, "class": <text_label>,
"confidence": <score>}` — o exato formato que `annotation_service.get_frame_annotations` já sabe ler
(AI_NOTE no código: "DINO salva bbox como dict {cx,cy,w,h}", "DINO salva 'class', legado usa 'label'").
Revisão humana acontece na MESMA tela `AnnotationInterface.jsx`, nenhuma UI nova.

**Sem hardware real:** nenhuma parte desta implementação foi exercitada contra um Jetson/TensorRT real —
mesma limitação de toda a fila 090/091/096. `OwlVitZeroShotDetector` faz import tardio do `nanoowl`
(dependência pesada, TensorRT) justamente pra que importar o módulo não exija essas libs instaladas; só
instanciar a classe exige. Validação de inferência real (baixar engine, rodar contra frame real, medir
qualidade das sugestões) fica para o go-live com hardware — mesmo texto de risco já usado nas tasks
anteriores desta fila.

**Não integrado — persistência em `training_frames.pre_annotations`:** este lote produz o payload no
formato certo; escrevê-lo de fato na coluna (um endpoint HTTP aceitando esse payload, ou outro mecanismo)
é trabalho futuro, fora do escopo desta task — evita inventar infra cloud nova (endpoint + migração) sem
necessidade comprovada antes do go-live com hardware.
