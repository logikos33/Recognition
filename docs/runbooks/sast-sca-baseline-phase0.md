# SAST/SCA Baseline — Phase 0

**Data:** 2026-07-14
**Ferramentas:** bandit (SAST), pip-audit (SCA)
**Escopo:** `services/` (bandit) · `requirements/*.txt` (pip-audit)

## Estado no início da Fase 0

`bandit -r services/ -x '*/tests/*,*/test_*.py'` → **198 achados** de histórico, nenhum
introduzido por este PR (só ligamos o scanner).

Distribuição por regra:

| Regra | Descrição | Ocorrências |
|---|---|---|
| B608 | hardcoded_sql_expressions (SQL montado por f-string/format) | 89 |
| B110 | try_except_pass | 36 |
| B108 | hardcoded_tmp_directory | 20 |
| B603 | subprocess_without_shell_equals_true | 17 |
| B404 | import subprocess (blacklist informativo) | 13 |
| B105 | hardcoded_password_string | 6 |
| B607 | start_process_with_partial_path | 5 |
| B311 | random não-criptográfico (blacklist informativo) | 3 |
| B310 | urllib urlopen (blacklist informativo) | 3 |
| B101, B112, B405, B314, B202, B104 | diversos (1 cada) | 6 |

Severidade: 1 HIGH (`services/api/scripts/rtsp_simulator.py:84`, `tarfile.extractall`
sem validação de membros — script de simulação/dev, fora do caminho servido), demais
MEDIUM/LOW.

**B608 merece nota:** a constitution (C-05) exige zero SQL com f-string de *input do
usuário*. Bandit não distingue SQL estático de SQL com input do usuário — os 89
achados precisam de triagem manual (não assumir que são todos falso-positivo nem
todos reais). Isso é trabalho de uma sprint de qualidade, não deste PR de CI.

`pip-audit -r requirements/{base,api}.txt` → **0 vulnerabilidades conhecidas** (rodado
localmente em 2026-07-14; os demais arquivos de `requirements/` rodam no CI via matrix,
sem necessidade de instalar torch/ultralytics localmente para validar).

**Achado real do primeiro run em CI (PR #165):** `pip-audit -r requirements/pre-annotation.txt`
falhou — não por vulnerabilidade, mas por **conflito de resolução de dependências**
(`supervision>=0.19.0` colide com outro pacote pinado em `pre-annotation.txt`). É um
problema pré-existente do arquivo, exposto pela primeira vez porque nada rodava
`pip install`/`pip-audit` contra ele no CI antes. Não é bloqueante (job com
`continue-on-error`), mas fica registrado aqui para triagem — corrigir
`requirements/pre-annotation.txt` é trabalho de uma sprint de qualidade, não deste PR
de CI. As demais 8 combinações de `requirements/*.txt` passaram sem vulnerabilidades
conhecidas. `npm audit --audit-level=high` em `apps/frontend` e `apps/landing` também
rodou de verdade e encontrou achados reais (15 vulnerabilidades no frontend, incluindo
1 crítica em dependências transitivas de dev/build — `vite`/`esbuild`/`vitest`); mesmo
tratamento: sinal não-bloqueante até triagem.

## Política Fase 0

- `bandit` e `pip-audit` rodam em **todo push/PR** para `develop`/`staging`/`main`,
  mas com `continue-on-error: true` — **não bloqueiam o merge** nesta fase.
- Os relatórios (`bandit-report.json`) sobem como artefato do workflow para consulta.
- O objetivo agora é **visibilidade contínua**, não gate — o baseline fica documentado
  aqui, não silenciado.

## Como promover a bloqueante

Em sprint de qualidade futura, uma vez triados os 198 achados do bandit:

1. Corrigir ou suprimir (com `# nosec` + justificativa) os achados triados como
   falso-positivo ou aceitos.
2. Remover `continue-on-error: true` do job `bandit` em
   `.github/workflows/security-scan.yml`.
3. Fazer o mesmo para `pip-audit` assim que o lock de `fix/pin-python-deps` estiver
   em produção há pelo menos um ciclo de release (evita quebrar CI por CVE em pacote
   transitivo sem plano de correção).
4. Cada passo em PR separado, igual ao runbook de lint (`lint-baseline-phase0.md`).

## Referência

- `.github/workflows/security-scan.yml` — jobs `bandit`, `pip-audit`, `npm-audit`, `sbom`
- Relatório bruto do bandit desta rodada: artefato `bandit-report` do primeiro run do CI
  neste PR (`fix/ci-supplychain-sast`)
