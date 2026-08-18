# D-107 · Quatro caminhos de treino que mentiam — deletados, não desligados

**Seção:** Rodada RunPod 10/08 (PR #343 — renumerada de D-85..D-88 → D-106..D-109) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**10/08 · Claude (auditoria + execução) · ✅ PR #340**

Os quatro: `_simulate_training` (dormia e inventava mAP), `_dispatch_vast_ai_legacy` +
`provision_and_train.sh` (treinava no Roboflow público e apresentava como do tenant),
`_dispatch_hub` (**nunca enviou o dataset do tenant ao Ultralytics Hub** — o `datasetId` era um
UUID interno que o Hub nunca viu) e `POST /dashboard/training-metrics` (**qualquer usuário
autenticado fabricava métricas** para qualquer `model_name` — este ganhou role + validação de
modelo real, é a via do seed legítimo). Saldo: **−5.127 linhas**. **Regra que fica (ADR-0061):
⛔ nunca `completed` sem artefato verificado no R2** — `verify_model_artifact` roda nos 3 pontos
que persistem sucesso; artefato ausente → `failed` com motivo. Achado lateral: **o retreino do
módulo Qualidade nunca funcionou** — `ImportError` (`run_quality_training` não existe) mascarado
por `except` genérico; corrigido. License-gate estendido a `training/` e `scripts/`; pesos
travados **por sha256** em `docs/WEIGHTS_LICENSES.md` (o caso DINOv2 — Apache e FAIR
Noncommercial no MESMO repo — é o motivo).
