# D-130 · A aba Classificar NUNCA conseguiu salvar — 400 permanente, não falha de rede

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **causa raiz das "14 aprovações não sincronizadas"**

`AnnotationService._validate_class` rejeita o batch INTEIRO com 400 se `class_name` ou `module_code`
vierem vazios. O `buildApprovalPayload` da aba Classificar montava só `{class_id, x_center, y_center,
width, height}`. O Estúdio, que funciona, sempre mandou os dois (`boxToPayload`, studioTypes.ts:94).

**Por isso as 599 anotações do RVB vieram todas do Estúdio e nenhuma da aba Classificar.**

O erro **nunca foi transitório** — nenhum retry resolveria, e o desenho de persistência (localStorage
antes do POST, replay no mount) estava certo o tempo todo: guardava fielmente um payload que o servidor
sempre ia recusar.

**Consertado em três pontos** (caixa nova, anotação preservada, desfazer) + **reparo das pendências já
gravadas** no localStorage antes de reenviar, para que o trabalho já feito pelo Vitor não se perca.

**Correções de honestidade do aviso:** o banner dizia "nada foi perdido" sem dizer por quê. Agora diz
**a causa real** e que o trabalho está guardado no navegador. Retry com recuo só para erro transitório —
4xx é permanente e some do banner com o motivo, em vez de girar em silêncio.

⚠️ **A hipótese "está em memória e recarregar perde" era falsa** — sempre esteve em `localStorage`.
