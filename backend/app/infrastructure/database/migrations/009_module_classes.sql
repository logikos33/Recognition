-- 009_module_classes.sql
-- Classes YOLO por módulo

CREATE TABLE IF NOT EXISTS module_classes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_code VARCHAR(50) NOT NULL,
    class_id INTEGER NOT NULL,
    class_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(100),
    icon VARCHAR(50),
    is_violation BOOLEAN DEFAULT FALSE,
    color VARCHAR(20),

    UNIQUE(module_code, class_name)
);

CREATE INDEX IF NOT EXISTS idx_module_classes_code ON module_classes(module_code);

-- Classes do módulo EPI
INSERT INTO module_classes (module_code, class_id, class_name, display_name, icon, is_violation, color) VALUES
('epi', 0, 'helmet',      'Capacete',    'hard-hat',       false, '#22c55e'),
('epi', 1, 'no_helmet',   'Sem Capacete','alert-triangle', true,  '#ef4444'),
('epi', 2, 'vest',        'Colete',      'shield',         false, '#22c55e'),
('epi', 3, 'no_vest',     'Sem Colete',  'alert-triangle', true,  '#ef4444'),
('epi', 4, 'gloves',      'Luvas',       'hand',           false, '#22c55e'),
('epi', 5, 'no_gloves',   'Sem Luvas',   'alert-triangle', true,  '#ef4444'),
('epi', 6, 'glasses',     'Óculos',      'eye',            false, '#22c55e'),
('epi', 7, 'no_glasses',  'Sem Óculos',  'alert-triangle', true,  '#ef4444')
ON CONFLICT (module_code, class_name) DO NOTHING;

-- Classes do módulo Fueling (placeholder)
INSERT INTO module_classes (module_code, class_id, class_name, display_name, icon, is_violation, color) VALUES
('fueling', 0, 'truck',        'Caminhão',         'truck',       false, '#3b82f6'),
('fueling', 1, 'plate',        'Placa',            'credit-card', false, '#3b82f6'),
('fueling', 2, 'fuel_nozzle',  'Bico Combustível', 'fuel',        false, '#3b82f6'),
('fueling', 3, 'product_box',  'Caixa Produto',    'box',         false, '#3b82f6'),
('fueling', 4, 'pallet',       'Pallet',           'layers',      false, '#3b82f6')
ON CONFLICT (module_code, class_name) DO NOTHING;
