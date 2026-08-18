# D-155 · `gpu_cost.actual_usd` ficou NULL no TREINO 1 — por quê

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente

O `metrics` do job `10feb67b` traz `gpu_cost: {price_usd_h: 0.22, estimated_usd: 0.22, actual_usd: null}`.
O **estimado** é gravado no dispatch; o **real** dependeria de consultar o custo do pod **depois** de
morto, e esse passo não existe — o runner mata o pod e encerra.

É a **mesma lacuna** que produziu o órfão de US$ 21,54: o sistema sabe estimar e sabe matar, mas não
fecha a conta. `gpu_instance_ref` **É** gravado (`63armpimqkz3km` no TREINO 1), então a consulta pós-morte
é possível — só não é feita.

**No TREINO 2 o custo real será gravado**, consultando o pod pelo `gpu_instance_ref` após a morte.
