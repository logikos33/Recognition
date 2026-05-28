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

---

## OQ-006 — Estratégia para serviços removidos de staging na Fase 3

**Decisão (2026-05-27):** Opção C modificada — **Referência pura**.

Disposição final por serviço:

| Serviço | Decisão | Motivo |
|---------|---------|--------|
| `camera-gateway` | **REFERÊNCIA** | Consultar durante Fase 3 — arquitetura nova é MediaMTX + DeepStream `nvurisrcbin`, sem FFmpeg→Redis intermediário |
| `ws-gateway` | **REFERÊNCIA** | Padrão já está em api-v3 (`socket_bridge.py`) |
| `training-service` | **ARCHIVE** | Workflow mudou para Roboflow + Colab puro; código do Hub client não se aplica |
| `scheduler-service` | **ARCHIVE** | Celery Beat no worker já cobre; sem funcionalidade nova |
| `auth-service` | **ARCHIVE** | api-v3 substituiu completamente |
| `pre-annotation-service` | **ARCHIVE** | Nunca usado em produção |

A tag `archive/microservices-attempt-1` preserva todo o código. Para desenvolvimento
da Fase 3, consultar apenas `camera-gateway` e `ws-gateway` como referência de
padrões arquiteturais. Os demais são descartados sem consulta.

**Nota sobre camera-gateway:** A arquitetura de edge usa MediaMTX (RTSP re-streaming)
+ DeepStream `nvurisrcbin` (leitura direta do stream na pipeline GStreamer). O pipeline
FFmpeg→HLS→Redis do camera-gateway original não se aplica — é referência apenas para
entender os padrões de saúde de stream e reconexão.

---

## OQ-007 — Engine de inferência na Fase 3

**Decisão (2026-05-27):** Opção C-modificada — **Multi-backend desde Fase 3**.

`services/inference/` implementa dois backends desde o início, selecionáveis por
env var `INFERENCE_ENGINE`:
- `INFERENCE_ENGINE=deepstream` — produção edge RVB (pipeline GStreamer nativo)
- `INFERENCE_ENGINE=ultralytics` — dev/staging/fallback (sem GPU obrigatória)

Mesma interface Redis pub/sub. Mesmo schema de evento. Mesma API interna.

**Razões:**
- Mantém ADR-0001 sem contradição (DeepStream é o backend de produção)
- Permite desenvolvimento sem GPU (Ultralytics em CPU)
- Permite test harness sem GPU no CI
- Fallback se DeepStream der problema no go-live
- Plano original já previa "multi-backend"

Detalhes de implementação em ADR-0015.
