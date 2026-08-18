# D-038 · DINO+SAM roda no RunPod, sob demanda

**Seção:** Adendos de 04/08 (pós-rodada #288–#292) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Vitor (AskUserQuestion) · 🔄**

Descartadas: Railway (não tem GPU — roda em CPU, lento e caro; foi assim que virou "custo × qualidade
ruim" em maio) · Orin (compete com a inferência, que é o trabalho nº 1 do box, e propagação é trabalho
pesado em rajada).

**Ganho decisivo:** mesma conta e credencial do treino (D-33) ⇒ **um único suboperador para nomear no
contrato**, em vez de dois. E as duas coisas usam a mesma peça de dispatch, que já está no plano.
