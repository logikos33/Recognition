# ADR-0045 — Evidência recorder-first (supersede ADR-0028 cloud-first)

**Status:** Aceito · **Data:** 2026-07-14 · **Autores:** Vitor Emanuel (Logikos)
**Supersede:** ADR-0028 (cloud-first evidence) · **Relaciona:** ADR-0033, ADR-0034, ADR-0040 (VST)

## Contexto
O cliente já possui um **gravador/NVR** no site com todas as evidências. Empurrar toda evidência pro R2 gasta
nuvem à toa; os 128GB do Jetson não são destino de armazenamento. O que importa: o cliente **no local** acessa a
evidência direto; **remoto**, baixa sob demanda.

## Decisão
- **Fonte primária de evidência = o gravador no site** (acessível por ONVIF/RTSP na LAN). O VST (JPS) indexa a
  timeline; o cliente local consulta direto, sem R2.
- **Acesso remoto** = download **sob demanda** via túnel WireGuard (nuvem → edge → gravador) por um **mini-API
  local** no edge.
- **R2 = upload seletivo e diferido**, só do que alimenta o **flywheel de dataset da Logikos** — não a cada evento.
- 128GB = SO+app+engines+buffer transitório; nunca storage.

## Consequências
- Mini-API local no edge (task-090) + índice ONVIF do gravador (task-091) + upload seletivo pro R2 (task-092).
- ADR-0028 marcado Superseded.
