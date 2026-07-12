# ADR-0030 — Transcode RTSP→HLS no tier da API: solução DEV/single-replica, não de escala

**Data:** 2026-07-05  
**Status:** ACEITO (decisão consciente — limitação documentada)  
**Autores:** Vitor Emanuel / Logikos  
**Referências:** task-059, task-060, ADR-0028 (evidência cloud-first), ADR-0020 (edge WireGuard)

---

## Contexto

O live view de câmeras exige transcode RTSP→HLS: o browser não fala RTSP; a UI consome um
`stream.m3u8` + segmentos `.ts`. O serviço `camera-gateway` (previsto na arquitetura AGENTS.md)
**não existe neste repositório**. Sem ele, `_is_gateway_online()` sempre retorna `False` e o
fallback Celery (`start_hls_stream.delay()`) despacha o FFmpeg para o container de inferência,
que escreve `/tmp/hls/{camera_id}/` no seu próprio filesystem — invisível para o container da API
que serve o `stream.m3u8` → **404 em produção e DEV**.

### Diagnóstico (teste de campo — 2026-07-05)

Câmera Intelbras (Dahua OEM) real, exposta via túnel TCP (pinggy) ao ambiente DEV do Railway:

- Cadastro: **OK** (onboarding wizard + INSERT bem-sucedido)
- Live view: **404** repetitivo no `GET /api/cameras/{id}/stream/stream.m3u8`
- Causa: isolamento de filesystem cross-container (API vs inference)

---

## Decisão

Implementar `LocalStreamManager` — singleton que roda FFmpeg como `subprocess.Popen` **dentro do
processo da API** (não via Celery). Os segmentos HLS são escritos em `/tmp/hls/{camera_id}/` no
próprio container da API, que é também o que serve o endpoint — sem cruzamento de container.

### Guard-rails obrigatórios (task-059)

| Guard-rail | Implementação |
|------------|---------------|
| RTSPUrlValidator antes do Popen | `LocalStreamManager.start()` chama `RTSPUrlValidator.validate()` antes de qualquer `Popen` |
| stderr surfaced | Thread daemon lê stderr não-bloqueante; `status()` expõe `stderr_tail` |
| Cleanup ao parar | `stop()` encerra FFmpeg + `shutil.rmtree /tmp/hls/{camera_id}/` |
| Cleanup por inatividade | Watchdog daemon verifica key Redis `epi:stream:{id}:active`; stop + rmtree se expirou |
| Storage limitado | `hls_list_size ≥ 6` + `hls_flags delete_segments+omit_endlist` (janela deslizante ~12s) |
| atexit cleanup | `_shutdown_all()` registrado em `atexit` — limpa todos os streams no shutdown |
| UUID validation | `camera_id` validado como UUID antes de montar `/tmp/hls/{camera_id}/` (path traversal) |
| args como lista | `subprocess.Popen(cmd, shell=False)` — sem injeção de shell |

### Separação de storage (CRÍTICO)

```
live view (efêmero)          evidência de infração (persistente)
─────────────────────────    ──────────────────────────────────
/tmp/hls/{camera_id}/*.ts    Cloudflare R2 (ADR-0028)
descartado em segundos       retenção configurável (ex: 30 dias)
NUNCA vai para R2            NUNCA fica em /tmp
```

---

## Consequências

### ✅ Positivas

- Elimina o 404 cross-container no ambiente DEV e qualquer ambiente **single-replica**.
- Zero infraestrutura adicional: FFmpeg já está presente na imagem da API (nixpacks.toml).
- Feedback de erro imediato: stderr do FFmpeg exposto em `GET /api/cameras/{id}/stream/status`.
- Cleanup automático: disco não acumula segmentos orfãos.

### ⚠️ Limitações — decisão consciente

**Esta solução NÃO funciona com 2+ réplicas da API.**

Com múltiplas instâncias (horizontal scaling), a réplica que processa `GET .../stream/stream.m3u8`
pode não ser a mesma que iniciou o FFmpeg via `start_stream`. Como `/tmp/hls/` é local por container,
a réplica sem o processo FFmpeg não encontra o arquivo → **o mesmo 404 cross-container ressurge,
agora entre réplicas**.

Adicionalmente, rodar transcode no tier HTTP compete com o atendimento de requisições: N câmeras = N
processos FFmpeg no mesmo container que serve a API. Escalabilidade horizontal fica inviável.

### 🔜 Arquitetura de produção — task-060 (PENDING)

| Opção | Descrição |
|-------|-----------|
| `camera-gateway` dedicado | Serviço separado de transcode; API redireciona/proxya para instância correta (afinidade câmera→gateway) ou usa storage compartilhado para os segmentos |
| Transcode no edge (Jetson) | No site do cliente, o edge decodifica RTSP e expõe HLS via túnel (ADR-0020 MikroTik/WireGuard) — nuvem não transcoda nada (modelo RVB) |
| Híbrido | Edge quando há edge no site; gateway na nuvem para câmeras diretamente conectadas à nuvem |

task-060 deve implementar o caminho escolhido e **remover o `LocalStreamManager`** do tier da API
(ou mantê-lo apenas como fallback explicitamente documentado para ambientes de desenvolvimento).

---

## Alternativas rejeitadas

| Alternativa | Por que rejeitada |
|-------------|-------------------|
| Manter fallback Celery | Worker escreve em container diferente da API → mesmo 404 |
| HLS em R2 (upload de segmentos) | Latência inaceitável para live view; custo de egresso; complexidade |
| Volume compartilhado Railway | Railway não oferece volumes compartilhados entre serviços sem configuração adicional |
| Aceitar 404 e documentar | Não aceitável — live view é funcionalidade core do produto |

---

## Decisão de registro para task-060

Antes de habilitar múltiplas réplicas da API **ou** de ter > 5 câmeras simultâneas em produção,
task-060 deve estar concluída. O risco de reintroduzir o 404 cross-réplica é **P0-CRÍTICO** e
esta ADR serve como gate explícito para esse milestone.
