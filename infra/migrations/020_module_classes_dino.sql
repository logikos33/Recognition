-- 020_module_classes_dino.sql
-- Adiciona dino_prompt e is_active à tabela module_classes
-- para suporte a detecção DINO/SAM com prompts por classe.

DO $$ BEGIN
    ALTER TABLE module_classes ADD COLUMN dino_prompt VARCHAR(200);
EXCEPTION WHEN duplicate_column THEN NULL; END $$;

DO $$ BEGIN
    ALTER TABLE module_classes ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;

-- Seed prompts DINO em inglês para módulo EPI
-- AI_NOTE: DINO funciona melhor com prompts em inglês descritivos
UPDATE module_classes SET dino_prompt = 'safety helmet hard hat construction'
WHERE module_code = 'epi' AND class_name = 'helmet' AND dino_prompt IS NULL;

UPDATE module_classes SET dino_prompt = 'person head without helmet no hard hat'
WHERE module_code = 'epi' AND class_name = 'no_helmet' AND dino_prompt IS NULL;

UPDATE module_classes SET dino_prompt = 'safety vest high visibility reflective'
WHERE module_code = 'epi' AND class_name = 'vest' AND dino_prompt IS NULL;

UPDATE module_classes SET dino_prompt = 'person without safety vest no reflective'
WHERE module_code = 'epi' AND class_name = 'no_vest' AND dino_prompt IS NULL;

UPDATE module_classes SET dino_prompt = 'safety gloves protective hand gear'
WHERE module_code = 'epi' AND class_name = 'gloves' AND dino_prompt IS NULL;

UPDATE module_classes SET dino_prompt = 'bare hands without gloves'
WHERE module_code = 'epi' AND class_name = 'no_gloves' AND dino_prompt IS NULL;

UPDATE module_classes SET dino_prompt = 'safety glasses protective eyewear goggles'
WHERE module_code = 'epi' AND class_name = 'glasses' AND dino_prompt IS NULL;

UPDATE module_classes SET dino_prompt = 'face without safety glasses no eye protection'
WHERE module_code = 'epi' AND class_name = 'no_glasses' AND dino_prompt IS NULL;

-- Fueling module
UPDATE module_classes SET dino_prompt = 'truck tanker vehicle'
WHERE module_code = 'fueling' AND class_name = 'truck' AND dino_prompt IS NULL;

UPDATE module_classes SET dino_prompt = 'vehicle license plate'
WHERE module_code = 'fueling' AND class_name = 'plate' AND dino_prompt IS NULL;

UPDATE module_classes SET dino_prompt = 'fuel nozzle hose dispenser'
WHERE module_code = 'fueling' AND class_name = 'fuel_nozzle' AND dino_prompt IS NULL;
