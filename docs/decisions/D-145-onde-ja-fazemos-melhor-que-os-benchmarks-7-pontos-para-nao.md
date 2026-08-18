# D-145 · Onde já fazemos MELHOR que os benchmarks — 7 pontos, para não reconstruir o que já é bom

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente

O confronto com o AWS PPE (e o que restou do Frigate) confirmou os dois pontos esperados e revelou mais cinco:

| Fazemos melhor | Onde | O benchmark faz |
|---|---|---|
| Split por vídeo ou câmera+dia | `versioning_v2.py:175-199` `_group_key` | random 20% por imagem → vaza |
| Avaliação campeão×desafiante automática | `model_evaluation.py:181`, disparada por `training.py:311` | 100% manual |
| Meta de dados por classe computada em código | `coverage_service.py:11-38` (100 img, ≥5 câm, ≤50%) | "mínimo 10", sem base |
| Fila humana aprovar/rejeitar/corrigir | `VerificationQueuePage.tsx` + V/X no Estúdio | não tem loop de revisão |
| Artefato verificado antes de "completed" | `training.py:33-37` + `verify_model_artifact` | não trata |
| Limiar de confiança configurável | `ZoneTuningForm.tsx` + `inference/config.py:17` | caixa-preta gerenciada |
| Treino que exporta ONNX real (não preso a SaaS) | `training/vast/remote_train.py` | Custom Labels não exporta |

**A decisão:** estes 7 pontos **não entram em nenhuma proposta de reforma.** Já estão certos.
A reforma da aba mira exclusivamente o que está medido como quebrado (D-137 a D-140, D-143, D-144).
