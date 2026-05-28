# ADR-0011: Como tratar painel-adm/ como git worktree na Fase 0

## Status
Aceito

## Data
2026-05-27

## Contexto

O diretório `painel-adm/` contém um arquivo `.git` (91 bytes), não um
diretório `.git`. O plano Fase 0 propõe `git mv painel-adm/auth-service/
services/auth/` e similares.

### Investigação do painel-adm/.git

**Conteúdo do arquivo `painel-adm/.git`:**
```
gitdir: /Users/vitoremanuel/Documents/Logikos/CATH/EPI - CATH V2/.git/worktrees/painel-adm
```

**Conclusão:** `painel-adm/` é um **git linked worktree**, não um
repositório git aninhado nem um submódulo.

- `git worktree list` confirma:
  ```
  /path/to/repo             [develop]
  /path/to/repo/painel-adm  a24fe5f [painel-adm]
  ```
- Branch `painel-adm` existe no repositório principal com commit `a24fe5f`
- Arquivo `.gitmodules` não existe — confirmado não é submodule
- Os arquivos de `painel-adm/` estão rastreados na branch `painel-adm`,
  não na branch principal (`staging`/`develop`)

**Por que `painel-adm/` aparece como untracked em staging/develop:**
O worktree está checado para branch `painel-adm`. Do ponto de vista da
branch principal, `painel-adm/` é um diretório não rastreado (seus arquivos
vivem em outra branch).

Além disso, `painel-adm/` contém mais do que os 6 microsserviços listados no plano:
- `auth-service/`, `camera-gateway/`, `inference-service/`, `ws-gateway/`,
  `scheduler-service/`, `training-service/` (listados no plano)
- `backend/` — conteúdo desconhecido (cópia do backend principal?)
- `frontend/` — conteúdo desconhecido
- `migrations/` — conteúdo desconhecido
- `pre-annotation-service/` — serviço DINO+SAM
- `agent/` — desconhecido
- `landing-page/` — cópia do landing?

Estes diretórios extras não foram mapeados no plano original.

## Decisão

**Opção escolhida: Remover o worktree de `painel-adm/` e incorporar
os arquivos necessários a partir da branch `painel-adm`.**

Procedimento aprovado:
1. **Pre-4 (investigação):** Comparar conteúdo dos diretórios de
   `painel-adm/` vs equivalentes em `backend/`, `frontend/` etc.
   Documentar destino em `docs/decisions/painel-adm-investigation.md`.
   Aguardar aprovação de Vitor.
2. Após aprovação: `git worktree remove painel-adm` (remove o link
   de worktree; arquivos continuam na branch `painel-adm`)
3. Para cada serviço a mover (ex: camera-gateway/):
   `git checkout painel-adm -- camera-gateway/`
   Isso traz os arquivos para o working tree da branch atual.
4. `git mv camera-gateway/ services/camera-gateway/` etc.
5. Commit das adições + movimentações

## Alternativas Consideradas

### A: git submodule
- Descartada desde o início: Railway não suporta submodules;
  `painel-adm/` não é um submodule (confirmado: sem `.gitmodules`)

### B: `rm -rf painel-adm/.git` e `git add painel-adm/`
- Era a abordagem da versão anterior deste ADR, baseada na premissa
  incorreta de que era um repo aninhado
- Incorreta: `rm -rf painel-adm/.git` corromperia o worktree;
  o arquivo `.git` de 91 bytes é uma referência de worktree, não
  um diretório de repositório

### C: `git worktree remove` + `git checkout painel-adm -- <dir>` **(ESCOLHIDA)**
- Prós: procedimento correto para worktrees; preserva histórico da
  branch `painel-adm`; sem corrupção do repositório
- Contras: requer entendimento do que está na branch `painel-adm`
  antes de agir (mitigado pela Pre-4 investigation)

## Consequências

### Positivas
- Procedimento correto para git worktree (sem corrupção)
- Branch `painel-adm` preservada como histórico
- Fase 0 pode prosseguir com `git mv` após incorporar arquivos

### Negativas
- Pre-4 obrigatória antes de qualquer ação em `painel-adm/`
- Necessário entender o que está na branch `painel-adm` vs staging

### Neutras
- Pre-4 investigation pode revelar código relevante que precisa ser portado

## Implementação

```bash
# 1. Executar Pre-4 investigation e aguardar aprovação de Vitor

# 2. Remover o worktree
git worktree remove painel-adm
# (A branch painel-adm continua existindo — apenas o checkout é removido)

# 3. Para cada serviço aprovado na Pre-4, incorporar da branch painel-adm:
git checkout painel-adm -- camera-gateway/
git checkout painel-adm -- inference-service/
git checkout painel-adm -- ws-gateway/
git checkout painel-adm -- scheduler-service/
git checkout painel-adm -- training-service/
git checkout painel-adm -- auth-service/

# 4. Proceder com git mv para estrutura final
git mv camera-gateway/ services/camera-gateway/
git mv inference-service/ services/inference/
git mv ws-gateway/ services/ws-gateway/
git mv scheduler-service/ services/scheduler/
git mv training-service/ services/training/
git mv auth-service/ services/auth/
```

## Referências
- OQ-002 em `docs/decisions/open-questions.md`
- Pre-4 task em `docs/decisions/initial-assessment.md`
- `git worktree list` — output verificado em 2026-05-27
