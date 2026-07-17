# Stack co-residente no edge (Jetson Orin NX 16GB) — hardening de memória + go-live

> **task-113** — provar que o box **não trava** com a stack COMPLETA co-residente
> (Redis + Postgres + API Recognition + edge-sync + coletor + 3 módulos de inferência
> + túnel + dashboard) rodando por horas, com budget de memória que garante folga
> para a inferência. **Companion:** `docs/edge/REGRAS_PLATAFORMA_JETSON.md` (§consultar
> sempre) e o relatório de soak mais recente em `docs/edge/SOAK_RVB_*.md`.
>
> ⚠️ **Estes artefatos são para RODAR NO BOX (`pandora`), com sudo.** Foram
> preparados fora do box (a sessão de nuvem **não alcança** o Tailscale `100.93.126.76`).
> Antes de aplicar: ler o REGRAS (documento vivo) e **medir** cada alavanca (§telemetria).

## Por que memory-hardening é o ponto central (o medo)

O Jetson tem **memória unificada**: os 16 GB são **divididos entre CPU e GPU**. Postgres,
Redis e API comendo RAM = **pressão direta na inferência** (surfaces NVMM, engines TensorRT,
working set do DeepStream). O stress dos 3 módulos sozinho já usou **~8,0 GB** (CENARIO_RVB
§3). Sem controle, um vazamento no Postgres ou um pico de COW no Redis pode fazer o **kernel
OOM-killer escolher o pipeline DeepStream** — travamento silencioso pós-cutover. Este bundle
**delimita cada serviço auxiliar** e **protege o pipeline** para que isso nunca aconteça.

## Budget de memória (16.384 MB unificados)

| Zona | Alvo | Mecanismo |
|---|---|---|
| **Inferência + NVMM** (4× DeepStream + engines + surfaces) | **~11 GB livres** | protegida (OOMScoreAdjust −900), sem cap |
| OS + GNOME (`:1`) + kernel | ~1,8 GB | — |
| **Stack auxiliar (teto duro somado)** | **≤ ~3,2 GB** | `MemoryMax` por serviço (cgroup v2) |

Working set medido da inferência = 8,0 GB → **~3 GB de folga** sobre os 11 GB reservados.

### Cap por serviço (systemd, cgroup v2)

| Serviço | `MemoryHigh` (soft throttle) | `MemoryMax` (kill no cgroup) | `OOMScoreAdjust` |
|---|---|---|---|
| deepstream (4 grupos) | — | — | **−900** (último a morrer) |
| postgresql | 384 M | 640 M | −700 |
| redis | 512 M | 640 M | −500 |
| recognition-api | 896 M | 1280 M | −100 |
| edge-sync-agent | 256 M | 384 M | +100 |
| edge-telemetry-collector | 96 M | 160 M | +500 |
| soak-sampler (só no soak) | 96 M | 160 M | +700 (mais sacrificável) |

**Soma dos `MemoryMax` = 3.264 MB ≈ 3,2 GB.** `MemoryHigh` freia o serviço (reclaim
agressivo) **antes** do teto; `MemoryMax` mata **dentro do cgroup** (não o box inteiro);
`OOMScoreAdjust` orienta o OOM-killer **global** como rede final — o pipeline é o último
alvo, os auxiliares morrem primeiro. Referências: systemd cgroup v2 memory pressure;
Red Hat cgroups-v2. Valores = **working set medido + folga**; re-medir no soak e ajustar.

## Ordem de aplicação (push-button)

```bash
# No box (pandora), com sudo. Ler o REGRAS antes. Cada passo é idempotente.
sudo bash deployments/edge/swap-nvme.sh            # 1. swap 16G em NVMe + swappiness baixo
sudo cp deployments/edge/sysctl-edge.conf /etc/sysctl.d/99-recognition-edge.conf
sudo sysctl --system                                # 2. pressão de VM
sudo bash deployments/edge/perf-jetson.sh          # 3. nvpmodel/jetson_clocks/fan (SUDO — ver nota)
sudo bash deployments/edge/install_edge_stack.sh   # 4. instala units + configs redis/pg (edita paths)
sudo systemctl daemon-reload
# 5. subir a stack (ordem de dependência resolvida pelos [Unit] Requires/After)
sudo systemctl enable --now recognition-postgres recognition-redis \
     recognition-api recognition-edge-sync recognition-edge-telemetry
# 6. subir os 3 módulos (via os runners mm/ reaproveitados — ver CENARIO_RVB)
sudo systemctl enable --now recognition-deepstream@epi \
     recognition-deepstream@parking recognition-deepstream@quality-aux \
     recognition-deepstream@quality-main
```

> **Reuse-first (§6 do REGRAS):** os `ExecStart` do DeepStream apontam para os runners
> **já existentes** no box (`~/jetson-experiments/mm/run_mm.sh` e cia). Este bundle **não
> recria** engines/parsers/pacers — só embrulha o que já roda em unidades systemd com
> `Restart=always`, budget e proteção de OOM. Editar os paths em `install_edge_stack.sh`
> conforme o inventário real do box.

## Nota sudo (pendências que exigem o Vitor / acesso ao box)

`swap-nvme.sh`, `sysctl`, `perf-jetson.sh` (nvpmodel/jetson_clocks/fan) e a instalação de
units systemd **exigem sudo no box**. A sessão de nuvem **não tem acesso ao box** (Tailscale
fora de alcance). Estão prontos para aplicação hands-on. `psi=1` no cmdline do kernel (se PSI
não estiver ativo) exige editar `extlinux.conf` + reboot — ver `sysctl-edge.conf`.

## Arquivos

| Arquivo | Papel |
|---|---|
| `swap-nvme.sh` | desliga zram grande, cria swap 16G em NVMe, `swappiness=10`, persiste `/etc/fstab` |
| `sysctl-edge.conf` | `vm.swappiness`, `vfs_cache_pressure`, `min_free_kbytes`, dirty ratios |
| `perf-jetson.sh` | `nvpmodel -m 0` (MAXN Super 40W) + `jetson_clocks` + fan (SUDO — pendência) |
| `redis-edge.conf` | `maxmemory 384mb` + `allkeys-lru` + persistência OFF (sem pico de COW) |
| `postgresql-edge.conf` | `shared_buffers` pequeno, `max_connections=30`, tuning de edge (não-servidor) |
| `systemd/*.service` | units da stack co-residente com budget + `OOMScoreAdjust` + `Restart=always` |
| `install_edge_stack.sh` | copia units/configs, aplica includes, valida paths (idempotente) |
