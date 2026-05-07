-- Migration 013: Atualiza classe YOLO do módulo de carregamento
-- Renomeia fuel_nozzle → forklift (empilhadeira), adequado para carga/descarga
UPDATE module_classes
   SET class_name   = 'forklift',
       display_name = 'Empilhadeira',
       dino_prompt  = 'forklift industrial vehicle loading dock'
 WHERE module_code = 'fueling' AND class_name = 'fuel_nozzle';
