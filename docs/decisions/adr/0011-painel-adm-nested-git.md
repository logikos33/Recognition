# ADR-0011: Como tratar painel-adm/ como repositório git aninhado na Fase 0

## Status
Aceito

## Data
2026-05-27

## Contexto

O diretório `painel-adm/` contém um repositório git próprio (`.git/` interno).
O plano Fase 0 propõe `git mv painel-adm/auth-service/ services/auth/` e similares.
`git mv` de diretórios dentro de um repo git aninhado não preserva histórico do repo pai —
o repo pai não rastreia os arquivos internos do sub-repo.

Além disso, `painel-adm/` contém mais do que os 6 microsserviços listados no plano:
- `auth-service/`, `camera-gateway/`, `inference-service/`, `ws-gateway/`, `scheduler-service/`, `training-service/` (listados no plano)
- `backend/` — conteúdo desconhecido (cópia do backend principal?)
- `frontend/` — conteúdo desconhecido (cópia do frontend principal?)
- `migrations/` — conteúdo desconhecido (migrations separadas?)
- `pre-annotation-service/` — serviço DINO+SAM
- `agent/` — desconhecido
- `landing-page/` — cópia do landing?

Estes diretórios extras não foram mapeados no plano original.

## Decisão

**Opção escolhida: Remover o `.git` aninhado de `painel-adm/` antes de qualquer `git mv`.**

Procedimento aprovado:
1. **Pre-4 (investigação):** Comparar `painel-adm/backend/` vs `backend/`, `painel-adm/frontend/` vs `frontend/`, `painel-adm/migrations/` vs `backend/app/infrastructure/database/migrations/`. Documentar destino de cada diretório em `docs/decisions/painel-adm-investigation.md`. Aguardar aprovação de Vitor.
2. Após aprovação: `tar czf /tmp/painel-adm-backup-$(date +%Y%m%d-%H%M%S).tar.gz painel-adm/.git` (backup do histórico interno)
3. `rm -rf painel-adm/.git` (transforma em diretório normal)
4. `git add painel-adm/` (agora rastreado pelo repo pai)
5. `git mv painel-adm/auth-service/ services/auth/` etc.

## Alternativas Consideradas

### A: git submodule
- Prós: preserva histórico do sub-repo formalmente
- Contras: Railway não suporta submodules bem; clone requer `--recurse-submodules`; adiciona fricção operacional pra todo desenvolvedor e CI

### B: Copiar sem histórico (cp + rm + git add)
- Prós: simples
- Contras: perde histórico de commits dos 6 serviços (commits de desenvolvimento, fixes, etc.)

### C: Remover .git aninhado e fazer git mv **(ESCOLHIDA)**
- Prós: histórico do repo pai preservado para os arquivos movidos; `git mv` funciona normalmente; Railway sem mudança
- Contras: perde histórico *interno* de commits do sub-repo (que estava isolado e nunca foi compartilhado no repo pai)

## Consequências

### Positivas
- Fase 0 executa `git mv` normalmente, preservando histórico no repo principal
- Estrutura de monorepo limpa sem dependências externas
- CI/CD Railway sem configuração adicional

### Negativas
- Histórico interno de commits de `painel-adm/.git` é perdido (mitigado pelo backup em `/tmp/`)

### Neutras
- Pre-4 investigation pode revelar código relevante em `painel-adm/backend/` que precisa ser portado

## Implementação

```bash
# 1. Executar investigação (Pre-4) e aguardar aprovação de Vitor

# 2. Backup do histórico interno
tar czf /tmp/painel-adm-backup-$(date +%Y%m%d-%H%M%S).tar.gz painel-adm/.git

# 3. Remover .git aninhado
rm -rf painel-adm/.git

# 4. Verificar que repo pai agora rastreia tudo
git status painel-adm/
git add painel-adm/

# 5. Proceder com git mv
git mv painel-adm/auth-service/ services/auth/
git mv painel-adm/camera-gateway/ services/camera-gateway/
git mv painel-adm/inference-service/ services/inference/
git mv painel-adm/ws-gateway/ services/ws-gateway/
git mv painel-adm/scheduler-service/ services/scheduler/
git mv painel-adm/training-service/ services/training/
```

## Referências
- OQ-002 em `docs/decisions/open-questions.md`
- Pre-4 task em `docs/decisions/initial-assessment.md`
