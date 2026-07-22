# Decisões do Bloco 2 — respostas para o Claude Code

**Data:** 2026-07-21 · **Contexto:** PR #202 (reconciliação de go-live). As 4 decisões que travavam o worker
de operações e a ponte do edge estão resolvidas abaixo. Pode seguir com a parte cloud do Bloco 2/3 num PR próprio.

---

## D1 — Registry de operation-types: **DECLARATIVO**

Construir o mecanismo declarativo (registro em runtime + schema em banco), não o estático (classe + deploy).

**Racional:** cumpre a tese central do produto — configurar sem tocar no código. A intenção é que tipos de
operação possam nascer sem deploy.
**Trade-off aceito conscientemente:** dá mais trabalho agora (mecanismo declarativo + UI schema-driven, não só
duas classes). `attention_points` e `stage_timer` já existem — migrá-los para o modelo declarativo faz parte.
**Referência de padrão:** o plugin auto-descritivo do Agent Studio (declara parâmetros + tipos + doc → a UI se
gera sozinha). Vale usar como inspiração de implementação.

## D2 — DeepStream config: **RUNTIME + RELOAD ESTRUTURAL**

O pipeline lê a config da ponte que já existe (F1, config/poll). Não gerar-e-reiniciar.

**Racional:** aproveita a ponte já construída e não derruba as 28 câmeras a cada ajuste (crítico para 24/7).
**Regra de fronteira:** parâmetros **quentes** (FPS/interval, threshold, ROI, zona, regra) aplicam **sem
restart**. Só mudança **estrutural** (troca de modelo, add/remove de câmera, mudança de batch) dispara um
**reload controlado** — no mesmo padrão que o `model_watcher.py` já usa para modelo. Definir e documentar
explicitamente qual conjunto de mudanças é "estrutural".

## D3 — Canal de detecção edge→cloud: **`/api/v1/edge/events/ingest` é o canônico**

Confirmar `events/ingest` (existe, testado, com dedup) e **matar `/detections`**.

**Ação:** reapontar o uploader do edge-sync-agent para `events/ingest`; remover a referência a `/detections`
(rota que nunca existiu no servidor). Não implementar `/detections`.

## D4 — Enrollment duplo e `/auth/rotate`: **BACKLOG**

Não entra antes do go-live.

**Racional:** a RVB é um device, um site. O caminho `edge/enroll` funciona e basta. Rotação de chave sem
re-enrollment é conveniência de frota; num site único, se a chave precisar mudar, re-enrollment resolve.
**Pós-go-live:** unificar os dois fluxos (aposentar o `devices/` órfão) e avaliar `/auth/rotate` quando houver
frota. Manter o `devices/` órfão na trilha de segurança como limpeza pendente (não é bloqueante).

---

## Próximo passo autorizado

Com D1–D4 resolvidas, seguir com a **parte cloud do Bloco 2/3** — o **worker de operações** que avalia contra o
stream fora do `/test` e popula `operation_results` — num PR próprio na develop. Não promover para staging/main.

**Continua sendo gate humano / cliente (não do Code):** rotação da senha admin pela app · promoção
develop→staging · fan quiet→cool (sudo) · credenciais Intelbras · contrato da API Wiser · lista dos pontos de
atenção da peça.
