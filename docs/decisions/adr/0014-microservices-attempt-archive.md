# ADR-0014: Archive da Primeira Tentativa de Microsserviços

## Status
Aceito

## Data
2026-05-27

## Contexto

A branch `painel-adm` (commit `a24fe5f`, 2026-04-16) é um savepoint do projeto
imediatamente antes do módulo Quality ser implementado. Representa a **primeira
tentativa de arquitetura de microsserviços** da plataforma Recognition.

### Linha do tempo

| Data | Evento |
|------|--------|
| ~fev/2026 | Desenvolvimento dos microsserviços originais (`camera-gateway`, `ws-gateway`, `auth-service`, `training-service`, `scheduler-service`, `pre-annotation-service`, `inference-service`) |
| 2026-04-16 | Savepoint `painel-adm` criado (commit a24fe5f) — "pre-quality-module implementation checkpoint" |
| abr–mai/2026 | Módulo Quality implementado; funcionalidades dos microsserviços absorvidas pelo monolito `api-v3` |
| 2026-05-08 | Commits f547609 e 8dfeae9 — remoção explícita dos microsserviços de staging |
| 2026-05-27 | Investigação Pre-4 confirma remoção intencional; ADR-0011 corrigido |

### Por que a tentativa foi descontinuada

O monolito `api-v3` absorveu as responsabilidades porque:
- Microsserviços adicionavam complexidade operacional sem clientes em produção
- Railway cobra por serviço; manter 6+ serviços separados aumentava custo
- Celery Beat no worker substituiu o `scheduler-service`
- Auth, WebSocket e streaming foram integrados ao api-v3 nativo

**Não foi uma falha de implementação** — o código dos microsserviços foi
escrito e funcionava. Foi uma decisão de simplificação antes do primeiro go-live.

### Valor do código arquivado

Avaliação por serviço (detalhes em `docs/decisions/painel-adm-code-value-assessment.md`):

| Serviço | LOC | Disposição para Fase 3 | Justificativa |
|---------|-----|------------------------|---------------|
| `camera-gateway` | ~544 | **PORTAR** | Pipeline FFmpeg RTSP→HLS único; frame_publisher via Redis |
| `training-service` | ~535 | **PORTAR** | UltralyticsHubClient customizado; job orchestration complexo |
| `ws-gateway` | ~271 | **REFERÊNCIA** | Padrão psubscribe→socketio documentado; api-v3 tem equivalente |
| `scheduler-service` | ~213 | **REFERÊNCIA** | Lógica check_cameras_health() via Redis TTL útil |
| `auth-service` | — | **DESCARTAR** | api-v3 tem auth nativo completo; sem multi-tenant |
| `pre-annotation-service` | — | **DESCARTAR** | DINO+SAM nunca usado em produção |
| `inference-service` | ~572 | **IGNORAR** | SHA idêntico ao em staging — mesma versão |

## Decisão

**Preservar o savepoint como tag permanente `archive/microservices-attempt-1`.**

```bash
git tag archive/microservices-attempt-1 refs/heads/painel-adm
git push origin archive/microservices-attempt-1
```

A tag serve como:
1. Evidência histórica da arquitetura original
2. Referência de implementação para Fase 3 (serviços marcados PORTAR/REFERÊNCIA)
3. Ponto de partida para análise de migração de funcionalidades

### Acesso ao código arquivado

```bash
# Ver conteúdo de um serviço
git show archive/microservices-attempt-1:camera-gateway/

# Checkout temporário para leitura
git checkout -b scratch/review-camera-gateway archive/microservices-attempt-1
ls camera-gateway/
git checkout -  # voltar ao branch anterior
```

### Uso na Fase 3

Para cada serviço marcado **PORTAR**:
- Criar `services/<nome>/` do zero na estrutura nova
- Usar código da tag como referência — adaptar, não copiar literalmente
- Serviço novo recebe multi-tenancy, logging padronizado, healthcheck Railway

Para serviços marcados **REFERÊNCIA**:
- Ler o código para entender padrões e lógica de negócio
- Implementar a funcionalidade equivalente onde já existe (ex: api-v3)

## Alternativas Consideradas

### A: Deletar branch e código após remoção de staging
- Descartada: código de camera-gateway e training-service tem valor real
  para a Fase 3; reescrever do zero descarta aprendizados

### B: Manter branch painel-adm ativa em origin
- Descartada: branch implica desenvolvimento ativo; tag é mais semântica
  para código arquivado e não mantido

### C: Criar repositório separado de archive
- Desnecessária: a tag resolve com overhead zero; repositório extra
  adiciona complexidade de acesso

## Consequências

### Positivas
- Código histórico acessível sem poluir o branch principal
- Fase 3 tem base concreta para camera-gateway e training-service
- Decisão arquitetural registrada formalmente

### Negativas
- Código da tag pode ficar stale — não será atualizado
- Devs precisam saber da tag para consultar o arquivo

## Referências

- `docs/decisions/adr/0011-painel-adm-nested-git.md` — como remover o gitlink
- `docs/decisions/painel-adm-branch-investigation.md` — investigação Pre-4
- `docs/decisions/painel-adm-code-value-assessment.md` — análise de valor por serviço
- `docs/decisions/inference-migration-feasibility.md` — análise do inference-service
