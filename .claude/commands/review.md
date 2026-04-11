Revisao de compliance com CLAUDE.md para EPI Monitor V2.

Verificar alteracoes recentes contra as regras do projeto.

## Checks

### 1. Identificar arquivos alterados
```bash
git diff --name-only HEAD~1
```

### 2. Regras absolutas (verificar em cada arquivo)
- [ ] AnnotationInterface.jsx NAO foi modificado
- [ ] Zero `CORS(app)` bare — deve ser `CORS(app, origins=config.CORS_ORIGINS)`
- [ ] Zero f-string com input do usuario em SQL
- [ ] Zero `print()` no backend — deve usar `logging.getLogger(__name__)`
- [ ] Zero `any` implicito no TypeScript
- [ ] Bounding boxes: `pointerEvents: 'none'`, zero `onClick`

### 3. Padroes obrigatorios
- [ ] Database: usa DatabasePool, nao conexao avulsa
- [ ] Responses: usa `success()` e `error()` de `app.core.responses`
- [ ] Multi-tenant: queries filtram por `tenant_id`
- [ ] Vite config: `cacheDir: '/tmp/vite-cache-epi'`

### 4. Lint e type-check
```bash
cd backend && python -m ruff check .
cd frontend && npx tsc --noEmit
```

### 5. Testes
```bash
cd backend && python -m pytest tests/ -v --tb=short -q
```

Reportar: lista de violacoes encontradas com arquivo:linha, ou "compliance OK".

$ARGUMENTS
