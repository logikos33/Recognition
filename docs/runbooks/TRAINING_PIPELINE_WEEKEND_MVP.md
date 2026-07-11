# Runbook — Pipeline de Treinamento MVP (validar treinando um modelo básico no fim de semana)

**Data:** 2026-07-10 · **Meta:** provar a pipeline end-to-end treinando um modelo EPI básico, com
licenças 100% comerciais (sem AGPL). · **Relaciona:** ADR-0031 (Training Studio), task-054 (pipeline
E2E), TRAINING_PIPELINE_DESIGN.md.

## Stack recomendada (tudo Apache 2.0 / permissivo — comercial OK)

| Peça | Escolha | Licença | Por quê |
|---|---|---|---|
| Detector (weekend) | **RF-DETR** (Nano/Small) | **Apache 2.0** (core Nano-Large + código) | API mais simples pra validar: `model.train()` + `model.export(format="onnx")`; notebook Colab pronto; SOTA. |
| Detector (edge/prod, benchmark depois) | **YOLOX-s** (Megvii) | **Apache 2.0** | Mais maduro em TensorRT/Jetson (edge). Benchmarkar contra RF-DETR na fase de produção. |
| Dataset (bootstrap) | Roboflow Universe: "Construction Site Safety" ou "HardHat & SafetyVest" | **CC BY 4.0** (atribuição) / Public Domain | Rotulados, classes EPI (Hardhat/NO-Hardhat/Vest/NO-Vest/Person…), COCO export. Comercial OK com atribuição. |
| Compute | **Vast.ai** RTX 4090 | serviço | ~$0.29-0.59/hr on-demand (~$0.14 interruptible). Docker+SSH+CLI, template PyTorch. Modelo básico = poucos dólares. |
| Export/inferência | **onnxruntime** | MIT | Roda o ONNX (edge depois via TensorRT). |
| Storage/registry | **Cloudflare R2** (já temos) | serviço | ONNX+pesos por tenant/modelo + linhagem na tabela `models`. |
| (Opcional) pré-anotação | GroundingDINO + SAM + supervision | Apache/MIT | Auto-caixas pra acelerar rotulagem — não precisa no weekend (dataset já vem rotulado). |

**Proibido no caminho servido:** `ultralytics`/YOLOv8/YOLO11 (**AGPL** — bloqueia fechar o código).

## Conectores / o que precisamos ter

- **Vast.ai:** conta + `VAST_API_KEY`.
- **R2:** `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `R2_BUCKET` (já temos).
- **Roboflow:** conta grátis pra exportar o dataset em COCO (ou baixar direto do Universe).
- Scripts: `train_rfdetr.py`, `export_onnx.py`, `register_model.py` (upload R2 + insert `models`).

## Passo a passo do fim de semana (MVP manual — provar que funciona)

1. **Dataset:** baixar um dataset EPI permissivo (COCO) do Roboflow Universe → subir no R2 (ou direto na
   instância). Estrutura COCO: `train/valid/test`, cada um com `_annotations.coco.json` + imagens.
2. **Compute:** subir instância Vast.ai RTX 4090 (template PyTorch), SSH.
3. **Treinar:** `pip install rfdetr` → `model.train(dataset_dir=..., epochs=N)` (fine-tune RF-DETR-N nas
   classes EPI). Poucas épocas já valida.
4. **Exportar:** `pip install "rfdetr[onnx]"` → `model.export(format="onnx")` → um `.onnx`.
5. **Validar:** conferir mAP no val + rodar onnxruntime numa imagem de teste (ver detecções).
6. **Registrar:** subir ONNX+pesos no R2 (prefixo por tenant/modelo) + inserir na tabela `models` com
   métricas e **linhagem** (dataset → treino → modelo).
7. **(Bônus) Inferência:** apontar uma câmera/inferência no ONNX e ver detecção ao vivo.

**Aceite do weekend:** um modelo EPI treinado, exportado em ONNX, no R2 + registrado na `models`, com mAP
razoável no dataset pequeno. Isso prova a pipeline license-safe de ponta a ponta.

## Depois do weekend (automatizar — não é meta agora)

- Substituir o `_dispatch_vast_ai` (hoje **simulação** em `training.py`) por provisionamento Vast.ai real
  (task-054).
- ONNX detector factory (task-055b) pra a inferência servir o ONNX (não ultralytics).
- Versionamento de dataset + registry + active-learning + campeão×desafiante (ADR-0031).

## Fontes
- RF-DETR (Apache, train/export ONNX): github.com/roboflow/rf-detr · rfdetr.roboflow.com
- YOLOX (Apache): github.com/Megvii-BaseDetection/YOLOX
- Datasets PPE (CC BY 4.0): universe.roboflow.com (Construction Site Safety, HardHat & SafetyVest)
- Vast.ai (preço/CLI): vast.ai/pricing · vast.ai/developers/cli
