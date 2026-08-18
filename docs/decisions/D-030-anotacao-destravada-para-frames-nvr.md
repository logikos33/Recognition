# D-030 · Anotação destravada para frames NVR

**Seção:** Contrato e jurídico · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · ✅ vigente**

A galeria mostrava os 679 frames NVR mas o clique só abria o anotador com `video_id` (NULL para NVR desde a
migration 094). Correção aditiva (PR #288): modo "frame direto" quando não há vídeo pai, sem quebrar o
caminho de frame-de-vídeo. Fiado também o `dataset_version_id` ponta a ponta (era placeholder `=job_id`).
Aceite (humano): abrir `/epi/training`, clicar num frame NVR, desenhar caixa, salvar, recarregar — persiste.
