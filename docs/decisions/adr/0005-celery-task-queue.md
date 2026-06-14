# ADR 0005 — Celery como Fila de Tarefas em Background

## Status

Aceito

## Data

2026-05-27

## Contexto

A plataforma precisa executar tarefas pesadas em background, desacopladas do ciclo request/response da API:

- Inferência YOLO em frames extraídos
- Jobs de treinamento de modelos personalizados
- Extração de frames de vídeo
- Análise de qualidade de anotações
- Versionamento de modelos

Três opções foram avaliadas:

- **Threading simples**: fácil de implementar, mas sem controle de concorrência, sem retry, sem monitoramento, sem distribuição entre múltiplos workers.
- **RQ (Redis Queue)**: mais simples que Celery, mas ecossistema menor, sem suporte nativo a schedules periódicos (Celery Beat equivalente é limitado).
- **Celery**: maduro, rico em funcionalidades (retry, rate limiting, routing por fila, Celery Beat para tarefas periódicas), integração nativa com Redis como broker.

O Redis já estava presente na infraestrutura como broker Celery e para pub/sub de detecções.

## Decisão

Usar **Celery com Redis como broker**. Filas separadas por tipo de tarefa permitem priorização e escalonamento independente:

| Fila | Tarefas |
|------|---------|
| `inference` | Inferência YOLO em frames |
| `training` | Jobs de treinamento |
| `extraction` | Extração de frames de vídeo |
| `quality` | Análise de qualidade de anotações |
| `versioning` | Versionamento e exportação de modelos |

**Celery Beat** integrado no serviço `worker` substitui o `scheduler-service` deprecado, centralizando tarefas periódicas (health checks, limpeza de streams mortos, relatórios).

## Consequências

- Worker é um serviço Railway dedicado (`SERVICE_TYPE=worker`) com requirements pesados (`requirements/worker.txt` inclui torch + ultralytics).
- API não instala dependências de ML (`requirements/api.txt` sem torch), mantendo o build leve.
- Routing por fila permite escalonar workers especializados (ex.: instância GPU apenas para fila `inference`).
- Monitoramento via Flower (opcional) ou logs estruturados do Celery.
- Celery Beat no worker garante que tarefas periódicas rodem mesmo sem o scheduler-service.
- Redis como broker e result backend: resultado de tarefas expiram após TTL configurável (padrão 24h).
