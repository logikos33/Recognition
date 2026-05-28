# OQ Responses — Respostas de Vitor às Open Questions

Data: 2026-05-27
Formato: respostas literais do usuário, preservadas para histórico de decisão.

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

Decisão: C — Dual mode com shadow period.

Regra de ouro: cloud Quality NUNCA para de funcionar pro cliente atual
em produção até validação completa do edge.

Estratégia em fases:
1. FASES 0-5 (BUILD): As 6 tasks EDGE continuam rodando no cloud Celery,
   sem alteração. Cliente Quality em produção segue funcionando como
   hoje. Novos serviços (services/inference/) são desenvolvidos em
   paralelo mas NÃO recebem tráfego.

2. FASE 6 (SHADOW): Quando edge stack estiver pronto na RVB, edge
   processa as MESMAS câmeras em paralelo com cloud durante período
   de validação (mínimo 7 dias).

   Adicionar:
   - Migration 046_event_origin.sql: coluna `origin VARCHAR(20)` em
     alerts, camera_events, counting_events (valores: 'cloud', 'edge')
   - Dashboard de comparação shadow: edge vs cloud (detecções/min,
     latência, false positives equivalentes?)

3. FASE 6.5 (CUTOVER POR CÂMERA): Validado o shadow, cutover gradual.

   Adicionar:
   - Migration 047_processing_mode.sql: coluna `processing_mode VARCHAR(20)`
     em ip_cameras (valores: 'cloud', 'shadow', 'edge')
   - Default 'cloud' pra todas. Câmera vira 'shadow' durante validação,
     depois 'edge'.
   - Se algo der errado, voltamos pra 'cloud' instantaneamente (1 UPDATE).

4. FASE PÓS-RVB-GO-LIVE (FORA DESTE PLANO): Quando 100% das câmeras RVB
   estão em 'edge' por 30 dias sem incidente, planejar desligamento
   físico das tasks Celery EDGE. NÃO faz parte deste deployment.

Documenta isso em ADR-0013 (shadow-mode-cutover).
Atualiza EDGE_DEPLOYMENT_PLAN.md adicionando:
- Migrations 046 e 047 na seção da Fase 1
- Fase 6.5 (Shadow Validation) entre Fase 6 e Fase 7
- Critério de aceitação na Fase 10: cutover por câmera funcionando

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
