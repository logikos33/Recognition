# D-143 · A propagação tem 100% de rejeição — e o motivo não é gravado, então NÃO se pode concluir nada sobre ela

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente (a decisão é sobre instrumentar, não sobre julgar a propagação)

| Propagação semeada (SAM + DINOv2), tenant RVB | |
|---|---|
| Frames com proposta gerada | **974** |
| Aprovadas | **0** |
| **Rejeitadas** | **974 (100%)** |
| Jobs | 8 completados, 5 falhados |

**E o motivo da rejeição não é gravado em lugar nenhum.**

Isto admite **três causas com tratamentos opostos**:
1. as propostas são ruins → melhorar ou desligar o motor
2. foi limpeza de fila em lote → o dado não diz nada sobre qualidade
3. rodou sobre o acervo misto (D-138) e produziu caixas sem sentido nos frames inteiros → o defeito é o
   acervo, não a propagação

**A decisão é explicitamente NÃO concluir qual é.** Instrumentar primeiro: ao rejeitar, três botões
(`caixa errada` / `classe errada` / `imagem imprestável`) + campo livre opcional.
**⛔ Não construir taxonomia de motivos agora** — refinar depois de 100 rejeições classificadas.

⚠️ Registrado como **dúvida reportada**, não como veredito sobre a propagação.
