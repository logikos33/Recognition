# OQ Responses — Respostas de Vitor às Open Questions

Data: 2026-05-27
Formato: respostas literais do usuário, preservadas para histórico de decisão.

**Nota:** Versão final das respostas após esclarecimento de 2026-05-27 sobre estado
pre-produção do sistema. OQ-003 foi refinada em duas iterações: resposta inicial
assumia cliente Quality em produção (shadow mode aprovado); após esclarecimento de
que Quality é módulo sem clientes ativos, decisão foi revertida para cutover direto.
A versão registrada abaixo é a **versão final** de cada OQ.

---

## OQ-001 — Chat/Assistant

Decisão: A — Manter como feature experimental.
Não promover, não remover. Documenta em docs/decisions/log.md como
"chat/assistant: feature experimental preservada, fora do escopo do
edge deployment. Roadmap a decidir no futuro."
Restrição: o trabalho de edge deployment NÃO deve quebrar essa feature.
Se algum refactor afetar /api/chat, ChatFAB, assistant_docs ou migration
pgvector, preserva o comportamento atual.
Mantém OQ-001 em open-questions.md marcada como "decisão futura — não
bloqueia edge deployment".

---

## OQ-002 — painel-adm/ é repo aninhado + contém mais que 6 serviços

Decisão em duas etapas.

ETAPA 1 — Investigação obrigatória (antes da Fase 0):
Pre-flight task adicional (chamada Pre-4):
- Compara painel-adm/backend/ com backend/ (raiz):
  * diff -r dos diretórios
  * timeline de commits (git log do .git interno)
  * arquivos exclusivos em cada lado
- Mesmo pra painel-adm/frontend/ vs frontend/
- Mesmo pra painel-adm/migrations/ vs backend/app/infrastructure/
  database/migrations/
- Inspeciona painel-adm/landing-page/, pre-annotation-service/, agent/
Documenta tudo em docs/decisions/painel-adm-investigation.md com
recomendação por diretório:
- ARCHIVE: mover pra archive/painel-adm-legacy/<nome>/ (preservar histórico)
- DELETE: confirmado código morto
- MERGE: porta código relevante divergente
NÃO executa decisão. Aguarda aprovação de Vitor após leitura do arquivo.

ETAPA 2 — Tratamento do .git aninhado:
Procedimento aprovado conforme ADR-0011:
1. Após investigação concluída e decisões tomadas
2. Backup do painel-adm/.git pra /tmp/painel-adm-backup-{timestamp}.tar.gz
   (caso precise resgatar histórico depois)
3. rm -rf painel-adm/.git
4. git add painel-adm/
5. Proceder com git mv normal

---

## OQ-003 — Tasks EDGE durante migração (decisão estratégica)

**Versão final após esclarecimento:** Recognition está em estado pre-produção.
Quality é um módulo do produto, não um cliente. Não há clientes ativos em produção.
RVB Isolantes será o primeiro tenant a usar o sistema em ambiente real.

Decisão final: **Cutover direto na Fase 3. Sem shadow mode.**

As 6 tasks EDGE permanecem no cloud Celery durante Fases 0–2 (período de build).
Na Fase 3, cutover direto para services/inference/ sem período de coexistência.

Sem migrations 046/047. Sem Fase 6.5. Sem roteamento dual por câmera.

Documenta isso em ADR-0013 (direct-cutover-no-shadow).

---

## OQ-004 — `models` como canônica

Decisão: Confirmado. `models` é a tabela canônica para edge manifest.
ADR-0012 aprovado.
Bug fix em quality_inference.py:90 deve ser Pre-1 (preceder Fase 0)
conforme já planejado.
`trained_models` permanece sem alteração, marcado como "legacy, sem
remoção planejada neste deployment". Documenta em log.md.

---

## OQ-005 — Branch base

Decisão: a partir de `staging`.
Razão: staging tem auto-deploy Railway, quero ver mudanças subindo em
staging conforme cada PR mergeia. Develop ainda não existe formalmente;
cria a partir de staging.

Fluxo aprovado:
- main (produção, protegida)
- staging (atual, auto-deploy Railway)
- develop (nova, criada de staging — recebe PRs das feature branches)
- feature/* (uma por fase do plano)

Sequência de merge:
- feature/<fase> → develop (PR + aprovação minha)
- develop → staging (quando develop estiver verde + testado)
- staging → main (após validação em staging)

Branch da Fase 0: feature/phase-0-reorg a partir de develop.
Branch do pre-flight: feature/preflight-fixes a partir de develop.
