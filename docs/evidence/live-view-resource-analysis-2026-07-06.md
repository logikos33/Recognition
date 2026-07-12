# Live View — Análise de Recursos e Latência (tasks 061/062/064)

**Data**: 2026-07-06  
**Ambiente medido**: DEV local (análise de código — sem acesso exec ao container Railway)  
**Branch**: `fix/task-061-hls-latency-tuning` (PR #117)

---

## 1. Diagnóstico (análise de código)

### FFmpeg — codec antes/depois

| | Antes | Depois (task-061) |
|---|---|---|
| Codec | `libx264` (re-encode) | `copy` (stream-copy) |
| CPU estimada | ~0.5 vCPU/câmera | ~0.03–0.05 vCPU/câmera |
| Env override | — | `HLS_VIDEO_CODEC=libx264` para câmeras H.265 |

**Causa raiz confirmada**: a versão pré-task-061 em `local_stream_manager.py` usava `libx264 -preset ultrafast`. Com 1 câmera isso consumia ~0.5 vCPU sustentado — confirmado pelo user.

### Stream source (stream principal vs substream)

- **Não confirmado por exec** — sem acesso ao container Railway não foi possível capturar o comando FFmpeg ativo
- A URL RTSP é construída por `CameraService.build_stream_url()` a partir dos campos da câmera
- **Suspeita**: câmeras Intelbras/Hikvision padrão podem estar puxando o stream principal (1080p) em vez do substream (704×576)
- **Ação pendente**: adicionar campo `subtype` ao cadastro de câmera e forçar `?channel=1&subtype=1` na URL (ver task-060/gateway)

### HLS — segmentos e playlist

| Parâmetro | Antes | Depois (task-061) |
|---|---|---|
| `hls_time` | 2s (local_stream_manager) / 2s (gateway cmd) | **1s** |
| `hls_list_size` | 6 (default FFmpeg) | **3** |
| `hls_flags` | — | `delete_segments+omit_endlist` |
| `#EXTINF` esperado | ~2s | **~1s** |
| Latência estimada (local/edge) | ~6-12s | **~2-4s** |
| Latência antes (cloud+túnel) | ~40s (medido) | N/A (túnel adiciona ~5-10s) |

### Segmentos HLS — disco vs RAM

- Gravados em `/tmp/hls/{camera_id}/` no container Railway
- Railway usa **disco efêmero** (não tmpfs) → segmentos não ocupam RAM
- Com `hls_list_size=3` + `delete_segments`: janela fixa de 3 segmentos × ~1s = **3s de disco por câmera**
- Estimativa de disco: 3 segmentos × ~50KB = **~150KB/câmera** (negligível)

### Redis TTL — watchdog lifecycle (task-062)

| | Antes | Depois (task-062) |
|---|---|---|
| TTL do `epi:stream:{id}:active` em `start_stream` | **3600s** (1h) | **30s** (`HLS_INACTIVITY_TIMEOUT`) |
| `serve_hls` renova o TTL? | **Não** | **Sim** (a cada segmento servido) |
| Tempo até watchdog matar stream ocioso | **~3600s** | **~30-35s** |

**Efeito**: ao navegar para outra tela, o FFmpeg agora é morto em ~30s (em vez de ficar vivo 1h consumindo CPU e memória).

### Gunicorn — workers e memória (task-064)

| Parâmetro | Antes | Depois |
|---|---|---|
| Worker class | `GeventWebSocketWorker` (1 worker) | idem |
| `--max-requests` | **ausente** (worker vive para sempre) | **500 req** |
| `--max-requests-jitter` | — | **50** |
| `--rtbufsize` (FFmpeg) | ausente | **4M** |

`--max-requests 500` faz o worker se reciclar após 500 requests, liberando memória acumulada pelo GC do Python. Jitter de 50 evita restart simultâneo de todos os workers.

---

## 2. Projeção de recursos — 28 câmeras (RVB)

### CPU

| Cenário | CPU estimada |
|---|---|
| 1 câmera, stream-copy | ~0.05 vCPU |
| 28 câmeras, stream-copy | **~1.4 vCPU** |
| 1 câmera, re-encode (libx264) | ~0.5 vCPU |
| 28 câmeras, re-encode | **~14 vCPU** ⚠️ inviável no tier API |

→ Stream-copy é **obrigatório** para 28 câmeras no tier API.

### Memória

| Fonte | Estimativa |
|---|---|
| Baseline gunicorn + app (0 câmeras) | ~200-300 MB |
| Por câmera (FFmpeg copy + buffers) | ~15-25 MB |
| 28 câmeras | **~620-1000 MB** |
| Limite tier Hobby Railway | ~512 MB |
| Limite tier Pro Railway | ~2 GB |

→ 28 câmeras requer **Pro tier** ou **task-060** (gateway dedicado fora do tier API).

### FFmpeg por câmera

- 1 processo por câmera (singleton LocalStreamManager)
- Watchdog mata processos ociosos em 30s → sem acúmulo de órfãos
- Sem acesso exec → FFmpeg count não medido diretamente

---

## 3. Pendências de acesso (DEFERRED)

- [ ] **Exec no container**: medir RSS por câmera com `ps aux | grep ffmpeg` e `cat /proc/meminfo`
- [ ] **Confirmar substream**: capturar a URL RTSP gerada e verificar se usa `subtype=1`
- [ ] **`#EXTINF` real**: baixar o `.m3u8` em produção e medir a duração dos segmentos
- [ ] **Latência end-to-end**: medir com câmera real (local/edge, sem túnel)

---

## 4. Estado do PR

**PR #117** — `fix/task-061-hls-latency-tuning` → `develop`  
- Commits: `1076ad9` (task-061 HLS latency) + `ab6a914` (task-062/064 lifecycle + recursos)
- 17 testes passando, ruff limpo
- **Gate humano**: merge PR #117 → develop para deploy Railway DEV
