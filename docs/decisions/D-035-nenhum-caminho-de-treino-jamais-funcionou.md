# D-035 · Nenhum caminho de treino jamais funcionou

**Seção:** Adendos de 04/08 (pós-rodada #288–#292) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · constatação · 📌**

Consolidando os quatro achados: `LocalProvider` era `_simulate_training` · a Vast.ai é o código real e
**a única tentativa deu 404 em 12/07** · o fallback treinava no dataset público do Roboflow fingindo ser
o do tenant · o `dataset_version_id` não chegava ao job.

**O degrau "treinar" nunca executou com sucesso, por provedor nenhum.** Isso reordena o flywheel: a volta 1
não é "fiar o que existe", é **construir a peça**. Anotar antes de existir caminho de treino trava no
degrau seguinte.
