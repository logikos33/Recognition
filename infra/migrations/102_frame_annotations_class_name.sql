-- 102_frame_annotations_class_name.sql
-- Task 077 — persiste o nome/módulo da classe escolhida na própria anotação.
--
-- Por quê: frame_annotations.class_id é FK legada para yolo_classes(id) (tabela
-- global, sem relação com o índice 0-based do módulo que o frontend envia —
-- ver task-077). A leitura hoje reconstrói o nome via JOIN em yolo_classes,
-- produzindo nomes trocados. Este passo apenas adiciona as colunas; a lógica
-- de gravação/leitura muda em commit separado.
--
-- Escopo: public (frame_annotations não é tabela por-tenant — confirmado via
-- grep: nenhuma query no módulo de anotação usa set_search_path/schema por
-- tenant; isolamento hoje é via user_id/tenant_id em colunas, não schema).
--
-- Idempotência: ADD COLUMN IF NOT EXISTS é no-op se já existir. Rodar 2x não
-- produz erro.

ALTER TABLE public.frame_annotations
    ADD COLUMN IF NOT EXISTS class_name VARCHAR(100);

ALTER TABLE public.frame_annotations
    ADD COLUMN IF NOT EXISTS module_code VARCHAR(50);
