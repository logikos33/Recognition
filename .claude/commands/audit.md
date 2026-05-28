Auditoria rapida do projeto EPI Monitor V2.

Executar os seguintes checks e reportar resultado estruturado:

1. **Testes backend**:
   ```bash
   cd backend && python -m pytest tests/ -v --tb=short -q
   ```

2. **Lint backend**:
   ```bash
   cd backend && python -m ruff check .
   ```

3. **TypeScript check**:
   ```bash
   cd frontend && npx tsc --noEmit
   ```

4. **Dead imports** (devem retornar zero):
   ```bash
   grep -r "from services.shared" . --include="*.py" -l
   ```

5. **Migrations count**:
   ```bash
   ls backend/app/infrastructure/database/migrations/*.sql | wc -l
   ```

6. **App factory**:
   ```bash
   cd backend && python -c "from app import create_app; print('OK')"
   ```

Reportar:
- Total de testes / passando / falhando
- Erros de lint (count)
- Erros TypeScript (count)
- Dead imports encontrados
- Numero de migrations
- App factory status

$ARGUMENTS
