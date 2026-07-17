# Reconciliação — artefatos de edge fora do develop (2026-07-16)

> Porque o Claude Code registrou (C-04) que "tasks 101–104 e docs de planejamento não existem em nenhuma branch":
> vários artefatos desta frente estão **untracked na cópia de trabalho** ou em **branch não-mergeada**.
> Este doc é o mapa do que precisa **entrar no develop**, o que **descartar** (duplicado) e o que **verificar**.

## A. Merge para develop (resultado dos experimentos)
- **Branch `claude/jetson-experiments-sequence-a53d0f`** → contém `docs/edge/EXPERIMENTOS_2026-07-16.md` (resultados
  103/104/101/102). **Mergear no develop** (merge commit).

## B. Adicionar ao develop (só existem na cópia de trabalho — NÃO estão em nenhuma branch)
Commitar (worktree de origin/develop → PR):
- Tasks: **099, 101, 102, 103, 104, 105** (specs).
- Docs: **`docs/edge/PLANEJAMENTO_EXPERIMENTOS_EDGE.md`**, **`docs/edge/REGRAS_PLATAFORMA_JETSON.md`** (com as landmines de 16/07).
- Edições: ponteiro de edge na **`DIRETRIZ_OPERACAO_CLAUDE_CODE.md`**, status **ADR-0040** (Aceito), **queue.txt / queue-hardware.txt**.
- Prompt: `tools/agent-driver/tasks/EXPERIMENTOS-JETSON-PROMPT-claude-code.md`.

## C. DESCARTAR (duplicado — versão canônica já está no develop)
A cópia de trabalho tem duplicatas de arquivos que o Code **já mergeou** no develop (versões dele são as boas):
- Tasks **077–098**, ADRs **0043–0047**, docs de governança (SECURITY, CONTRIBUTING, BENCHMARK_*, LGPD), `docs/README`.
- **Não re-commitar** esses — usar a versão do develop pra não gerar conflito/regressão.

## D. VERIFICAR (findings de campo que podem se perder)
Meus appends de 16/07 nas tasks **087/088/095/100** (NIC `enP8p1s0`, netfilter/iptables, timezone/NTP, gotchas Tailscale,
confirmação DeepStream 7.1) — conferir se a versão do develop já contém. Se **não**, portar SÓ esses trechos.
(Boa parte já foi capturada pelo Code no `STATUS_2026-07-16` / `EXPERIMENTOS_2026-07-16`.)

## Ordem sugerida
1. Merge A (resultados). 2. PR com B (specs/docs novos). 3. Verificar D e portar o que faltar. 4. Ignorar C.
> Depois disso, develop reflete a realidade da frente de edge e o Code para de trabalhar "pela spec do prompt".
