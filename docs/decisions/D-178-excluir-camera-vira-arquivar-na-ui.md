# D-178 · Excluir câmera vira Arquivar na UI

**Data:** 2026-08-18 · **Status:** ✅ vigente

**O risco (issue #428).** `DELETE /cameras/<id>` apaga a linha e o CASCATA leva junto **frames,
anotações e detecções** da câmera. Isso é acervo de treinamento — trabalho humano de anotação que
não se recupera de backup nenhum, porque o que se perde é o julgamento de quem anotou. A UI oferecia
essa operação como um botão vermelho numa tabela, atrás de um "não pode ser desfeita" que era
literalmente verdade.

**Decisão.** A UI arquiva (`is_active=false`), nunca apaga. O `delete()` **sai da camada de serviço
do frontend** — não fica escondido atrás de um `if`, deixa de existir. A rota `DELETE` continua no
backend como operação administrativa explícita.

**Texto honesto.** A confirmação diz o que de fato acontece: *sai do reconhecimento e do export de
dataset; frames, anotações e detecções continuam no banco; dá para desarquivar.* Sem "removida",
sem "permanentemente".

**Câmera arquivada não some da lista.** `list_cameras` não filtra por `is_active`, então ela continua
visível com o botão **Desarquivar**. Sumir da tela seria trocar um susto por outro.

⚠️ **Backend já estava pronto** — `archive_camera`/`restore_camera` e `camera_repository.set_active()`
existiam desde a auditoria da aba de treinamento. Faltava só a UI parar de chamar o `DELETE`.
O teste que fixa isso afirma a ausência (`'delete' in cameraService === false`), não só a presença
do caminho novo: senão o `delete` volta na próxima rodada sem ninguém notar.

**Descartado:** manter Excluir atrás de confirmação mais dura (digitar o nome da câmera). Fricção não
é reversibilidade — o dado continuaria indo embora, só que mais devagar.
