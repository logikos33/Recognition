-- 130_operations_template_id.sql
-- F5-LEVE "Cenário e Operações" — pedido B3 ao backend.
--
-- B3: template_id — string curta do template do editor (epi/restrita/linha/tempo/
-- aproximacao, conforme docs/design/handoff-f5/Cenário e Operações.dc.html, aba
-- Editor) que originou a regra, para o frontend reabri-la no mesmo assistente de
-- 3 passos. Sem CHECK: o catálogo de templates vive no desenho/frontend, não no
-- banco — travar aqui obrigaria migration toda vez que ganhar um template novo.
--
-- B1 (pausar/retomar) e B10 (último disparo) NÃO precisam de migration:
--   - B1: `status` (migration 038) já aceita 'inactive' e o motor
--     (OperationsEngine / OperationRepository.list_all_active) já filtra
--     `status <> 'inactive'` da avaliação — faltava só a rota (ver commit de lógica).
--   - B10: `operation_results` (migration 039) já guarda cada avaliação com
--     `condition_satisfied`, e já tem índice (operation_id, evaluated_at DESC)
--     — o repository usa esse índice via LEFT JOIN LATERAL, sem coluna nova
--     nem N+1 (ver commit de lógica).

ALTER TABLE operations ADD COLUMN IF NOT EXISTS template_id VARCHAR(40);
