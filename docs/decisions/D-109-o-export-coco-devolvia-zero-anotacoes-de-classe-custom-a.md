# D-109 · O export COCO devolvia ZERO anotações de classe custom — a Volta 0 teria saído vazia

**Seção:** Rodada RunPod 10/08 (PR #343 — renumerada de D-85..D-88 → D-106..D-109) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**10/08 · Claude (achado em execução) · ✅ PR #337**

O JOIN de categorias do export não desfazia o offset do namespace
(`frame_annotations.class_id = 100000 + yolo_classes.id`) — **toda anotação de classe custom de
tenant caía fora silenciosamente**. As 17 caixas do RVB nunca teriam entrado em dataset nenhum.
Corrigido junto com: split por **câmera+dia** para frames de NVR (antes: `frame:{id}` = split
aleatório por imagem, a métrica mentiria), exclusão de classes arquivadas e de frames
`curation_status='excluida'`, e `r2_weights_key` finalmente persistido na linhagem.
