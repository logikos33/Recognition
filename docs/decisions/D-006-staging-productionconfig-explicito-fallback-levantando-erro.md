# D-006 · `"staging": ProductionConfig` explícito + fallback levantando erro

**Seção:** Processo e qualidade · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**03/08 · Claude → aceito · ✅ · PR #277**

`_configs.get("staging", ProductionConfig)` fazia o **DEV rodar como produção sem ninguém saber**.
Resolvido: `DevelopmentConfig` **herda** de `ProductionConfig` com 4 divergências explícitas — dissolve a
tensão entre ambiente honesto e fidelidade de produção.
⚠️ Ordem obrigatória: mapear explícito → corrigir a env → só então fazer o fallback falhar.
Inverter derruba o DEV.
