# inference-service — Análise de Viabilidade de Migração

**Data:** 2026-05-27
**Contexto:** Fase 3 do EDGE_DEPLOYMENT_PLAN prevê mover as 6 tasks EDGE do
cloud Celery para um `services/inference/` no Mini PC com GPU. Este documento
analisa o quanto do `inference-service/` da branch `painel-adm` é reaproveitável.

---

## 1. Arquitetura Atual

O `inference-service` (tag `archive/microservices-attempt-1`) é um consumidor
Redis Pub/Sub:

```
Redis canal frame:{camera_id}
    → inference_engine.py (YOLO + DeepSORT)
    → Redis canal det:{camera_id}
    → ws-gateway (broadcast para clientes)
```

**Arquivos principais:**

| Arquivo | LOC | Função |
|---------|-----|--------|
| `inference_engine.py` | ~180 | Core: Ultralytics YOLO + DeepSORT tracking |
| `frame_consumer.py` | ~120 | Loop Redis Pub/Sub, decode frame, chama engine |
| `model_watcher.py` | ~80 | Monitora S3/MinIO para modelos novos, hot-reload |
| `health_reporter.py` | ~60 | Publica métricas de saúde (FPS, latência, erros) |
| `redis_client.py` | ~50 | Wrapper Redis com retry e connection pooling |
| `config.py` | ~40 | Variáveis de ambiente, validação de config |
| `main.py` | ~30 | Entrypoint, inicialização, shutdown gracioso |
| **Total** | **~572** | |

**Dependências:**
```
ultralytics>=8.0
deep-sort-realtime>=1.3.0
opencv-python-headless>=4.8
redis>=5.0
boto3>=1.28          # acesso a modelos no S3/MinIO
torch>=2.0           # backend PyTorch para YOLO
```

---

## 2. Análise de Portabilidade

### 2.1 Código 100% agnóstico de engine (35% do total)

Esses módulos não dependem do Ultralytics e funcionam com qualquer engine:

| Módulo | Reaproveitamento | Observações |
|--------|-----------------|-------------|
| `frame_consumer.py` | **90%** | Padrão Redis Pub/Sub é idêntico com DeepStream; só muda o callback de inferência |
| `health_reporter.py` | **95%** | Métricas de FPS/latência independem de engine |
| `redis_client.py` | **100%** | Wrapper puro Redis |
| `config.py` | **80%** | Maioria das vars de ambiente é igual; DeepStream adiciona `PIPELINE_CONFIG_PATH` |
| `main.py` | **85%** | Inicialização e shutdown gracioso são iguais |

### 2.2 Código Ultralytics-específico (65% do total)

`inference_engine.py` (~180L) é o núcleo específico:

```python
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

class InferenceEngine:
    def __init__(self, model_path: str):
        self.model = YOLO(model_path)          # Ultralytics-specific
        self.tracker = DeepSort(max_age=30)    # DeepSORT-specific
    
    def process_frame(self, frame: np.ndarray) -> list[Detection]:
        results = self.model(frame, conf=0.5)  # Ultralytics API
        # ... parse results, run tracker
        return detections
```

Com DeepStream, esse módulo seria substituído por um GStreamer pipeline com
`nvinfer` + `nvtracker` — implementação completamente diferente.

`model_watcher.py` (~80L) também é parcialmente específico: monitora `.pt`
(formato PyTorch/Ultralytics). Com DeepStream, monitoraria `.engine` (TensorRT).

### 2.3 Estimativa consolidada

| Cenário de destino | Reaproveitamento estimado |
|-------------------|--------------------------|
| **Manter Ultralytics** (GPU via CUDA, sem DeepStream) | **85–90%** do código |
| **Migrar para DeepStream** (pipeline GStreamer nativo) | **55–60%** do código |

---

## 3. Caminho de Migração Recomendado

### Opção A — Ultralytics + CUDA (caminho mais rápido)

Usar o `inference-service` da tag como base quase direta:
- `inference_engine.py` funciona sem modificação se GPU tem driver CUDA
- Adicionar suporte ao modelo DeepStream é opcional
- Tempo estimado: **1–2 sprints** para adaptar ao monorepo + multi-tenancy

**Prós:** Reaproveita 85–90% do código; equipe já conhece Ultralytics
**Contras:** Ultralytics não é otimizado para DeepStream; throughput menor que TensorRT nativo

### Opção B — DeepStream nativo (caminho de maior performance)

Reescrever `inference_engine.py` como pipeline GStreamer:
- `frame_consumer.py`, `health_reporter.py`, `redis_client.py` reaproveitados
- `model_watcher.py` adaptado para `.engine` em vez de `.pt`
- Tempo estimado: **3–4 sprints** (curva de aprendizado DeepStream)

**Prós:** Throughput máximo com RTX 5060 Ti; TensorRT FP16 reduce latência ~3×
**Contras:** Complexidade GStreamer; debugging mais difícil

### Opção C — Ultralytics agora, DeepStream depois (recomendada)

1. Fase 3: Ultralytics + CUDA (Opção A) — serviço funcionando rápido
2. Pós-RVB-go-live: Migrar `inference_engine.py` para DeepStream sem tocar nos outros módulos

**A interface Redis Pub/Sub (`frame:{camera_id}` → `det:{camera_id}`) permanece
idêntica em ambas as opções** — os consumidores (ws-gateway, dashboard) não precisam
mudar quando a engine muda.

---

## 4. Principais Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Driver CUDA incompatível com RTX 5060 Ti | Média | Alto | Verificar versão CUDA mínima antes de comprar hardware |
| DeepSORT com múltiplas câmeras em memória compartilhada | Baixa | Médio | Instanciar tracker por câmera (já é o padrão atual) |
| `model_watcher.py` com hot-reload durante inferência | Baixa | Alto | Lock de leitura já implementado no código original |
| Latência Redis localhost vs. cloud | Baixa | Baixo | Redis local no Mini PC tem latência <1ms |

---

## 5. Conclusão

O `inference-service` da branch `painel-adm` é **altamente reaproveitável**.
A arquitetura Redis Pub/Sub, o loop de consumo, o health reporter e o redis
client são agnósticos de engine e podem ser portados diretamente.

**Recomendação:** Opção C — Ultralytics na Fase 3, DeepStream pós-go-live.
O `inference_engine.py` é o único módulo que muda entre as duas engines;
a interface externa (Redis canais) permanece estável.

---

## Referências

- `archive/microservices-attempt-1:inference-service/` — código completo
- ADR-0014 — estratégia de arquivo dos microsserviços
- ADR-0001 — DeepStream vs Ultralytics (decisão de engine)
- `docs/decisions/painel-adm-code-value-assessment.md` — avaliação dos outros serviços
