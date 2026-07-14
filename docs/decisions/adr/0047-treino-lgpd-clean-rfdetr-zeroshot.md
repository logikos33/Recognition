# ADR-0047 — Pipeline de treino LGPD-clean (anotação self-hosted + RF-DETR) + zero-shot no onboarding

**Status:** Aceito · **Data:** 2026-07-14 · **Autores:** Vitor Emanuel (Logikos)
**Estende:** ADR-0031 (training studio), ADR-0039 (compute providers) · **Relaciona:** ADR-0044, docs/security/LGPD_PRIVACIDADE_CFTV.md

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
