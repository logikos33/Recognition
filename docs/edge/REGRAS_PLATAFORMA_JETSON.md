# Regras da Plataforma Jetson (Orin NX 16GB Super) — doc vivo

> **Como usar:** consultar ANTES de qualquer trabalho no box; ALIMENTAR depois com
> aprendizados novos. Box real: `ssh pandora@100.93.126.76` (Tailscale).
> Última atualização: 2026-07-18 (task-113 — soak co-residência RVB).

## 0. Hardware / SO
- NVIDIA **Jetson Orin NX 16GB Super**, JetPack 6 (L4T r36 / kernel `5.15.148-tegra`), aarch64.
- **Memória UNIFICADA 16GB** (15.6Gi visível) — CPU + GPU + NVMM dividem o mesmo pool.
  Toda RAM que Postgres/Redis/API consomem é RAM a menos para inferência.
- Disco: **NVMe 119GB** (`/dev/nvme0n1p1`, ~80GB livres em `/`).
- Power: `nvpmodel` já em **40W (modo 4)**. `jetson_clocks` exige sudo.

## 1. §REUSE — o que já existe no box (inventariar SEMPRE antes de construir)
- `~/jetson-experiments/` — workspace da campanha de escala. Contém:
  - `mediamtx` + `mediamtx.yml` (proxy RTSP, ADR-0009) — roda em tmux `mediamtx`.
  - `mm/pacer_mm.py` / `stress102/pacer_shard.py` — pacers que injetam .ts em `rtsp://127.0.0.1:8554/camN`.
  - `mm/app_mm_all_prod_*.txt` — **configs deepstream-app de PRODUÇÃO** dos 3 módulos
    (epi 16, park/counting 8, qaux 2, qmain 2×4MP) = CENARIO_RVB 28 cams. Sink `type=1` (fakesink, headless).
  - `campaign/sampler.py` — telemetria 2s (INA3221 power rails, GPU load, temps, fan) → `telemetry_campaign.jsonl`.
  - `campaign/recognition_load.py` — simulador de carga edge (POSTs + clipe evidência).
  - Engines TensorRT: `ppe_tiny_dyn_int8.engine` (**INT8 YOLOX — config vencedora**), `yolox_tiny_coco_dyn_fp16`, `rfdetr_nano_*`.
  - Parser YOLOX: `~/yolox-deepstream-parser/libnvdsparsebbox_yolox.so`.
- `~/recognition-edge-telemetry/` + user-service `edge-telemetry-collector.service` (tegrastats → JSONL).
- **Paths sysfs validados** (reusar no lugar de tegrastats parsing):
  - GPU load: `/sys/devices/platform/17000000.gpu/load` (÷10 = %).
  - GPU freq: `/sys/class/devfreq/17000000.gpu/cur_freq`.
  - Power rails INA3221: `/sys/class/hwmon/hwmon*` (name==`ina3221`), `in{i}_input`×`curr{i}_input`/1000 = mW. Label `VDD_IN` = total.
  - Temps: `/sys/devices/virtual/thermal/thermal_zone*/{type,temp}`.
  - Fan: `/sys/class/hwmon/hwmon0/pwm1`, `/sys/class/hwmon/hwmon2/rpm`.

## 2. Restrições de acesso (o que trava execução autônoma)
- **sudo EXIGE senha** (`sudo -n` falha; nem `sudo -l`). Bloqueia: apt install, jetson_clocks,
  nvpmodel, sysctl, swap em disco, systemd de **sistema**, reboot, docker-group, `chmod` socket.
  → Registrar como pendência do Vitor; NÃO travar a missão nisso.
- **Docker:** socket é root:docker e `pandora` NÃO está no grupo docker → `permission denied`.
  Não dá pra usar containers sem sudo. Use userspace (abaixo).
- **`/proc/pressure/*` (PSI) NÃO existe** neste kernel (sem `CONFIG_PSI`). Sem métrica de pressão de memória direta.
  Proxies: `MemAvailable`, `pswpin/pswpout` (delta de `/proc/vmstat`), `loadavg`, swap usado.
- **dmesg restrito** (`kernel.dmesg_restrict=1`) → sem leitura de OOM-kills do kernel sem sudo.
  Proxy de OOM: systemd `Result=oom-kill` + `NRestarts` + estado do serviço.

## 3. Padrões sudo-free que FUNCIONAM (validados task-113)
- **Postgres/Redis sem sudo:**
  - Redis: build do source (`make`, gcc presente) → `redis-server` userspace. ✓
  - Postgres: **micromamba** (binário estático único, sem sudo) + `-c conda-forge postgresql=16`.
    `pgserver`/`postgresql-wheel` do pip NÃO têm wheel aarch64 — não perca tempo.
- **Python 3.11 sem sudo:** sistema tem só 3.10; o backend usa `from enum import StrEnum` (3.11+).
  → env `micromamba create -n api -c conda-forge python=3.11` e `pip install -r requirements/api.txt`.
  Deps (flask/gevent/psycopg2/opencv-headless/numpy/cryptography) têm wheel aarch64 — instala em ~1-2min.
- **Budget de memória por serviço sem sudo:** cgroup v2 com controllers `memory pids` **delegados
  ao user slice** → `systemctl --user` aceita `MemoryHigh=/MemoryMax=` sem privilégio. ✓
- **Ordenação de OOM sem sudo:** `OOMScoreAdjust=` POSITIVO em unit `--user` (mais matável) não exige
  privilégio. Auxiliares (redis/pg/api/load) com adj alto (300–800), pipeline deepstream em 0 (default)
  → kernel mata auxiliar antes do pipeline. Negativo (proteger) exigiria CAP_SYS_RESOURCE (sudo).
- **Persistência/reboot sem sudo:** `Linger=yes` JÁ ativo para `pandora` → serviços `systemctl --user`
  com `WantedBy=default.target` sobrevivem a logout SSH E a reboot. Auto-restart via `Restart=always`.
- **tmux** sobrevive a disconnect SSH (server daemoniza) — bom para downloads/builds longos.

## 4. Armadilhas específicas encontradas
- **`pgvector` do conda-forge PUXA UPGRADE do Postgres 16→18** (landmine de restart/reboot!). Instalar
  `pgvector` no env `pg` fez o conda **atualizar o binário postgresql p/ 18.4**. O postmaster 16 já rodando
  seguiu servindo (não reiniciou), mascarando o problema por horas; no **restart/reboot** o binário 18 sobe
  contra data dir 16 → `FATAL: database files are incompatible with server ... version 18.4`. **Só aparece no
  restart, não em runtime.** Diagnóstico: `postgres -D <data>` manual mostra o FATAL. Fix: `micromamba remove
  pgvector` + `micromamba install postgresql=16.14` (pina a major; data preservado). Regra: **NUNCA co-instalar
  pacote que arraste upgrade de major do Postgres num env com data dir existente** — pinar a versão.
  Migration `036_pgvector_assistant.sql` (assistente de treino) fica sem pgvector — fora do caminho crítico RVB.
- `railway_start.py` (develop) aponta `--chdir` para `backend/` que **não existe** no monorepo
  (API real = `services/api/app`). Rodar gunicorn manualmente de `services/api` com `app:create_app()`.
- `deepstream-app` com 28 streams exige `ulimit -n 65535` (unit: `LimitNOFILE=65535`).
- Câmeras: API lê **`public.cameras`** (filtrado por `tenant_id`); `{schema}.cameras` é usado por
  subsistemas (quality/edge). Embarque precisa popular AMBAS para consistência.
- `tenants.deployment_mode` CHECK aceita só `cloud|edge|hybrid` — **"dual" = `hybrid`**.
- `tenants.schema_name` (não `tenant_schema`) é a coluna; login mapeia → claim JWT `tenant_schema`.

## 5. Config de produção CENARIO_RVB (28 cams, 3 módulos)
| Módulo | Cams | Engine | interval | batch |
|---|---|---|---|---|
| EPI/Segurança | 16 | `ppe_tiny_dyn_int8.engine` (INT8 YOLOX) | 4 | 8 |
| Estacionamento/Contagem (park) | 8 | `yolox_tiny_coco_dyn_fp16.engine` | 4 | 8 |
| Qualidade aux | 2 | PPE INT8 | 2 | 2 |
| Qualidade main | 2×4MP (2560×1440) | `rfdetr_nano_*` ROI | 4 | 2 |

Baseline medido: **3 módulos só → GPU ~68%, ~7.2GB RAM**; stack completa co-residente
(+Redis+PG+API+load) → **GPU ~68-72% em regime, ~7.8GB RAM, swap ~0**. Camada de dados/API
adiciona só **~400MB** (redis 31 + pg 163 + api 126 + prod/cons 60). Ver `SOAK_RVB_2026-07-18.md`.
