# Task 064 — Perfil de Recursos do Live View (memória alta no cloud)

**Status**: PENDING (custo de nuvem + estabilidade)
**Risk**: P1-ALTO (memória do tier API; risco de OOM/queda sob N câmeras)
**Branch**: fix/task-064-live-view-resource-footprint

## Contexto (reportado — 2026-07-06)

Uso de **memória alto** no `api-v3-desenvolvimento` com **1 câmera** (~400MB reportado). Precisa
medir e otimizar antes de escalar pra 28 câmeras (RVB). CPU aparentemente OK; foco em MEMÓRIA.

## Hipóteses (medir pra confirmar)

1. **Baseline do container**: gunicorn + gevent com N workers, cada um carregando o app → 200-400MB
   SEM câmera. Pode ser o grosso. (Medir baseline com 0 câmera.)
2. **Segmentos HLS em tmpfs (RAM)**: se `.ts` gravam em tmpfs e o `delete_segments`/janela deslizante
   não limpa, acumulam na MEMÓRIA e ela cresce. (Medir `du` do dir de segmentos ao longo do tempo.)
3. **FFmpeg órfão** (liga com task-062): stream não para ao trocar de página → FFmpeg + buffers vivos
   → memória sobe com o tempo.
4. **FFmpeg re-encode** (liga com task-061): mais memória/CPU que stream-copy.

## Diagnóstico (medir — Railway CLI / exec no container)

- Memória do serviço: **baseline (0 câmera)** vs **1 câmera** vs **N câmeras** vs **ao longo de 10 min**
  (detectar vazamento/crescimento).
- `ps`/`pgrep ffmpeg` no container: quantos FFmpeg vivos? Crescem ao navegar/abrir-fechar câmera?
- `du -sh` do diretório de segmentos HLS: fica limitado (janela) ou cresce? Está em tmpfs (RAM) ou disco?
- Nº de workers do gunicorn e memória por worker.

## Fixes (conforme o que a medição apontar)

- **Segmentos**: garantir janela deslizante limitada + delete real; se em tmpfs, **capar o tamanho**
  do tmpfs (evitar RAM ilimitada); ou gravar em disco efêmero em vez de RAM se a memória apertar.
- **FFmpeg**: stream-copy (task-061) reduz footprint; matar processo ao parar o stream (task-062);
  sem órfãos.
- **Gunicorn**: revisar nº de workers/threads pro tamanho do container (não superprovisionar); avaliar
  `--max-requests` pra reciclar workers e conter crescimento de memória.
- **Escala**: reforça task-060 — transcode fora do tier web (28 FFmpeg + segmentos num container API
  não escala em memória).

## Aceite

- Baseline, 1-câmera e N-câmeras medidos e documentados (docs/evidence/).
- Memória **estável** ao longo do tempo (sem crescimento com navegação/abrir-fechar) — sem vazamento.
- Segmentos HLS limitados (não acumulam em RAM); tmpfs capado ou em disco efêmero.
- Projeção de memória pra 28 câmeras dentro do limite do plano; se não couber, decisão registrada
  (mais réplica / edge / gateway — task-060).
- Suíte verde. PR develop. Gate humano pra staging.

## Referências

- task-059 (live view), task-060 (escala/gateway), task-061 (stream-copy/latência),
  task-062 (órfãos/lifecycle), ADR-0030 (transcode single-replica)
