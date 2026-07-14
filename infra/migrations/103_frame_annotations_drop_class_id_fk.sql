-- 103_frame_annotations_drop_class_id_fk.sql
-- Task 078 — remove a FK obsoleta frame_annotations.class_id -> yolo_classes(id).
--
-- EXCEÇÃO EXPLÍCITA a constitution.md C-02 (migrations só ADD COLUMN/CREATE
-- INDEX/CREATE TABLE) — autorizada em sessão registrada em
-- tools/agent-driver/tasks/task-079-frame-annotations-class-id-fk-relax.md.
-- Não remove a coluna class_id, não altera seu tipo, não altera NOT NULL —
-- apenas o relacionamento físico com a tabela errada.
--
-- Por quê: class_id hoje guarda o índice 0-based do MÓDULO (module_classes),
-- não o id SERIAL global de yolo_classes (tabela de "classes customizadas"
-- por usuário, sem relação com o índice do módulo). A FK bloqueia
-- estruturalmente class_id=0 para qualquer tenant (SERIAL começa em 1) e é
-- não-determinística para os demais índices (só "funciona" se algum
-- yolo_classes.id colidir por acaso com o índice enviado) — confirmado
-- empiricamente contra Postgres local migrado do zero (ver task-079.md).
--
-- A validação de que (module_code, class_id) é uma combinação real de
-- module_classes passa a ser feita em código de aplicação (task-077 Commit 2)
-- — não expressável como FK do Postgres hoje, pois module_classes não tem
-- UNIQUE(module_code, class_id) (só UNIQUE(module_code, class_name)).
--
-- yolo_classes NÃO é removida nem descontinuada — POST/PUT/DELETE /api/classes
-- continua funcionando; só deixa de ter relação com frame_annotations.
--
-- Idempotência: DROP CONSTRAINT IF EXISTS é no-op se já removida. Rodar 2x
-- não produz erro.

ALTER TABLE public.frame_annotations
    DROP CONSTRAINT IF EXISTS frame_annotations_class_id_fkey;
