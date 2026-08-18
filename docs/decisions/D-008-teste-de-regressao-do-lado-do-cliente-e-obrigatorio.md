# D-008 · Teste de regressão do lado do cliente é obrigatório

**Seção:** Processo e qualidade · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**03/08 · Claude → aceito · ✅ · PR #283**

O servidor tinha teste; o cliente não. O bug estava no cliente (`CameraPlayer.tsx:155-170` recarregando
URL morta). Essa família de bug já voltou uma vez.
