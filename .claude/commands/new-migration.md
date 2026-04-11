Criar nova database migration para EPI Monitor V2.

Input: $ARGUMENTS (descricao da mudanca de schema)

Carregar contexto:
- @CLAUDE.md (automatico)
- @docs/DATABASE.md (schema atual)

## Protocolo (nivel P0-CRITICO — INFRAESTRUTURA)

### 1. PLANEJAR
- Ler docs/DATABASE.md para entender schema atual
- Checar ultima migration:
  ```bash
  ls backend/app/infrastructure/database/migrations/*.sql | sort | tail -1
  ```
- Definir EXATAMENTE: quais tabelas, colunas, tipos, constraints
- Listar TODOS os arquivos impactados (model, repository, service, route, types)

### 2. CRIAR migration
- Arquivo: `backend/app/infrastructure/database/migrations/NNN_descricao.sql`
- APENAS permitido:
  - `CREATE TABLE IF NOT EXISTS`
  - `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
  - `CREATE INDEX IF NOT EXISTS`
- NUNCA permitido: `DROP`, `ALTER COLUMN TYPE`, `DELETE FROM`, `TRUNCATE`
- Toda nova tabela DEVE ter: `tenant_id UUID REFERENCES tenants(id)`
- Testar idempotencia: arquivo deve rodar 2x sem erro

### 3. PROPAGAR (checklist obrigatoria)
- [ ] Model/dataclass atualizado em `backend/app/domain/models/`
- [ ] Repository atualizado em `backend/app/infrastructure/database/repositories/`
- [ ] Service atualizado em `backend/app/domain/services/`
- [ ] Route/handler atualizado em `backend/app/api/v1/`
- [ ] Types frontend atualizados (se exposto na API)
- [ ] Testes atualizados para novos campos
- [ ] `docs/DATABASE.md` atualizado

### 4. VALIDAR
- `cd backend && python -m pytest tests/ -v --tb=short`
- `cd backend && python -m ruff check .`
- App factory: `cd backend && python -c "from app import create_app; print('OK')"`

### NUNCA
- Criar migration e nao executar
- Alterar migration ja executada (criar nova para corrigir)
- Criar campo no banco sem refletir em model+repository+service
- Migration + mudanca de logica no mesmo commit
