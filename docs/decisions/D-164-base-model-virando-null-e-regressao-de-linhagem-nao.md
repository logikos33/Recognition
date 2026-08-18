# D-164 · `base_model` virando NULL é regressão de LINHAGEM, não metadado cosmético

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente

`POST /api/training/jobs` não aceita `base_model`: mandei `"base"`, o job `4c782cdf` gravou `null`.
No TREINO 1 (`10feb67b`) ficava `base`.

🔴 **O gate de licença depende de saber qual variante rodou.** RF-DETR **base** é Apache 2.0; **XL** e
**2XL** são PML (ADR-0044, `license_gate.assert_rfdetr_variant_allowed`). Linhagem `null` **não prova
nada numa auditoria** — e o gate deixa passar justamente porque variante ausente cai no default
`RFDETRBase()`, que é permitido. Funciona; não é auditável.

**Consertado:** o handler passa a aceitar e persistir `base_model`, com default explícito `"base"`.
O job `4c782cdf` foi preenchido retroativamente, porque se sabe qual variante rodou.
