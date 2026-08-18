# D-031 · Provedor de GPU: Vast.ai é o do código; RunPod é outro sistema

**Seção:** Contrato e jurídico · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · ✅ vigente · resolve a pendência "Suboperador de GPU no contrato"**

O Vitor disse usar RunPod. Investigação (C4): o código do treino do **modelo de visão** (RF-DETR/YOLOX) é
genuinamente Vast.ai — `vast_client.py` fala com `console.vast.ai/api/v0` real (não é RunPod renomeado); a
única tentativa real da integração retornou 404 em 12/07 (nunca funcionou de fato). A conexão RunPod
existe, mas em **outro sistema**: `training/finetune_assistant.py`, fine-tune do **chatbot assistente**
(LLM), script manual por SSH, fora de `training_jobs`. Zero chaves Vast/RunPod em qualquer ambiente Railway.
`gpu_enabled` não checa `RUNPOD_API_KEY` → a tela reporta GPU desabilitada mesmo com RunPod setado.
**Para o contrato:** o suboperador de GPU do modelo de visão, se e quando ligado, é a Vast.ai — não RunPod.
Renomear o enum `gpu_provider` (migration 097, valores gravados) é migração de dados, planejada, não feita.
