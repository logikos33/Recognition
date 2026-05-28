# ADR-0011: Tratamento do gitlink órfão painel-adm/

## Status
Aceito (revisado 2026-05-27 — sobrescreve versão anterior baseada em premissa incorreta)

## Data
2026-05-27

## Contexto

`git ls-tree staging` retorna:
```
160000 commit a24fe5f9e3325881e6808ce8b8e03659fa318a8e    painel-adm
```

Modo `160000` é um **gitlink** — referência a um commit externo usada por
submodules. Porém não existe `.gitmodules` no repositório. Resultado: estado
de submodule incompleto, também chamado de **gitlink órfão**. O Git sabe que
há uma referência, mas não sabe de onde clonar.

Simultaneamente, `painel-adm/` existe no filesystem como um **git linked
worktree** apontando para a branch local `painel-adm` (commit `a24fe5f`,
2026-04-16, "pre-quality-module implementation checkpoint"). Essa branch nunca
foi pushed para origin — existe apenas localmente.

### O que está na branch painel-adm

A branch `painel-adm` é um savepoint frozen do projeto **antes** do módulo
Quality ser implementado. Contém:

```
auth-service/    camera-gateway/   inference-service/  ws-gateway/
training-service/  scheduler-service/  pre-annotation-service/
backend/  frontend/  landing-page/  migrations/  agent/  scripts/
```

### Por que esses serviços não estão em staging

Entre abril e maio de 2026, os serviços foram absorvidos pelo monolito `api-v3`
e explicitamente removidos de staging:

| Serviço | Commit de remoção | Motivo |
|---------|-------------------|--------|
| auth-service | f547609 (2026-05-08) | Funcionalidade absorvida por api-v3 |
| camera-gateway | f547609 (2026-05-08) | Idem |
| ws-gateway | f547609 (2026-05-08) | Idem |
| training-service | f547609 (2026-05-08) | Idem |
| scheduler-service | 8dfeae9 (2026-05-08) | Substituído pelo Celery Beat no worker |
| pre-annotation-service | e5582c9 | DINO+SAM nunca usado em produção |

**Esses serviços foram deletados intencionalmente, não arquivados.**
`git mv painel-adm/camera-gateway/ services/camera-gateway/` não funciona e
não deve acontecer: (1) gitlink não aceita `git mv`; (2) a intenção foi remover,
não reorganizar.

### Versão anterior deste ADR

A versão anterior propunha `git worktree remove painel-adm` seguido de
`git checkout painel-adm -- camera-gateway/` para cada serviço aprovado.
Esse procedimento foi invalidado pela investigação de Pre-4 (2026-05-27):
os serviços foram removidos de staging por decisão arquitetural — não faz
sentido reincorporá-los via checkout no branch principal.

## Decisão

**Remover o gitlink órfão e o worktree vinculado; preservar o conteúdo como
tag arquivada.**

Procedimento:

```bash
# 1. Remover o gitlink do index (elimina a entrada 160000 de staging/develop)
git rm --cached painel-adm

# 2. Remover o linked worktree do filesystem
git worktree remove painel-adm
# painel-adm/ desaparece do filesystem; branch painel-adm continua existindo

# 3. Criar tag permanente apontando para o commit preservado
git tag archive/microservices-attempt-1 refs/heads/painel-adm
# Tag pushed para origin como referência histórica permanente

# 4. Commit para remover o gitlink do tree
git commit -m "chore: remove orphan painel-adm gitlink — preserved as archive/microservices-attempt-1"
```

Após isso:
- `git ls-tree develop` não mostra mais `painel-adm`
- `git show archive/microservices-attempt-1:camera-gateway/` acessa o código
- Branch `painel-adm` permanece localmente para consulta durante Fase 3

## Alternativas Consideradas

### A: Manter como worktree
- Descartada: gitlink órfão sem `.gitmodules` cria estado confuso para
  qualquer colaborador; `git clone` não reconstrói o worktree

### B: Criar `.gitmodules` e transformar em submodule real
- Descartada: Railway não suporta submodules; os serviços foram
  intencionalmente removidos — formalizá-los como submodule vai contra a
  decisão arquitetural

### C: `git checkout painel-adm -- <dir>` para reincorporar serviços
- Descartada: os serviços foram removidos por decisão, não por acidente.
  Reincorporação seria regressão. Para Fase 3, os serviços que valem
  serão portados com base no código da tag `archive/microservices-attempt-1`,
  não via `git checkout` no branch principal.

### D: Push da branch painel-adm para origin
- Desnecessário: a tag `archive/microservices-attempt-1` é suficiente e
  mais semântica. Branch é para desenvolvimento ativo.

## Consequências

### Positivas
- Tree de `develop` e `staging` fica limpa (sem gitlink órfão)
- Código preservado permanentemente via tag
- Estado arquitetural claro: monolito api-v3 é canônico; microsserviços
  são referência histórica

### Negativas
- Worktree local desaparece; acesso ao código passa a ser via `git show`
  ou checkout temporário da tag

### Neutras
- Fase 3 decide por serviço se porta o código da tag (ver ADR-0014)

## Referências

- `docs/decisions/painel-adm-branch-investigation.md` — investigação completa
- ADR-0014 — estratégia de arquivo e disposição por serviço
- Commits de remoção: f547609, 8dfeae9, e5582c9
