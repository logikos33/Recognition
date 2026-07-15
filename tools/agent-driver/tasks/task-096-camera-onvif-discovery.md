---
title: "Plug-and-play: descoberta de câmeras por ONVIF/DHCP (sem IP hard-coded)"
pr_title: "feat(cameras): descoberta ONVIF/DHCP das câmeras no edge"
commit_message: "feat(cameras): auto-descoberta ONVIF das câmeras atrás do MikroTik"
eval: default
risk: security
depende_de: task-095
bloco: 7 (Portabilidade de rede)
---

# Task 096 — Descoberta ONVIF/DHCP

> **Status:** EM REVISÃO — implementado em `agent/task-096-camera-onvif-discovery` (PR para develop;
> STOP-for-review, risk:security). C-04: não existia nenhum código de descoberta ONVIF/WS-Discovery no
> monorepo (greenfield) — `onvif_recorder_client.py` (task-091) fala ONVIF Profile G com o gravador em host
> **já conhecido**, protocolo diferente de WS-Discovery (multicast UDP 239.255.255.250:3702), cujo propósito é
> achar dispositivos de IP desconhecido. Implementado em `services/edge-sync-agent/app/{onvif_discovery,
> discovery_api}.py`: scan WS-Discovery com socket UDP injetável, parsing defensivo por regex (mesma
> disciplina anti-XXE do onvif_recorder_client.py), timeout + cap de respostas (DoS), `RTSPUrlValidator`
> obrigatório antes de qualquer URL sugerida (rejeita IP de origem forjado/loopback/link-local/multicast).
> `GET /api/v1/edge/discovery/scan` reusa o trust-anchor RS256 da task-090 (novo escopo `discovery:read`),
> registrado no mesmo processo/porta da mini-API de evidência. Decisões completas em **ADR-0052**. **Retorna
> dispositivos crus, não associa automaticamente a câmeras cadastradas** — decisão de escopo documentada na
> ADR (associação depende de `cameras`/`ip_cameras` no cloud, fora do alcance de dados deste processo edge).
>
> **⚠️ Sem validação em rede/hardware real** — nenhuma chamada foi exercitada contra multicast real ou câmera
> física; toda cobertura é via socket/HTTP fake. `depende_de: task-095` no frontmatter (rede portátil, MikroTik
> físico) é sobre a validação em hardware, não sobre a implementação: o dono do projeto categorizou esta
> task-096 explicitamente como **"Bloco 7 (parte cloud)"** em `queue.txt`, separada das tasks de hardware —
> construída e testada isoladamente, validação em subnet real adiada para quando task-095 destravar
> (`tools/agent-driver/queue-hardware.txt`), mesmo padrão já usado nas tasks 090/091.

## Objetivo
Descobrir câmeras por ONVIF/DHCP no subnet isolado, sem depender de IP fixo — chave para a portabilidade.

## Escopo
- Scan ONVIF no subnet de câmera; associar às câmeras cadastradas; validar via RTSPUrlValidator antes do FFmpeg/DeepStream.

## Aceite
- [ ] Câmeras descobertas automaticamente no subnet; mapeadas ao cadastro; sem IP hard-coded.

## Checkpoint
- STOP-for-review.
