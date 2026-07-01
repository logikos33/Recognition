# Prompt para colar no Claude Code — Mutirão de qualidade

```
Leia e siga à risca tools/agent-driver/MUTIRAO.md (e o tools/agent-driver/AUTORUN.md que ele
referencia para o loop por PR), além de CLAUDE.md e AGENTS.md. Esta é uma missão de SAÚDE DE
CÓDIGO, não de features: auditar tudo, corrigir o débito técnico, subir a cobertura e garantir
que o frontend bate com o backend — de forma autônoma, do início ao fim, sem parar entre itens.

Execute nesta ordem:

FASE 0 — Bootstrap (AUTORUN Fase 0): git checkout develop && pull; tree limpo; docker compose
-f docker-compose.dev.yml up -d; criar role/banco test:test/recognition_test no Postgres do
compose e validar a conexão ANTES do pytest; env idêntico ao ci.yml; rodar baseline e confirmar
develop verde.

FASE 1 — AUDITORIA (read-only): varra services/api/ e apps/frontend/ com as skills code-review,
security-review, tech-debt e testing-strategy. Produza docs/quality/AUDITORIA_<data>.md com a
lista priorizada P0/P1/P2/P3 (arquivo:linha, severidade, fix, esforço), incluindo os débitos
conhecidos do CLAUDE.md (Débitos Técnicos P3). Produza também docs/quality/CONTRATO_FRONT_BACK.md
cruzando cada chamada de API do frontend (services/*.ts e todo fetch() raw) contra as rotas reais
do backend (blueprints em app/api/v1/**/routes.py): existe a rota? método bate? o tipo TS bate com
o envelope {status,data}? Toda divergência vira item. NÃO corrija nada ainda — commit a auditoria
num PR de chore próprio (branch chore/auditoria-mutirao), CI verde, merge.

Itens P0 que JÁ SEI que existem e têm que entrar: (1) cross-tenant — frame_repository.count_validated()
e get_annotated_by_video() não filtram por tenant_id (e varrer todos os repositories atrás de
SELECT/UPDATE/DELETE sem tenant_id); (2) AnnotationPage.tsx usa fetch() raw em vez do wrapper api.ts;
(3) os 11 testes deselecionados no ci.yml; (4) eventlet deprecated (worker SocketIO) — alto risco.

FASE 2 — Fila: converta o inventário em itens pequenos (um tema por PR, alvo ≤~400 linhas),
grave em tools/agent-driver/queue-mutirao.txt na ordem: P0 segurança (cross-tenant primeiro) →
P1 bugs → contrato front↔back → cobertura → padrões/limpeza → alto-raio (eventlet) por último.

FASE 3 — Loop AUTORUN por item (branch quality/item-NN-slug → portão local verde → PR develop →
CI verde → review por risco → squash merge → próximo). Regras do mutirão:
- PRs pequenos e temáticos; refactor/fix, não feature; preservar contrato salvo onde conserta bug.
- Cobertura HONESTA: proibido baixar --cov-fail-under, adicionar deselect/skip/xfail novo, apagar
  teste, ou escrever teste oco. Meta: global ≥60%, e ≥80% nos arquivos tocados/novos.
- Os 11 deselecionados: corrigir a CAUSA RAIZ e REMOVER o --deselect do ci.yml no mesmo PR, verde.
- Segurança nunca regride (tenant isolation, RTSPUrlValidator, CORS explícito, masking, authz).
- ALTO RAIO (eventlet→gevent/threading, auth, worker SocketIO, refactor massivo de tenant): NÃO
  auto-mergeie. Abra o PR, passe CI+smoke, e PARE para validação humana em staging; registre no
  relatório. Isso é guard-rail, não falha.

Só pare nas condições §7 (tree sujo perigoso / vuln não-corrigível / item bloqueado / CI infra
quebrada) — nesses casos registre, pule e siga. Não me peça confirmação a cada passo. Trabalhe
até a fila do mutirão esvaziar, por mais que demore.

Ao final: verificação completa em develop (ruff + pytest com os deselects REDUZIDOS + tsc + smoke)
e relatório §8 de MUTIRAO.md — tabela de PRs, cobertura ANTES→DEPOIS (global + módulos), issues
fechados/abertos por severidade, quais dos 11 testes foram re-habilitados, divergências
front↔back encontradas vs corrigidas, e os PRs high-blast abertos pra revisão humana.

Comece agora pela Fase 0 e a auditoria da Fase 1.
```
