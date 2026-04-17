# DEPRECATED — scheduler-service

Este serviço é um **scaffold mínimo** (213 linhas) com configuração básica de Celery.

**Status:** Provisionado no Railway mas inativo.

**Funcionalidade assumida por:**
- Agendamento de tarefas → Celery tasks no `backend/app/infrastructure/queue/`
- Filas: extraction, versioning, training, inference
- Config Celery → `backend/app/infrastructure/queue/celery_app.py`

**Ação necessária:** Manter provisionado no Railway até migração on-premise completa. NÃO deletar arquivos. NÃO desligar o serviço Railway sem alinhamento com a equipe.

**Fase de remoção:** Após worker on-premise operacional e validado em produção.
