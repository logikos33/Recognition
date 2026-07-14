# ADR-0039 — Provedores de compute de treinamento (nuvem/edge/self-hosted) + credenciais via integrações

**Status:** Aceita (aprovada 2026-07-11) · **Data:** 2026-07-11 · **Estende:** ADR-0038 (dispatch Vast.ai),
ADR-0031 (Training Studio) · **Relaciona:** ADR-0058 (integrações/segredos), ADR-0025 (hardware Orin),
edge-sync-agent, ADR-0027/0028 (evidência R2).

## Contexto

O dispatch de treino hoje só fala com a **Vast.ai** (nuvem, ADR-0038). Precisamos de mais opções:
1. **Treinar no EDGE do cliente** (Jetson) quando houver GPU disponível — dados não saem do site.
2. **Plugar um edge da Logikos** (nó de treino externo, mais potente) numa instância de cliente —
   treino gerenciado sem depender da nuvem.
3. **Vast.ai + R2 configuráveis DENTRO da plataforma** (painel de integrações), não só via env.

## Decisão

### 1. Abstração de provedor de compute
Interface `TrainingCompute`: `dispatch(job)` · `poll(job)` · `stop(job)` · `fetch_result(job)`.
Implementações plugáveis:
- **VastAiProvider** (nuvem, on-demand — pesado).
- **EdgeProvider** (client OU logikos — via edge-sync-agent).
- **LocalProvider** (dev/Colab — fallback).

`training_jobs.compute_target` = `vast | edge_client | edge_logikos | local` (+ `compute_node_ref`).
Ao iniciar um treino, o usuário **escolhe o alvo** (Nuvem / Edge do site / Nó Logikos), com
disponibilidade + capacidade GPU exibidas; ou política de auto-roteamento (ex.: pequeno→edge, grande→nuvem).

### 2. Treino no edge (cliente ou Logikos)
- O **edge-sync-agent** ganha capacidade de **treino**: recebe um job (dataset_version + config),
  treina na GPU local (RF-DETR/YOLOX), **reporta progresso** (mesmo canal do inference) e **sobe o
  modelo pro R2** ao terminar. O modelo entra no registry com linhagem, igual à nuvem.
- O **heartbeat do edge** passa a informar GPU/VRAM/uso → a plataforma sabe se aquele edge **pode
  treinar** e mostra a capacidade.
- **Nó de treino Logikos:** um edge mais potente (ex.: box com RTX 4090) registrado como **recurso de
  compute atrelável a um tenant** — mesmo agente/protocolo do edge do cliente, mas dedicado a treino.
  Permite "treino gerenciado" (a Logikos treina pro cliente sem custo de nuvem por job).

### 3. Credenciais via integrações (ADR-0058)
- **Vast.ai (API key)** e **R2 (endpoint/bucket/keys)** passam a ser configuráveis no **painel de
  Integrações** (cifradas at-rest, write-only/masked, botão "Testar conexão") — default por plataforma
  + **BYO por tenant** (cliente que quer o próprio R2/compute). O dispatch e o registry **leem daí**, com
  precedência sobre o env.

## Consequências / trade-offs (honestos)

- **Edge do cliente (Jetson Orin NX):** GPU **limitada** — serve pra **fine-tune pequeno/lento**, não
  treino pesado. O valor é **data-locality**: os dados **não saem do site** (privacidade + banda) — forte
  argumento de venda pra clientes sensíveis a dados.
- **Nó Logikos (potente):** treino gerenciado, sem custo de nuvem por job; ótimo pra bootstrap.
- **Nuvem (Vast.ai):** on-demand, escala pra treino pesado; custo por hora.
- **Complexidade:** a abstração de provider + o edge-agent treinar exigem cuidado (o mesmo agente faz
  inference E training — isolar recursos pra não competir com a inferência ao vivo).
- **Segurança:** credenciais no store de integrações (cifradas), isolamento por tenant; o edge sobe o
  modelo por presigned URL (device token RS256), igual à evidência (ADR-0028).

## Faseamento
Fica para **Fase B/C** da pipeline (após validar a Fase A E2E na nuvem/Colab). Ordem sugerida:
integrações (Vast.ai/R2 no painel) → EdgeProvider (nó Logikos) → treino no edge do cliente.

## Referências
ADR-0038, ADR-0031, ADR-0058, ADR-0025, edge-sync-agent, TRAINING_PIPELINE_DESIGN.md.
