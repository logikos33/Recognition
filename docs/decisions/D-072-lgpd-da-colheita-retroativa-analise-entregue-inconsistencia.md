# D-072 · LGPD da colheita retroativa: análise entregue + inconsistência RunPod×Vast.ai no contrato

**Seção:** Rodada 06/08 — pipeline de treino (varredura R2, coleta, bloqueadores da anotação) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**06/08 · Claude → decisão do Vitor**

Análise em `docs/negocio/ANALISE_LGPD_COLHEITA_RETROATIVA.md` (base legal
candidata: legítimo interesse com LIA documentado; minimização já embutida no
pipeline; tag de sessão/origem ANTES de colher para expurgo em lote; minuta de
aviso aos trabalhadores). **Decisão é do Vitor com a assessoria.**
Achado colateral que trava a cláusula de suboperador: o dicionário do contrato
nomeia **RunPod** (linhas 73/105/138) e o adendo D-33 (04/08) idem, mas o código
aponta **Vast.ai** (`constants.py::GpuProvider.VAST_AI`) — que o próprio registro
descreve como difícil de nomear em contrato. **Confirmar o provedor real antes
de assinar.**
