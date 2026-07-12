# Prompt para colar no Claude Code

```
Leia e siga à risca o arquivo tools/agent-driver/AUTORUN.md como sua constituição para esta
sessão. Também leia CLAUDE.md e AGENTS.md antes de começar.

Sua missão: processar TODA a fila tools/agent-driver/queue.txt, do topo ao fim, de forma
autônoma e sem parar entre tasks. Para cada task: leia o spec em
tools/agent-driver/tasks/task-NNN-*.md, verifique as premissas no código real, crie o branch
agent/task-NNN-slug, implemente, valide localmente espelhando o CI (ruff em services/api/ +
pytest em services/api/tests/ com os deselects do ci.yml + npx tsc --noEmit em apps/frontend),
corrija até tudo ficar verde, faça stage cirúrgico (NUNCA git add -A — anti-sweep), commit em
Conventional Commits, push, abra PR para develop, espere o CI do GitHub ficar verde, faça
auto-revisão (use as skills code-review/review; e security-review nas tasks risk:security) e
faça merge com squash. Depois volte para develop atualizado e siga para a próxima task.

Regras inegociáveis: nunca push em main; nunca merge com CI vermelho; nunca merge de código
com vulnerabilidade real não resolvida; uma task = um branch = um PR; o PR só contém os
arquivos daquela task. Só pare nas condições §7 do AUTORUN.md (working tree sujo perigoso,
vuln de segurança não corrigível, task bloqueada por dependência externa, ou CI infra
quebrada) — nesses casos pule a task, registre e continue a fila.

Não me peça confirmação a cada passo. Trabalhe até a fila esvaziar, por mais que demore.
Quando terminar, rode a verificação final (§6) e me entregue o relatório final (§8) com a
tabela de todas as tasks (PR, CI, merge) e o estado final do develop.

Comece agora: suba o Postgres+Redis locais (docker compose -f docker-compose.dev.yml up -d),
confirme git status limpo em develop, e processe a primeira linha da fila.
```
