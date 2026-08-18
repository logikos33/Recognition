# D-152 · Consumidores dos dois endpoints — determinado

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente

| Endpoint | Consumidor | Veredito |
|---|---|---|
| `POST /api/training/models/<id>/activate` (sem gate) | Só `trainingService.ts:50`, e **nenhuma tela o chama** (o `useTraining` não é montado em lugar nenhum; `CameraModelAssignment` só usa `listModels`). O `qualityService` chama rota **diferente** (`/v1/quality/training/models/...`, por câmera) | **Pode sair** — esforço **P**. Remover o método morto de `trainingService.ts` e a rota |
| `DELETE /api/cameras/<id>` | **TEM consumidor vivo** — botão "Excluir" | ⛔ **Não tirar do ar** sem antes fazer o botão arquivar (D-151) |
