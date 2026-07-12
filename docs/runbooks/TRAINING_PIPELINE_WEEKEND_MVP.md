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

## Verificação pós-deploy das migrations (093–101)

**Por que verificar manualmente:** o runner de produção (`railway_start.py`, função
`run_migrations`, linhas ~80–84) **NÃO aborta em erro real** — se um statement falha com erro que
não contém `already exists`/`duplicate`, ele loga `❌` e **continua para o próximo arquivo**
(crítica arquitetural D-1 / ajuste #13). Uma 094 falhada seria pulada silenciosamente e a 095
(que depende dela) falharia em cascata, deixando o banco inconsistente com `✅ Migrations OK` no
final do log. Até o runner ganhar abort-on-error, **esta verificação manual é o guard-rail**.

Rode após todo deploy que inclua as migrations 093–101 (`psql $DATABASE_URL`). Cada query deve
retornar as linhas indicadas — retorno vazio/menor = migration não aplicou por inteiro (procurar
`❌` no log de deploy do serviço api-v3).

```sql
-- 093: yolo_classes ganhou tenant_id + module_code (espera 2 linhas)
SELECT column_name FROM information_schema.columns
 WHERE table_schema='public' AND table_name='yolo_classes'
   AND column_name IN ('tenant_id','module_code');

-- 094: training_frames multi-fonte (espera 8 linhas) + CHECK de source (espera 1 linha)
SELECT column_name FROM information_schema.columns
 WHERE table_schema='public' AND table_name='training_frames'
   AND column_name IN ('source','r2_key','camera_id','recorder_id',
                       'width','height','model_confidence','captured_at');
SELECT conname FROM pg_constraint
 WHERE conname='chk_training_frames_source';

-- 095: frame_annotations com proveniência (espera 3 linhas)
SELECT column_name FROM information_schema.columns
 WHERE table_schema='public' AND table_name='frame_annotations'
   AND column_name IN ('source','created_by','reviewed_by');

-- 096: tabela datasets (espera 1 linha) + dataset_versions estendida (espera 8 linhas)
SELECT table_name FROM information_schema.tables
 WHERE table_schema='public' AND table_name='datasets';
SELECT column_name FROM information_schema.columns
 WHERE table_schema='public' AND table_name='dataset_versions'
   AND column_name IN ('dataset_id','tenant_id','module_code','split',
                       'augmentations','coco_r2_key','export_format','status');

-- 097: training_jobs com campos do pipeline (espera 7 linhas)
SELECT column_name FROM information_schema.columns
 WHERE table_schema='public' AND table_name='training_jobs'
   AND column_name IN ('dataset_version_id','framework','base_model','hyperparams',
                       'gpu_provider','gpu_instance_ref','callback_token');

-- 098: trained_models com linhagem do registry (espera 6 linhas)
SELECT column_name FROM information_schema.columns
 WHERE table_schema='public' AND table_name='trained_models'
   AND column_name IN ('framework','r2_onnx_key','r2_weights_key',
                       'metrics','dataset_version_id','module_code');

-- 099: tabela recorders (espera 1 linha) + CHECK de protocol e FK de
--      training_frames.recorder_id (espera 2 linhas)
SELECT table_name FROM information_schema.tables
 WHERE table_schema='public' AND table_name='recorders';
SELECT conname FROM pg_constraint
 WHERE conname IN ('chk_recorders_protocol','fk_training_frames_recorder');

-- 100: tabela model_deployments (espera 1 linha)
SELECT table_name FROM information_schema.tables
 WHERE table_schema='public' AND table_name='model_deployments';

-- 101: model_evaluations + model_drift_metrics (espera 2 linhas)
SELECT table_name FROM information_schema.tables
 WHERE table_schema='public'
   AND table_name IN ('model_evaluations','model_drift_metrics');

-- Multi-tenant (C-01): as 5 tabelas novas têm tenant_id UUID NOT NULL (espera 5 linhas, todas NO)
SELECT table_name, is_nullable FROM information_schema.columns
 WHERE table_schema='public' AND column_name='tenant_id'
   AND table_name IN ('datasets','recorders','model_deployments',
                      'model_evaluations','model_drift_metrics');
```

Os mesmos asserts rodam automatizados no harness D1
(`tests/harness/migrations/test_migrations_harness.py`) contra Postgres efêmero — mas o harness
não valida o banco de produção; daí a checklist acima.

**Follow-up formal (D-1):** adicionar flag abort-on-error ao `run_migrations()` de
`railway_start.py` (ex.: `MIGRATIONS_STRICT=1` → primeira falha real encerra o boot com exit != 0,
mantendo a tolerância a `already exists`/`duplicate`). É mudança de comportamento de boot em todos
os ambientes — fazer em PR próprio, separado de qualquer migration, com teste do runner. Enquanto
não existir, a seção acima é obrigatória em todo deploy com migration nova.

## Fontes
- RF-DETR (Apache, train/export ONNX): github.com/roboflow/rf-detr · rfdetr.roboflow.com
- YOLOX (Apache): github.com/Megvii-BaseDetection/YOLOX
- Datasets PPE (CC BY 4.0): universe.roboflow.com (Construction Site Safety, HardHat & SafetyVest)
- Vast.ai (preço/CLI): vast.ai/pricing · vast.ai/developers/cli
