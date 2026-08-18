# D-033 · RunPod é o provedor do primeiro treino real de visão

**Seção:** Adendos de 04/08 (pós-rodada #288–#292) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Vitor (AskUserQuestion) · 🔄**

Descartadas: consertar o caminho Vast.ai (mantém o pior cenário de LGPD) · treino local no Orin
(1-2 dias + concorrência térmica com a inferência) · decidir depois de anotar (trava no degrau seguinte).

**Razão principal, e ela é jurídica antes de ser técnica:** a Vast.ai é **marketplace** de GPU —
datacenter, empresa e país desconhecidos, suboperador **impossível de nomear** em contrato. A RunPod tem
datacenters próprios e identificáveis. Some-se a isso que a conta já existe e funciona (fine-tune do
assistente).

**Efeito no contrato:** resolve a pendência "suboperador de GPU". O documento passa a poder nomear
RunPod — mas **só depois de implementado**. Enquanto o dispatch apontar para a Vast, é a Vast que está
descrita pela realidade.

**Dívida que nasce junto:** o caminho Vast vira código morto com enum de aparência viva
(`GpuProvider.VAST_AI`, `training/vast/`, `_dispatch_vast_ai`). É a mesma classe de armadilha que já nos
custou uma rodada inteira de confusão de nome. **Remover ou desativar duro, não deixar dormindo.**
⚠️ `gpu_provider` é coluna com valores gravados (migration 097) — renomear é migração de dados.
