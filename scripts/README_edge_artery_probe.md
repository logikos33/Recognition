# edge_artery_probe.py — prova da artéria edge→cloud (DEV)

> ⚠️ **Utilitário de diagnóstico, NÃO o agente de produção.** O agente real é
> `services/edge-sync-agent/` (placeholder — Fase 4). Este probe existe para provar que um
> device fala com a nuvem (enroll → heartbeat → `public.edge_heartbeats` → painel de health).
> Não deixar rodando como gambiarra permanente: quando a prova terminar, parar e remover.

## Por que existe

O diagnóstico do #217 mostrou o pandora **100% local** — nada chegava na nuvem. Não havia
cliente de enroll/heartbeat no repo (o `edge-sync-agent` é placeholder), então não havia
como provar a artéria. Este script é o menor cliente honesto que fecha esse laço.

## Contrato implementado (validado no código, C-04)

| Passo | Endpoint | Auth | Retorno |
|---|---|---|---|
| Enroll | `POST /api/v1/edge/enroll` | público (token one-time) | `201` `{data:{tenant_id, site_id, device_id, scopes}}` |
| Heartbeat | `POST /api/v1/edge/heartbeat` | `Bearer <JWT RS256 do device>` | `201` `{data:{id, received_at}}` |

Pontos que **não** batem com a doc antiga do agente:
- O enroll **não retorna JWT**. O device **auto-assina** (ADR-0019 S7) com a chave privada
  que ele mesmo gerou; o servidor verifica contra a pública guardada em `public.device_tokens`.
- As respostas usam o envelope `success()` → ler `body["data"]`, não a raiz.
- O JWT precisa das claims `{tenant_id, site_id, device_id, scopes, iat, exp}` e do escopo
  **`heartbeat:write`** — sem ele, `403`. Sem `aud`/`iss`; verificação é RS256 + `exp`.

## Uso

```bash
export EDGE_API_URL="https://api-v3-desenvolvimento.up.railway.app"   # DEV
export ENROLLMENT_TOKEN="<token one-time gerado pelo admin>"          # nunca commitar

python3 scripts/edge_artery_probe.py --once            # enroll + 1 heartbeat
python3 scripts/edge_artery_probe.py --loop            # heartbeat a cada 10s
python3 scripts/edge_artery_probe.py --loop --jetson   # no Orin: GPU real via tegrastats
python3 scripts/edge_artery_probe.py --once --sample   # rodada de validação da nuvem (Mac)
```

Deps: `pip3 install requests cryptography pyjwt psutil` (wheels existem para aarch64).

**Loop sustentado:** o health considera o device offline após **120s** sem heartbeat — para o
painel mostrar "online", use `--loop` (em `tmux` para a prova rápida, ou um
`edge-artery-probe.service` systemd se for coletar por horas).

## Honestidade da telemetria (regra, não detalhe)

| Campo | Fonte | Quando não há fonte |
|---|---|---|
| `cpu_pct`, `mem_pct`, `disk_pct` | `psutil` (real) | `null` |
| `gpu_pct`, `gpu_mem_pct`, `gpu_temp_c` | `tegrastats` com `--jetson` (**não** `nvidia-smi` no Orin) | `null` |
| `inference_fps`, `cameras_online/total`, `queue_depth`, `latency` | — pipeline não instrumentado (Fase 4 / task-112) | **sempre `null`** |

Nunca enviar número inventado: `null` significa "não instrumentado", `0` significaria
"medido e é zero". `--sample` marca o `last_error` deixando explícito que a rodada é de
validação da nuvem, não telemetria de device — para ninguém ler "28 câmeras a 22 FPS" que
não existem.

## Segurança

- A chave privada é gerada no host e **nunca sai dele** — só em memória, ou em arquivo
  `chmod 600` com `--key-file`. Nunca commitar.
- Token de enrollment e JWT **nunca** são logados (só status HTTP e prefixos de id).
- Guardrail: o probe **aborta** se `EDGE_API_URL` apontar para produção
  (`api-v3-production` / `interchange`).
- O `device_id` é único por tenant — reusar um já enrolado dá `409` (use outro ou revogue).

## Verificação do lado da nuvem

```sql
SELECT device_id, revoked, last_seen_at, enrolled_at FROM public.device_tokens WHERE tenant_id='<RVB>';
SELECT id, expires_at, used_at, used_by_device_id FROM public.enrollment_tokens WHERE site_id='<site_id>';
SELECT id, received_at, status, cpu_pct, inference_fps FROM public.edge_heartbeats
  WHERE tenant_id='<RVB>' ORDER BY received_at DESC LIMIT 5;
```

E como admin: `GET /api/v1/edge/sites/health` (`derived_status` != offline, `last_heartbeat_at`
recente) e `GET /api/v1/edge/overview` (`devices_online >= 1`).

## O que isto prova — e o que NÃO prova

**Prova:** endpoints de nuvem (enroll RS256, heartbeat), auth por chave pública, gravação em
`edge_heartbeats`, o caminho de leitura de observabilidade e — rodando no pandora — a **rede
edge→cloud**.

**Não prova:** o `edge-sync-agent` de produção (segue placeholder, Fase 4); telemetria por
câmera / FPS e drops por stream (task-112); nada do pipeline DeepStream. Conclusão correta é
"**artéria provada**", não "edge pronto".
