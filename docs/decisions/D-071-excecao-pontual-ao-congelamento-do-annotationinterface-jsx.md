# D-071 · Exceção pontual ao congelamento do `AnnotationInterface.jsx` (PR #317)

**Seção:** Rodada 06/08 — pipeline de treino (varredura R2, coleta, bloqueadores da anotação) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**06/08 · Claude**

O cabeçalho "CONGELADO — nunca modificar" protege contra reescrita, não contra
conserto de perda silenciosa de dados. PR #317 fez **3 correções cirúrgicas**:
shape da resposta de criar classe (`data.class` inexistente → classe fake
`Date.now()` que quebrava o save), erro de save de anotação visível (era
`// Silencioso`), erro de load de anotações visível. O congelamento segue
valendo para reestruturação.
