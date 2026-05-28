# Classificação de Celery Tasks — EDGE | CLOUD | KILL

**Data:** 2026-05-27
**Baseado em:** análise do código em `backend/app/infrastructure/queue/tasks/`

---

## Tabela de Classificação

| Task | Arquivo | Classificação | Justificativa |
|------|---------|--------------|---------------|
| `inference_loop` | inference.py | **EDGE** | Loop RTSP→YOLO em tempo real, publica `det:*` Redis |
| `start_hls_stream` | inference.py | **EDGE** | Processo FFmpeg RTSP→HLS para live view local |
| `quality_inference_loop` | quality_inference.py | **EDGE** | Loop contínuo YOLO para câmeras quality em tempo real |
| `run_quality_gate_inspection` | quality_inference.py | **EDGE** | Inspeção sob demanda com votação de frames múltiplos |
| `record_quality_camera` | quality_recording.py | **EDGE** | Gravação FFmpeg RTSP contínua em segmentos de 5min |
| `capture_reference_snapshot` | quality_clips.py | **EDGE** | Captura 1 frame do stream RTSP em tempo real |
| `extract_frames` | extraction.py | **CLOUD** | Batch: download R2 → FFmpeg FPS → upload paralelo (não real-time) |
| `quality_filter` | quality.py | **CLOUD** | Batch blur/brightness filtering em frames para treinamento |
| `dispatch_training` | training.py | **CLOUD** | Orchestration: pipeline Ultralytics Hub |
| `build_dataset_version` | versioning.py | **CLOUD** | Agrupa frames anotados, split train/val/test |
| `verify_alert` | verification.py | **CLOUD** | Verificação Claude AI em baixa confiança, não real-time |
| `check_auto_retraining` | auto_training.py | **CLOUD** | Celery Beat: monitora crescimento de frames e dispara treino |
| `generate_quality_clip` | quality_clips.py | **CLOUD** | Pós-processamento: recorte ±30s de gravação após NOK |
| `prepare_quality_frames` | quality_annotation.py | **CLOUD** | Extrai frames do clip em batch para anotação |
| `run_quality_training_pipeline` | quality_training.py | **CLOUD** | Pipeline completo de treinamento quality |
| `update_quality_cep_baseline` | quality_cep.py | **CLOUD** | Celery Beat diário: recalcula baseline CEP de NOK rate |
| `cleanup_quality_recordings` | quality_cep.py | **CLOUD** | Celery Beat horário: deleta segmentos >48h do R2 |
| `cleanup_quality_clips` | quality_cep.py | **CLOUD** | Celery Beat diário: deleta clips >7 dias |
| `generate_shift_reports` | quality_cep.py | **CLOUD** | Celery Beat (06:15/14:15/22:15): gera relatórios de turno |
| `retry_failed_wiser_exports` | quality_inference.py | **CLOUD** | Celery Beat: retry de exportações WISER com falha |
| *(nenhuma)* | — | **KILL** | Zero tasks obsoletas identificadas |

## Resumo

| Classificação | Count | Tasks |
|---|---|---|
| **EDGE** | 6 | inference_loop, start_hls_stream, quality_inference_loop, run_quality_gate_inspection, record_quality_camera, capture_reference_snapshot |
| **CLOUD** | 15 | todas as de training, scheduling, maintenance, pós-processamento |
| **KILL** | 0 | nenhuma task morta/obsoleta |

---

## Estratégia de Migração

### Durante Fases 0–5 (BUILD)
As 6 tasks EDGE permanecem rodando no cloud Celery **sem alteração**.
Cliente Quality em produção continua funcionando como hoje.
Novos serviços em `services/inference/` são desenvolvidos em paralelo mas NÃO recebem tráfego.

### Fase 6 (SHADOW)
Edge processa as mesmas câmeras em paralelo com cloud (mínimo 7 dias).
Coluna `origin` em alerts/camera_events/counting_events distingue eventos cloud vs edge.
Dashboard de comparação shadow valida equivalência.

### Fase 6.5 (CUTOVER POR CÂMERA)
Cutover gradual câmera a câmera via coluna `processing_mode` em `ip_cameras`.
Rollback imediato disponível (1 UPDATE).

### Pós-RVB Go-Live (FORA DO PLANO ATUAL)
Apenas após 30 dias de edge estável: desligamento físico das tasks Celery EDGE.

**Referência:** ADR-0013 — docs/decisions/adr/0013-shadow-mode-cutover.md
