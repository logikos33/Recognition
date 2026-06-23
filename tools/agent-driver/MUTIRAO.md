# MUTIRAO.md — Mutirão de qualidade (auditoria + débito técnico + cobertura + contrato front↔back)

> **Para o agente (Claude Code):** missão de saúde de código, **não** de features. Objetivo:
> auditar todo o código, corrigir o débito técnico, subir a cobertura e garantir que o frontend
> bate com o backend — autonomamente, do início ao fim, sem parar entre itens. O **loop por
> item (branch → validar → PR → CI verde → review → squash merge em develop)** segue
> `tools/agent-driver/AUTORUN.md` §3–§5; este arquivo só adiciona as fases e regras do mutirão.
> Pré-condições de sessão (develop limpo, docker compose, DB de teste `test:test/recognition_test`,
> baseline verde) = AUTORUN §1/Fase 0. **Branch alvo: develop. Nunca main.**

---

## Princípios do mutirão (além dos inegociáveis do AUTORUN)
1. **Refactor/fix, não feature.** Preservar o comportamento/contrato existente, salvo onde um item
   explicitamente conserta um bug. Nada de escopo novo de produto aqui.
2. **PRs pequenos e temáticos.** Um tema coeso por PR, alvo ≤ ~400 linhas de diff. Mantém revisável
   e reduz raio de explosão na branch compartilhada.
3. **Cobertura honesta (anti-gaming) — proibido:**
   - baixar `--cov-fail-under`; adicionar `--deselect`/`skip`/`xfail` novo; apagar teste para "passar".
   - testes vazios/triviais só pra inflar número (asserts ocos, testar getter trivial).
   - Subir cobertura = escrever testes reais que exercitam lógica e casos de borda.
4. **Os 11 testes deselecionados no CI são alvo, não exceção.** Corrigir a **causa raiz** e
   **re-habilitar** removendo os `--deselect` do `.github/workflows/ci.yml`. Não deletar, não skipar.
5. **Segurança nunca regride.** Nenhum fix pode afrouxar tenant isolation, validação de URL, CORS,
   masking de credencial, authz por role.
6. **Alto raio de explosão → não auto-mergeia.** Itens que mudam modelo de concorrência (eventlet→
   gevent/threading), auth, isolamento de tenant em massa, ou o worker SocketIO: abrir PR, passar
   CI + smoke, e **PARAR para validação humana em staging** (§7.B-like). Listar no relatório.

---

## Fase 1 — AUDITORIA (read-only; produz inventário; 1º PR de chore)
Varra `services/api/` e `apps/frontend/` com as skills `engineering:code-review`,
`security-review`, `engineering:tech-debt`, `engineering:testing-strategy`. **Não corrija nada
ainda.** Produza `docs/quality/AUDITORIA_<data>.md`: lista priorizada (P0/P1/P2/P3) com
`arquivo:linha`, severidade, fix proposto e esforço estimado. Commit como PR de chore próprio
(branch `chore/auditoria-mutirao`) — assim o plano fica rastreável antes de qualquer mudança.

Categorias obrigatórias (incluir os débitos já conhecidos do `CLAUDE.md` → "Débitos Técnicos P3"):

- **Segurança (P0):**
  - Cross-tenant: `tenant_id` ausente em queries. **Confirmado:** `frame_repository.count_validated()`
    e `get_annotated_by_video()` não filtram por tenant. Varrer todos os repositories atrás de
    `SELECT`/`UPDATE`/`DELETE` sem `tenant_id`.
  - SQL não-parametrizado (f-string com input), SSRF, segredo hardcoded, `CORS(app)` bare,
    exposição de credencial de câmera/R2, JWT/role checks faltando.
- **Correção/bugs (P1):** N+1, falta de try/except em rota, casos de borda, `_dispatch_vast_ai`
  (simulação — documentar/gated, decidir destino).
- **Contrato front↔back (P1):** ver Fase 1b.
- **Cobertura (P1/P2):** módulos descobertos (validation_handlers, versioning, training dispatch)
  + os 11 testes deselecionados no CI.
- **Padrões (P2/P3):** arquivos >200 linhas, `print()` no backend, `any` no TS, `fetch()` raw
  (ex.: `AnnotationPage.tsx`) em vez de `api.ts`, `App.tsx`>100 linhas, componente >200 linhas.
- **Infra/risco (P2, alto raio):** eventlet deprecated (gunicorn v26) → migração de worker.
- **Schema drift:** colunas/tabelas referenciadas no código que não existem no schema final.

### Fase 1b — Matriz de contrato front↔back
Produza `docs/quality/CONTRATO_FRONT_BACK.md`: cruze cada chamada de API do frontend
(`apps/frontend/src/services/*.ts` + todo `fetch(` raw) contra as rotas reais do backend
(url_rules dos blueprints em `services/api/app/api/v1/**/routes.py`). Para cada par registre:
método+path do front · existe no backend? · método bate? · shape da resposta bate com o tipo TS
(envelope `{status, data}`)? · divergência. Toda divergência vira item de execução.

---

## Fase 2 — Fila de execução
Converta o inventário em itens pequenos (um tema por item), grave em
`tools/agent-driver/queue-mutirao.txt` (artefato local; nunca entra em PR de item). Ordem:
1. **P0 segurança** (cross-tenant primeiro — é vazamento de dados).
2. **P1 bugs**.
3. **P1 contrato front↔back** (alinhar o lado errado; migrar `fetch()`→`api.ts`).
4. **Cobertura** (re-habilitar os 11 + cobrir módulos descobertos).
5. **P2/P3 padrões/limpeza**.
6. **Alto raio (eventlet etc.)** por último, marcados `needs-human` (não auto-merge — §princípio 6).

Formato por linha: `item-NN <tema> risk:<low|security|high-blast>`.

---

## Fase 3 — Loop de execução (AUTORUN §3–§5 por item)
Para cada item: partir de develop limpo → branch `quality/item-NN-<slug>` → fix mínimo →
portão local (ruff + pytest com deselects atuais + tsc se tocou front) verde → stage cirúrgico →
commit Conventional (`fix(scope):`/`refactor(scope):`/`test(scope):`) → push → PR para develop →
`gh pr checks --watch` verde → review por risco → merge squash → develop verde → próximo.

- **risk:low** → auto-review (`engineering:code-review`/`review`) → merge.
- **risk:security** → `security-review` + escrutínio → merge se limpo; vuln não-corrigível → §7.B.
- **high-blast** → abre PR, CI+smoke, **PARA p/ humano** (não mergeia). Registra no relatório.
- **Item de cobertura que re-habilita teste:** depois de corrigir a causa, **remover o `--deselect`
  correspondente do `ci.yml`** no mesmo PR e provar verde.

### Metas de cobertura (concretas)
- Global: subir do baseline atual (~45–55%) para **≥60%**.
- Arquivos novos/tocados num item: **≥80%**.
- Reportar antes/depois (global + por módulo) no relatório. Sem atingir → continuar com mais
  testes, nunca afrouxando o gate.

---

## Condições de PARADA (§7 do AUTORUN) — só estas
A. tree sujo perigoso/ambíguo · B. vuln real não-corrigível (PR aberto, segue) ·
C. item bloqueado por dependência externa (`# BLOCKED`, segue) · D. CI infra quebrada.
Mais: **high-blast** sempre para pra humano (não é falha — é o guard-rail). Fora disso, não parar.

---

## Verificação final (§6) + Relatório (§8)
Em develop atualizado: ruff + pytest (deselects **reduzidos** pelos que você re-habilitou,
`--cov-fail-under` no novo patamar) + `npx tsc --noEmit` — tudo verde. `./scripts/smoke_test.sh`.

Relatório:
- Tabela de PRs: `| Item | Tema | Risco | PR | CI | Status |`.
- **Cobertura antes → depois** (global + módulos chave).
- Issues fechados vs abertos por severidade (P0/P1/P2/P3).
- **11 testes deselecionados:** quais re-habilitados / quais ainda fora (e por quê).
- Matriz front↔back: divergências encontradas vs corrigidas.
- **Itens high-blast/needs-human** abertos pra revisão (eventlet etc.) com link do PR.
- Débito remanescente pra humano.
