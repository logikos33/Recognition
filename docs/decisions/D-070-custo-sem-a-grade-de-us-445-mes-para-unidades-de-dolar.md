# D-070 · Custo sem a grade: de ~US$445/mês para unidades de dólar

**Seção:** Rodada 06/08 — pipeline de treino (varredura R2, coleta, bloqueadores da anotação) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**06/08 · Claude**

Premissas do estudo (`docs/ESTUDO_CUSTO_INFRA_E_HOSTZERA.md`): ~137 KB/s de
egress por câmera assistida, US$0,05/GB. A projeção de **US$445/mês** era
**25 câmeras × 24/7** (video wall permanente ≈ 8,9 TB/mês). No modelo do [[D-67]]
(câmera unitária sob demanda): 1 câmera × 2 h/dia ≈ 1 GB/dia ≈ **US$1,50/mês**;
mesmo 5 sessões-hora/dia ≈ US$7,40/mês. Clipes de evidência (~5 MB × dezenas/dia)
somam centavos. **Duas ordens de magnitude** — o problema de custo de egress
praticamente desaparece com a grade fora de escopo.
