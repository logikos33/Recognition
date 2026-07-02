# ADR-0026 — FPS and Quality Configuration per Camera

## Status: Accepted (2026-07-01)

## Contexto

O inference-service processa todas as câmeras de um tenant à mesma taxa (padrão: 5 FPS,
configurável por variável de ambiente global). Isso é ineficiente:

- Câmeras em áreas de baixo movimento (estacionamento, depósito) não precisam de 5 FPS
- Câmeras em pontos críticos (entrada, linha de produção) podem precisar de 10 FPS
- Workers com GPU limitada precisam distribuir capacidade entre câmeras do tenant
- Presets de qualidade afetam o tamanho do substream HLS (ADR-0022) e o custo de
  armazenamento de frames

A configuração global por variável de ambiente impede otimização por câmera e não
expõe controle ao operador.

## Decisão

### Campo na tabela de câmeras

Adicionar `fps_target` e `quality_preset` à tabela `{schema}.cameras` via migration:

```sql
ALTER TABLE {schema}.cameras
    ADD COLUMN IF NOT EXISTS fps_target      SMALLINT NOT NULL DEFAULT 5
                                             CHECK (fps_target BETWEEN 1 AND 30),
    ADD COLUMN IF NOT EXISTS quality_preset  TEXT NOT NULL DEFAULT 'balanced'
                                             CHECK (quality_preset IN ('economy', 'balanced', 'quality'));
```

### Semântica dos presets

| Preset | Resolução inferência | Modelo | Uso típico |
|--------|---------------------|--------|------------|
| `economy` | 320×320 | yolov8n | Câmeras de baixo risco, GPU limitada |
| `balanced` | 640×640 | yolov8s | Padrão — maioria dos casos |
| `quality` | 1280×1280 | yolov8m | Câmeras críticas, GPU disponível |

O worker/inference-service lê `fps_target` e `quality_preset` ao iniciar cada
câmera e ajusta o loop de captura e o modelo carregado.

### Health-aware warning na UI

O frontend exibe um aviso visual ao salvar configurações de FPS/qualidade que
podem exceder a capacidade estimada do worker:

```
Regra de warning:
  capacidade_usada = sum(fps_target * peso_preset para todas câmeras ativas do tenant)
  peso: economy=1, balanced=2, quality=4

  Se capacidade_usada > WORKER_CAPACITY_THRESHOLD (default: 40 unidades):
    exibir: "Atenção: a configuração pode sobrecarregar o worker. 
             Considere reduzir FPS ou usar preset economy em algumas câmeras."
```

`WORKER_CAPACITY_THRESHOLD` é exposto como variável de ambiente do worker e
consultado via `GET /api/worker/capacity` (endpoint interno, sem autenticação de
tenant — apenas service-to-service).

### Endpoint de atualização

`PUT /api/cameras/{id}` já existente aceita os novos campos.
Validação no backend: `fps_target` ∈ [1, 30], `quality_preset` ∈ enum.

### UX

Na página de edição de câmera (`<Drawer>` — ADR-0023), nova seção "Performance":
- Slider para `fps_target` (1–30, step 1, default 5)
- Radio group para `quality_preset`
- Indicador de capacidade estimada (barra de progresso) atualizado em tempo real
  ao mudar os controles

## Consequências

- Operadores controlam o custo de inferência por câmera sem intervenção de infra.
- Worker precisa recarregar configuração de câmeras ao receber evento de atualização
  (via Redis `PUBLISH camera:config:updated:{camera_id}` após PUT).
- Risco: operador pode configurar todas as câmeras em `quality` + 30 FPS e travar o
  worker. Mitigação: warning na UI + hard cap no worker (ignora fps > 30, degrada
  preset se capacidade > 120% do threshold).
- Migration é não-destrutiva (`ADD COLUMN IF NOT EXISTS` com DEFAULT) — câmeras
  existentes recebem automaticamente `fps_target=5, quality_preset='balanced'`.
