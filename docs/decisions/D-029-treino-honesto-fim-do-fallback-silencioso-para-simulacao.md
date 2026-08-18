# D-029 · Treino honesto — fim do fallback silencioso para simulação

**Seção:** Contrato e jurídico · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · ✅ vigente · ADR-0060**

O treino caía em simulação (`_simulate_training`, métricas fabricadas) sem avisar quando faltava dataset ou
provider — terceira aparição da doença do fallback silencioso (ADR-0017). Corrigido (PR #292): simulação só
com `TRAINING_SIMULATION_ENABLED=true`; dataset ausente = erro alto; artefato simulado nasce marcado
(`metrics.simulated`, prefixo `SIMULATED_`, badge vermelho na tela); nuvem de terceiro gateada por
`training_third_party_cloud_enabled` (padrão OFF). **4º caminho encontrado** além dos três mapeados: o
fallback Vast→legado treinava no dataset público do Roboflow fingindo ser do tenant — eliminado.
