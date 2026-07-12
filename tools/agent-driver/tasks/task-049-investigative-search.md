# task-049 — Busca investigativa / timeline de eventos

**risk:low** (consultas read-only sobre dados que já coletamos)
**modo:** AUTO

## Objetivo
Dar ao gestor uma busca investigativa sobre os eventos já gravados: filtrar por câmera, classe
(ex.: `no_helmet`, `plate`, `truck`), período e confiança, com timeline visual e link pro frame
no R2. "Me mostre todos os eventos de X entre 14h e 16h de ontem."

## Por que (Camerite)
A solução "Analítico e Investigativo" deles é justamente busca em gravação. Nós já temos `alerts`
+ frames no R2 — falta a camada de busca/timeline. Alto valor percebido, baixo custo (não cria
dado novo, só consulta).

## Escopo
### Backend (`services/api`)
- **Verificar** o schema de `alerts` (tenant_id, module_code, camera_id, class_name, confidence,
  created_at, frame ref). Reusar repositório/serviço existentes.
- Endpoint `GET /api/events/search` com filtros: `camera_id[]`, `class_name[]`, `module_code`,
  `from`, `to`, `min_confidence`, paginação. Sempre filtra por `tenant_id`. Zero SQL com f-string
  de input do usuário (params).
- Agregação para timeline: contagem por bucket de tempo (`GET /api/events/timeline`).
- Cada resultado devolve URL assinada/curta do frame no R2.

### Frontend
- Página "Investigação": filtros + timeline (densidade por hora) + lista de eventos com thumbnail
  e deep-link pro frame. Reusar `api.ts`.

## Fora de escopo
- Busca por similaridade facial / re-ID (depende de embeddings — fase 2).
- Exportação de clipe de vídeo (só frame por enquanto).

## Critérios de aceite
- Filtros combinados retornam resultados corretos e escopados por tenant.
- Timeline agrega por bucket sem N+1.
- Paginação estável; frames abrem via URL assinada.
- Testes: isolamento por tenant; filtros de período/classe; injeção (params, não f-string).

## Migration
Provável **nenhuma**. Se a busca exigir, criar só `CREATE INDEX IF NOT EXISTS` em
`alerts(tenant_id, module_code, created_at)` / `(camera_id, class_name)` para performance.
