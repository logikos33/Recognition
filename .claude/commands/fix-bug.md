Workflow de correcao de bug para EPI Monitor V2.

Input: $ARGUMENTS (descricao do bug)

Carregar contexto:
- @CLAUDE.md (automatico)

## Protocolo

### 1. CLASSIFICAR impacto
- P0-CRITICO: Multi-servico, risco de dados
- P1-ALTO: Servico unico, user-facing
- P2-MEDIO: Refactor interno
- P3-BAIXO: Documentacao

### 2. REPRODUZIR
Nao tocar no codigo antes de reproduzir o bug.
- Identificar endpoint/componente afetado
- Reproduzir com curl, teste, ou UI

### 3. TRACE o fluxo end-to-end
- De onde vem o input? (route -> service -> repository -> banco)
- Onde exatamente diverge do esperado?
- Usar grep, git blame, logs — NAO adivinhar

### 4. ISOLAR causa raiz
- Problema de dados, logica, timing, ou schema?
- `git log` para entender quando foi introduzido

### 5. ESCREVER TESTE que reproduz o bug (deve FALHAR)
- Adicionar em `backend/tests/unit/` ou `backend/tests/integration/`

### 6. CORRIGIR com mudanca minima
- Se "conserta aqui, quebra ali" — o problema e mais profundo

### 7. VALIDAR
- Teste do bug passa
- TODOS os testes passam: `cd backend && python -m pytest tests/ -v --tb=short`
- Lint: `cd backend && python -m ruff check .`
- Se frontend: `cd frontend && npx tsc --noEmit`

### CONSTRAINTS
- NUNCA modificar AnnotationInterface.jsx
- NUNCA usar DROP em SQL
- NUNCA usar f-string com input do usuario em SQL
- Zero print() — usar logging.getLogger(__name__)
