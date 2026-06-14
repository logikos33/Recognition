# ADR-0015: Multi-backend inference — DeepStream + Ultralytics no mesmo serviço

## Status
Aceito

## Data
2026-05-27

## Contexto

ADR-0001 decidiu **DeepStream** como engine de inferência para edge deployment.
A análise de viabilidade (`docs/decisions/inference-migration-feasibility.md`)
revelou que DeepStream requer GPU com driver CUDA no ambiente de desenvolvimento,
tornando o desenvolvimento e o test harness mais difíceis sem hardware dedicado.

A opção "simples" seria começar com Ultralytics na Fase 3 e migrar para DeepStream
depois. Mas isso:
1. Contradiz ADR-0001
2. Cria débito técnico de migração pós-go-live
3. Exige manutenção de dois ciclos de upgrade de engine

### Tensão a resolver

| Necessidade | Requer |
|-------------|--------|
| Produção edge (RVB, RTX 5060 Ti) | DeepStream — throughput máximo, TensorRT FP16 |
| Desenvolvimento local (sem GPU) | Ultralytics em CPU — sem DeepStream |
| CI/CD (GitHub Actions, sem GPU) | Ultralytics em CPU — test harness viável |
| Fallback de go-live | Ultralytics como backup se DeepStream falhar |

## Decisão

**`services/inference/` implementa dois backends desde a Fase 3, selecionáveis
por env var `INFERENCE_ENGINE`.**

### Estrutura

```
services/inference/
├── backends/
│   ├── base.py              # InferenceBackend ABC
│   ├── deepstream/          # Pipeline GStreamer + nvinfer + nvtracker
│   │   ├── pipeline.py
│   │   ├── config/          # deepstream_config.txt, tracker_config.yml
│   │   └── ...
│   └── ultralytics/         # YOLO + DeepSORT (Ultralytics)
│       ├── engine.py
│       └── ...
├── consumer.py              # Redis Pub/Sub — agnóstico de backend
├── health_reporter.py       # Métricas — agnóstico de backend
├── config.py                # INFERENCE_ENGINE=deepstream|ultralytics
└── main.py                  # Seleciona backend em runtime
```

### Interface comum

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Detection:
    track_id: int
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2

class InferenceBackend(ABC):
    @abstractmethod
    def load_model(self, model_path: str) -> None: ...

    @abstractmethod
    def process_frame(self, frame: bytes) -> list[Detection]: ...

    @abstractmethod
    def health(self) -> dict: ...
```

### Seleção em runtime

```python
# config.py
INFERENCE_ENGINE = os.environ.get("INFERENCE_ENGINE", "ultralytics")

# main.py
if INFERENCE_ENGINE == "deepstream":
    from backends.deepstream.pipeline import DeepStreamBackend as Backend
elif INFERENCE_ENGINE == "ultralytics":
    from backends.ultralytics.engine import UltralyticsBackend as Backend
else:
    raise ValueError(f"Unknown INFERENCE_ENGINE: {INFERENCE_ENGINE}")
```

### Interface Redis permanece idêntica

Independente do backend, o serviço consome `frame:{camera_id}` e publica
em `det:{camera_id}` com o mesmo schema JSON. Mudança de backend é
**transparente para consumidores** (ws-gateway, dashboard).

### Variáveis de ambiente por ambiente

```bash
# Edge production (RVB Mini PC com RTX 5060 Ti)
INFERENCE_ENGINE=deepstream

# Desenvolvimento local (sem GPU)
INFERENCE_ENGINE=ultralytics

# CI/GitHub Actions
INFERENCE_ENGINE=ultralytics

# Staging Railway (sem GPU)
INFERENCE_ENGINE=ultralytics
```

## Alternativas Consideradas

### A: DeepStream apenas (ADR-0001 puro)
- Descartada: impossibilita desenvolvimento sem GPU; CI sem GPU quebra
- Mantém ADR-0001 mas aumenta risco de Fase 3 (nenhum teste antes do hardware)

### B: Ultralytics primeiro, DeepStream depois (recomendação original de inference-migration-feasibility.md)
- Descartada: cria débito técnico de migração; contradiz ADR-0001; exige
  segunda reescrita do `inference_engine.py` pós-go-live

### C: Multi-backend desde Fase 3 **(ESCOLHIDA)**
- Prós:
  - ADR-0001 continua válido (DeepStream é o backend de produção)
  - Desenvolvimento sem GPU via Ultralytics
  - Test harness completo sem GPU (CI verde desde o início)
  - Fallback de produção se DeepStream der problema no go-live
- Contras:
  - Dois backends para manter e evoluir
  - Mais código na Fase 3 (~20% overhead)
  - Risco de backends divergirem em comportamento de detecção

### D: Mock/stub backend para CI
- Descartada: mock não valida lógica real de detecção; multi-backend real
  é mais valioso que mock

## Consequências

### Positivas
- Desenvolvimento local possível sem GPU desde o primeiro dia da Fase 3
- CI/GitHub Actions roda testes de inferência em CPU
- Fallback de produção disponível sem código adicional
- ADR-0001 mantido: DeepStream é o caminho de produção

### Negativas
- Dois backends para manter e evoluir em paralelo
- Possível divergência de comportamento entre backends (mitigação: testes
  de contrato no CI verificam que ambos produzem o mesmo schema de evento)
- Overhead de ~20% na Fase 3

### Neutras
- Ultralytics em CPU é mais lento mas funcionalmente equivalente para
  testes de lógica (tracking, schema, pub/sub)
- DeepStream em GPU permanece como único backend de produção medido

## Implementação

### Fase 3

1. Implementar `InferenceBackend` ABC e `UltralyticsBackend` primeiro
2. CI verde com backend Ultralytics
3. Implementar `DeepStreamBackend` em paralelo quando hardware disponível
4. Teste de contrato: mesmo frame → mesmo schema de evento em ambos backends
5. Deploy edge: `INFERENCE_ENGINE=deepstream`

### Pós-go-live

Avaliar se manter ambos os backends ou deprecar Ultralytics após estabilização
do DeepStream em produção.

## Referências

- ADR-0001 — DeepStream vs Ultralytics (decisão original de engine)
- `docs/decisions/inference-migration-feasibility.md` — análise de viabilidade
- OQ-007 em `docs/decisions/oq-responses.md` — questão que gerou este ADR
