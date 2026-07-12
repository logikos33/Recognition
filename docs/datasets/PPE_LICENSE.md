# Licenças de dataset — bootstrap de EPI (PPE)

**Relaciona:** `docs/runbooks/TRAINING_PIPELINE_WEEKEND_MVP.md` (fonte original desta escolha),
ADR-0031 (Training Studio), ADR-0037 (contrato de API — WS-C1 avaliação campeão×desafiante).

## Escopo deste documento

Cobre **apenas o dataset de bootstrap** usado para provar a pipeline de treino ponta-a-ponta antes de
um tenant ter dados próprios rotulados suficientes. **Não se aplica** a dados de um tenant real —
imagens capturadas das câmeras do cliente, upload manual ou mineração de NVR/DVR são dados do próprio
cliente, sem questão de licença de terceiro envolvida.

## Dataset de bootstrap escolhido

**Roboflow Universe** — "Construction Site Safety" ou "HardHat & SafetyVest" (dataset rotulado,
classes de EPI: Hardhat/NO-Hardhat/Vest/NO-Vest/Person, entre outras conforme o dataset específico
escolhido; export em formato COCO).

- **Licença:** CC BY 4.0 (Creative Commons Attribution 4.0) — uso comercial permitido **com
  atribuição** ao criador original do dataset no Roboflow Universe.
- **Por que serve para bootstrap comercial:** CC BY 4.0 não exige compartilhar derivados sob a mesma
  licença (diferente de CC BY-SA) nem restringe uso comercial — só exige creditar a fonte.
- **Acesso:** requer conta Roboflow (gratuita) para exportar via API/COCO; `curl` direto ao Universe é
  bloqueado por Cloudflare (scraping). Exportar manualmente ou via `roboflow` SDK com API key.

## Texto de atribuição (usar ao publicar/documentar um modelo treinado com este bootstrap)

```
Dataset de bootstrap: "Construction Site Safety" / "HardHat & SafetyVest", via Roboflow Universe
(universe.roboflow.com), licenciado sob CC BY 4.0. Consulte a página do dataset no Universe para o
crédito específico do autor/workspace de origem.
```

## Stack de treino associada (license-safe, sem AGPL no serving path)

| Peça | Escolha | Licença |
|---|---|---|
| Modelo | RF-DETR-Nano (github.com/roboflow/rf-detr) | Apache 2.0 |
| Export/serving | ONNX + onnxruntime | MIT/BSD-style |
| Pré-anotação (opcional, flag OFF por padrão) | GroundingDINO + SAM + supervision | Apache/MIT |

Ver `scripts/check_license_gate.py` / `scripts/check_licenses.py` — gate de CI que bloqueia
dependências AGPL/GPL no path de serving (o backend `ultralytics` legado, quando usado, é logado com
warning explícito de que está fora da política pós-migração — task-055c).

## Dados reais de tenant (fora do escopo de licença)

Qualquer avaliação campeão×desafiante (WS-C1, ADR-0037) ou dataset de produção usa o holdout
(`test`/`val`) da própria `dataset_version` do tenant — construída a partir de frames capturados das
câmeras dele (auto-captura, upload, NVR/DVR) ou anotados na plataforma. Esse fluxo normal **não usa o
dataset de bootstrap listado aqui** e não tem questão de licença de terceiro — é dado do próprio
cliente.
