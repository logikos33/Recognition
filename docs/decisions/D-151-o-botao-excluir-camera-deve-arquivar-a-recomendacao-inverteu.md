# D-151 · O botão "Excluir" câmera deve ARQUIVAR — a recomendação inverteu

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ⏸ proposta — ⛔ NÃO implementada

Achado: `DELETE /api/cameras/<id>` **não está esquecido** — está exposto ao usuário final em
`CamerasPage.tsx:108` (botão "Excluir" + `ConfirmDialog`) via `cameraService.ts:188`. E apaga em
**CASCADE** `alerts`, `camera_events`, `counting_sessions`, `demo_videos` e `operations`.

**Isso piora o quadro, não melhora:** o endpoint destrutivo é de uso corrente.

**Recomendação: o botão passa a chamar `POST /cameras/<id>/archive`** (já existe, veio no #392).

| Peça | Esforço |
|---|---|
| Trocar `cameraService.delete` por `archive` + copy do diálogo | **P** |
| Mostrar câmera arquivada na lista com selo + ação "Restaurar" | **P/M** |
| Manter `DELETE` só para admin, ou tirar do ar | **decisão do Vitor** |

⚠️ **A tela de triagem (`CameraTriagePage`) NÃO faz isso hoje** — ela triaga descoberta de câmera, não
ciclo de vida. Não há o que reaproveitar; é tela de câmeras mesmo.
