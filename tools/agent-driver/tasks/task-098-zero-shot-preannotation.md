---
title: "Onboarding: pré-anotação zero-shot (Apache — OWL-ViT/NanoOWL) para bootstrap de dataset"
pr_title: "feat(training): pré-anotação zero-shot no edge para acelerar onboarding de cliente"
commit_message: "feat(training): zero-shot pre-annotation (Apache) para bootstrap de dataset"
eval: default
risk: security
depende_de: ADR-0047
bloco: 8 (Zero-shot onboarding)
---

# Task 098 — Zero-shot pré-anotação

> **Status:** EM REVISÃO — implementado em `agent/task-098-zero-shot-preannotation` (PR para develop;
> STOP-for-review, risk:security). **C-04 investigado:** já existe um padrão de pré-anotação plugável
> flag-OFF (`services/api/app/domain/services/pre_annotation/`, ADR-0031 adendo 2026-07-12) — proxy HTTP
> **síncrono** por-frame pro extinto microserviço DINO+SAM, com `pre_annotation_backend` já previsto como
> segundo campo pra escolher implementação. Zero-shot é uma capability DIFERENTE (roda no **edge**, não
> cloud) que reaproveita as MESMAS duas flags mas NÃO o mesmo transporte — o edge só é alcançável via
> polling (1-5 min), incompatível com o contrato síncrono `predict_and_store()`. **Onde vive:**
> `services/edge-sync-agent/app/zero_shot_detector.py` (interface `ZeroShotDetector`, `Protocol`, mesmo
> padrão de `RecorderClient` das tasks 090/091 — `NotConfiguredZeroShotDetector`/`StubZeroShotDetector`/
> `OwlVitZeroShotDetector`) + `zero_shot_pre_annotation.py` (conversão pro formato `pre_annotations`, gate
> de flag, orquestração de lote sob demanda + CLI). **Licença — VERIFICADA na fonte primária, não
> presumida:** NanoOWL (github.com/NVIDIA-AI-IOT/nanoowl) = Apache-2.0 (metadado de licença do GitHub);
> pesos OWL-ViT (`google/owlvit-base-patch32`) = Apache-2.0 (front-matter do model card + `cardData.license`
> da API do Hugging Face). Ambas checadas na sessão de implementação (2026-07-15) — comandos no PR. Cloud-side:
> `factory.py` documenta que `pre_annotation_backend: "zero_shot"` resolve pra `None` propositalmente (não é
> lacuna) + teste dedicado. 34 testes novos verdes em `services/edge-sync-agent/tests/` (98-100% cobertura
> nos módulos novos) + 1 teste novo em `services/api` confirmando o `None` intencional. **Sem validação em
> hardware real** (Jetson/TensorRT) — mesma limitação de toda a fila 090/091/096; `OwlVitZeroShotDetector`
> nunca é exercitado contra um engine real. **Não integrado:** persistência de fato em
> `training_frames.pre_annotations` (endpoint HTTP aceitando o payload) é trabalho futuro, fora do escopo
> — este lote produz o JSON no formato certo, não escreve no banco cloud. Ver ADR-0047 (adendo 2026-07-15)
> para a análise completa.

## Objetivo
Acelerar o onboarding de cliente novo: zero-shot pré-rotula frames → humano revisa → treina modelo custom.

## Escopo
- Integrar zero-shot Apache (ex. OWL-ViT/NanoOWL — **validar licença** antes) rodando no Jetson.
- Saída = pré-labels no formato de anotação (task-085); flag OFF por padrão (plugável, como ADR-0031/0047).
- É onboarding/pré-anotação, **não** serving de produção.

## Aceite
- [x] Zero-shot gera pré-labels revisáveis para um cliente novo (contrato/formato — sem hardware pra rodar
      inferência real nesta sessão); licença do modelo confirmada Apache (fonte primária, ver Status);
      flag plugável (`pre_annotation_enabled` + `pre_annotation_backend: "zero_shot"`, reaproveitada de
      ADR-0031/0047, OFF por padrão).

## Checkpoint
- STOP-for-review.
