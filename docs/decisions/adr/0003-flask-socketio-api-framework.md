# ADR 0003 — Flask + Flask-SocketIO como Framework da API

## Status

Aceito (herdado)

## Data

2026-05-27

## Contexto

A camada de API precisa servir endpoints REST e manter conexões WebSocket persistentes para broadcast de detecções em tempo real. Duas opções foram consideradas:

- **Flask + Flask-SocketIO**: codebase existente, equipe familiarizada, sem necessidade de reescrita. Requer eventlet ou gevent como worker WSGI para suporte a WebSocket em produção.
- **FastAPI**: framework moderno com async nativo (ASGI), geração automática de documentação OpenAPI, melhor suporte a type hints. Exigiria migração completa do codebase existente.

A base de código atual possui mais de 500 linhas de rotas em Flask, blueprints por domínio, middleware de autenticação JWT e integração Flask-SocketIO já funcional. Uma migração para FastAPI representaria risco de regressão e esforço estimado em várias sprints sem benefício funcional imediato para o cliente.

## Decisão

**Manter Flask + Flask-SocketIO**. A migração para FastAPI fica adiada para pós-v1, quando houver estabilidade de produto e cobertura de testes suficiente para suportar uma reescrita de framework sem risco.

Gunicorn com worker eventlet é usado em produção Railway (`gunicorn -k eventlet`). Documentação OpenAPI é mantida manualmente em `docs/api/`.

## Consequências

- Sem custo de migração imediato; equipe permanece produtiva no stack conhecido.
- Eventlet/gevent obrigatório para WebSocket: gunicorn eventlet worker em produção, incompatível com threading padrão.
- Documentação de API manual: sem geração automática de schema OpenAPI. Risco de documentação desatualizada.
- Migração futura para FastAPI (ou outro ASGI framework) deve ser tratada como projeto separado com suite de testes de contrato como pré-requisito.
- Gunicorn v26 remove suporte a eventlet (débito técnico registrado): migração para gevent ou threading worker necessária antes do upgrade do gunicorn.
