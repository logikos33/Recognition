# task-050 — LPR (leitura de placa) no módulo de carga/descarga

**risk:low** (aditivo; novo analítico sobre classe já existente)
**modo:** AUTO

## Objetivo
Ler a placa do caminhão na baia e associar automaticamente à sessão de carga/descarga. Hoje o
módulo `fueling` já tem a classe `plate` detectada — falta o OCR da placa e o vínculo com a
sessão/evento.

## Por que (Camerite)
LPR é um dos analíticos centrais deles. No nosso módulo de carga/descarga encaixa direto:
identifica o veículo na baia sem digitação manual, fecha o ciclo "qual caminhão / quanto carregou".

## Escopo
### Backend / inferência
- **Verificar** o módulo `fueling` (`services/api/app/api/v1/fueling/routes.py`,
  `FUELING_CLASSES` inclui `plate`) e como os crops/frames chegam ao R2.
- Sobre o bbox `plate` já detectado, rodar OCR de placa (modelo leve / lib de LPR BR — placas
  Mercosul e antigas). Rodar no edge quando possível; fallback worker Celery.
- Persistir `plate_text` + confiança no evento/sessão de carga (verificar tabela de
  `counting_sessions` / alerts antes de criar campo).
- Endpoint para listar sessões com placa associada.

### Frontend
- Mostrar a placa lida no card da baia e na sessão de carga/descarga. Permitir correção manual
  (humano no loop alimenta o flywheel de qualidade já existente).

## Fora de escopo
- Validação da placa contra base de veículos autorizados (fase 2 — conferência).
- LPR como módulo de segurança genérico (foco aqui é carga/descarga).

## Critérios de aceite
- Placa lida e associada à sessão em staging (vídeo de teste).
- Correção manual persiste e fica disponível como feedback de treino.
- Confiança baixa → marca para revisão, não descarta.
- Testes: parsing de placa Mercosul + antiga; associação à sessão; isolamento por tenant.

## Migration
Aditiva se faltar campo: `ADD COLUMN IF NOT EXISTS plate_text TEXT` /
`plate_confidence REAL` na tabela de sessão/evento (padrão, backfill por tenant). Idempotente.
