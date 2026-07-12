# Task 062 — Estabilidade/Ciclo de Vida do Live View (carregando infinito + trava ao navegar)

**Status**: PENDING (robustez — recomendado ANTES do go-live RVB)
**Risk**: P1-ALTO (user-facing; vazamento de recurso frontend + possível saturação da API)
**Branch**: fix/task-062-live-view-lifecycle

## Contexto (medido em teste real — 2026-07-06)

Com o live view funcionando (task-059), ao **trocar de página** no sistema a câmera "fica carregando"
e **às vezes trava/cai**. Sintoma clássico de player não destruído no unmount.

## Hipóteses (confirmar no diagnóstico)

### Frontend (mais provável)
- `hls.js` **não é destruído** no unmount do componente (falta `hls.destroy()` no cleanup do useEffect).
- O **poll do `.m3u8`** continua rodando após sair da página (setInterval/loop sem clear).
- **WebSocket** (`useMonitoringSocket`) não é fechado no unmount → reconnect storm.
- Resultado: múltiplas instâncias/loops acumulando → "carregando" infinito + trava a aba (memória).

### Backend (agravante — casa com ADR-0030)
- Cada câmera aberta sobe **1 FFmpeg no tier da API** (single-replica). Navegação rápida pode
  **empilhar** FFmpeg (start sem stop imediato do anterior; watchdog só mata após TTL de inatividade)
  → satura CPU/memória do container da API → lentidão/queda geral.

## Diagnóstico

1. Determinar o escopo da queda: **só o player** (vazamento frontend) vs **sistema todo/outros usuários**
   (saturação da API por FFmpeg empilhado).
2. Revisar o useEffect do CameraPlayer: tem cleanup com `hls.destroy()`, clear do poll e do WS?
3. Backend: quantos FFmpeg ficam vivos ao navegar entre páginas repetidamente? O stop é imediato ao
   sair, ou só via watchdog (30s)?

## Fixes

### Frontend
- Cleanup completo no unmount: `hls.destroy()`, `clearInterval/clearTimeout` do poll, fechar o WS,
  abortar fetches pendentes (AbortController).
- Idempotência: garantir 1 instância de player por câmera; não recriar por cima de uma viva.
- Ao sair da página, **sinalizar stop** do stream (ou deixar o TTL cuidar) — mas sem empilhar starts.

### Backend
- Endpoint/mecanismo pra **parar o stream imediatamente** quando o player desmonta (ou reduzir o TTL
  de inatividade), evitando FFmpeg órfão acumulando.
- Dedup Redis (já existe) tem que impedir 2 FFmpeg pra mesma câmera durante navegação rápida.

## Aceite

- Navegar entre páginas repetidamente NÃO deixa player/loop/WS órfão (verificar no DevTools:
  sem múltiplas conexões/timers acumulando; memória estável).
- Nº de FFmpeg no backend não cresce com navegação (1 por câmera ativa; zero após sair + TTL).
- Sem "carregando infinito" ao voltar pra câmera; sem trava de aba; sem queda da API.
- Suíte verde. PR develop. Gate humano pra staging.

## Referências

- task-059 (live view), task-060 (escala/gateway — FFmpeg fora do tier web), ADR-0030,
  `apps/frontend` (CameraPlayer, useMonitoringSocket), `docs/product/VMS_MONITORING_UX.md`
