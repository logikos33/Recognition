# D-133 · Arquivar câmera: a autorização comparava tenant com usuário, e o `DELETE` é destrutivo

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente

**O erro relatado tinha causa exata:** `camera_service.delete_camera` fazia
`if str(camera["tenant_id"]) != str(user_id)` — dois identificadores de entidades diferentes.
Para qualquer não-admin isso é sempre verdadeiro, então **sempre negava**.

**Consertado:** compara tenant com tenant; cross-tenant responde **404, nunca 403** (C-01);
override por `is_admin` preservado como estava.

**O `DELETE` é destrutivo de verdade** — `cameras` é referenciada com `ON DELETE CASCADE` por
`alerts`, `camera_events`, `counting_sessions`, `demo_videos` e `operations`; e por `NO ACTION` em
`training_frames`, `model_deployments`, `model_drift_metrics`. Numa câmera com histórico ele trava por FK;
numa câmera sem frames ele passa e **leva os alertas e as operações junto, em silêncio.**

**Novo caminho:** `POST /api/cameras/<id>/archive` e `/restore` — `is_active=false`, reversível.
⛔ Zero `DELETE` executado nesta rodada.

🔴 **E o que importa de verdade:** fila de anotação **e** export do dataset passam a ignorar câmera
arquivada. Sem isso arquivar seria cosmético e o modelo continuaria aprendendo de câmera descartada.
Frame de upload/vídeo (sem `camera_id`) não é afetado.

**⏸️ Tirar o `DELETE` do ar fica adiado**, por decisão do Vitor — alcance próprio.
**Condição de reabertura:** quando existir tela de arquivamento em uso e nenhum consumidor do
`DELETE /api/cameras/<id>` for encontrado no monorepo.
