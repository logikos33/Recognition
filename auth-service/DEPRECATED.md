# DEPRECATED — auth-service

Este serviço é um **scaffold mínimo** (302 linhas) que duplica funcionalidade já implementada no backend principal (`api-v3`).

**Status:** Provisionado no Railway mas inativo.

**Funcionalidade assumida por:**
- Autenticação JWT → `backend/app/api/v1/auth/routes.py`
- Hash de senha → `backend/app/core/auth.py` (bcrypt)
- Gerenciamento de usuários → `backend/app/domain/services/auth_service.py`

**Ação necessária:** Manter provisionado no Railway até migração on-premise completa. NÃO deletar arquivos. NÃO desligar o serviço Railway sem alinhamento com a equipe.

**Fase de remoção:** Após go-live RVB e validação do backend principal em produção.
