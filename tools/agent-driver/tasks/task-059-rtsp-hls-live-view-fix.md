# Task 059 — Fix: Live View RTSP→HLS (404 no dev) + storage efêmero

**Status**: IN PROGRESS (1ª versão implementada — LocalStreamManager; falta hardening)
**Risk**: P1-ALTO (user-facing; toca streaming/transcode e disco)
**Branch**: fix/task-059-rtsp-hls-live-view

## Contexto (achado em teste real — 2026-07-05)

Teste de campo com câmera Intelbras (Dahua OEM) real, exposta via túnel TCP (pinggy) pro ambiente
DEV da nuvem:

- Onboarding **funcionou**: "Verificar" alcançou a câmera pelo túnel e a câmera **salvou** (INSERT OK —
  o antigo erro `column tenant_id does not exist` NÃO reapareceu; considerar aquele bug resolvido,
  mas confirmar cadastrando outra câmera).
- **Live view falha**: console dispara repetidamente
  `GET /api/cameras/{id}/stream/stream.m3u8 → 404` para TODAS as câmeras (3 UUIDs distintos).

Diagnóstico preliminar: navegador não toca RTSP; a UI espera um **HLS** (`stream.m3u8` + segmentos)
que **nunca é gerado**. O processo que transcoda RTSP→HLS (camera-gateway / worker com ffmpeg) não
está produzindo o arquivo no ambiente dev (serviço não deployado/ligado, endpoint on-demand não
disparado, ou ffmpeg falha ao abrir o RTSP).

## Objetivo

Fazer a visualização ao vivo funcionar de ponta a ponta (RTSP → HLS → player no browser) no ambiente
dev, com o transcode **efêmero e limitado** (sem acumular disco).

## Diagnóstico (obrigatório antes do fix)

1. Localizar o handler de `GET /api/cameras/{id}/stream/stream.m3u8` em `services/api` — quem deveria
   gerar o HLS? É sob demanda (endpoint `/stream/start` dispara ffmpeg) ou serviço contínuo
   (camera-gateway)? Mapear o fluxo completo.
2. Conferir se o serviço de streaming/transcode está **deployado e rodando no ambiente dev** (o dev foi
   duplicado — pode faltar esse serviço). Checar logs Railway (`api-v3-desenvolvimento` + gateway).
3. Se o ffmpeg roda: confirmar que abre o RTSP com `-rtsp_transport tcp` (câmera Intelbras/Dahua,
   `/cam/realmonitor?channel=1&subtype=1`; fallback `subtype=0` se não houver substream). Logar erro
   de conexão se houver.
4. Verificar **onde** os segmentos HLS são gravados e servidos, e se o path do `.m3u8` bate com a rota
   que a UI busca (causa direta do 404).

## Correção

- Garantir o transcode RTSP→HLS funcionando (subir/ligar o serviço no dev, ou wire do endpoint
  on-demand, ou corrigir o path de escrita/leitura do HLS).
- Player no browser (hls.js ou nativo) consumindo o `.m3u8` — live view carrega (200 + segmentos).

## Requisito de armazenamento (INEGOCIÁVEL — evitar vazamento de disco)

- **Janela deslizante limitada**: `hls_list_size` ~6–10 + `hls_flags delete_segments` (mantém só os
  últimos ~30–60s; apaga os antigos). Live view **não pode** acumular arquivos.
- Gravar segmentos em **tmpfs / disco efêmero**, **NUNCA no R2**. HLS ao vivo é scratch descartável.
- **Parar o transcode e limpar os segmentos** quando não há espectador (timeout de inatividade).
- Casa com o "reserved-space guard" do edge (ADR-0027) e protege o disco da Railway no cloud.
- **Separação clara**: live view (efêmero, tmpfs) ≠ **evidência de infração** (foto/clipe → R2 com
  retenção, ex. 30 dias RVB). Não misturar os dois caminhos de storage.

## Causa raiz (confirmada — 2026-07-05)

`camera-gateway` não existe neste repo → `_is_gateway_online()` sempre `False` → fallback usava
`start_hls_stream.delay()` (Celery) → FFmpeg rodava no container **inference**, escrevendo
`/tmp/hls/{camera_id}/` **lá** → `serve_hls` lê `/tmp/hls/` no container da **API** (vazio) → **404**.
Isolamento de filesystem cross-container.

**Fix 1ª versão:** `LocalStreamManager` (singleton) roda FFmpeg como subprocess **no próprio container
da API** → HLS escrito e servido pelo mesmo container. Elimina o 404. **PORÉM precisa dos guard-rails
abaixo antes do merge** (senão vira dívida perigosa).

## Hardening obrigatório (guard-rails do review — 2026-07-05)

1. **FFmpeg na imagem da API:** confirmar o binário `ffmpeg` no Dockerfile da API (a API não instala o
   stack pesado por padrão). **Capturar stderr do FFmpeg** e expor em status/health — proibido falhar
   em silêncio (senão `start` diz "starting" e o `.m3u8` fica 404 sem pista).
2. **Storage efêmero + cleanup (crítico):** `hls_list_size` ~6–10 + `hls_flags delete_segments`;
   segmentos em **tmpfs**; **matar o FFmpeg + limpar** ao fechar o player / timeout de inatividade.
   Sem isso, N câmeras = N FFmpeg escrevendo `/tmp` pra sempre → **enche o disco do tier web e derruba
   a API inteira**. Testar que o diretório fica LIMITADO ao longo do tempo.
3. **Segurança do subprocess:** validar a RTSP com `RTSPUrlValidator` **antes** do FFmpeg; args como
   **lista** (nunca `shell=True`) — evita injeção de comando no tier web.
4. **Flag de escala (ADR-0030):** o singleton-por-container só funciona com **1 réplica da API**. Com
   2+ réplicas, o `serve_hls` da réplica B não acha os segmentos da réplica A → **o mesmo 404 volta
   entre réplicas**, e o transcode carrega o tier HTTP. Registrar em **ADR-0030** que isto é
   **solução de DEV/single-replica, não de escala** (arquitetura de prod = task-060). Guardar como
   decisão consciente.
5. **Validação real (não parar no 200):** ver o **vídeo renderizar** no browser; `/tmp` **limitado**
   por alguns minutos; **fechar player → FFmpeg morre** e limpa. Túnel pinggy expira ~60min e muda
   host:porta — manter o túnel no ar e a câmera salva com o host:porta atual durante o teste.

## Gap confirmado no teste E2E (2026-07-05) — gatilho do transcode ausente

Após o hardening, o live view no dev **ainda dá 404**. Diagnóstico no DevTools/Network:
- `GET .../stream/stream.m3u8` → **404** em loop (hls.js: `onManifestLoading → handleNetworkError`).
- Filtro `start` na aba Network → **0 requisições** (com "Preserve log" ligado). Ou seja: o frontend
  **nunca chama `POST /stream/start`** → o `LocalStreamManager` nunca sobe o FFmpeg → o `.m3u8` nunca
  é gerado → 404 permanente.

O hardening arrumou o *motor* (FFmpeg, cleanup, segurança); **falta o gatilho** que liga o motor.

### Fix (GR-6 — gatilho do transcode)

- **Lazy-start no backend (preferido):** no `serve_hls` (GET do `.m3u8`), se não há stream ativo pra
  a câmera, **disparar `LocalStreamManager.start()` on-demand** e responder um status de "iniciando"
  (ex.: 404/425 com `Retry-After`) até os segmentos existirem; renovar o TTL de atividade a cada GET
  (integra com o watchdog do GR-2). Robusto: funciona mesmo se o frontend não chamar start.
- **Frontend (complementar):** o componente de live view faz `POST /stream/start` ao abrir a câmera e
  faz **poll** do `.m3u8` até 200 (com backoff), em vez de martelar 404. Mensagem "conectando…" na UI.
- **Regressão:** teste que abrir a câmera → o transcode dispara sozinho (lazy-start) → `.m3u8` vira 200
  sem nenhum POST manual. E teste de que o GET renova o TTL (não morre com espectador ativo).

## Aceite

- Abrir uma câmera no dev → vídeo ao vivo carrega (`200` no `.m3u8` + segmentos servindo), sem 404.
- Sob observação por N minutos, o diretório de segmentos permanece **limitado** (janela deslizante),
  não cresce indefinidamente.
- Ao fechar o player, o transcode para e os segmentos são limpos (verificar via log/disco).
- Suíte verde (ruff + pytest cov≥60 + tsc). PR pra `develop`. Revisão humana (P1).

## Achado relacionado (registrar em task-046 — onboarding wizard)

- O campo **"Endereço IP"** do wizard valida só **IPv4 literal** e rejeita **hostname/DDNS**
  (bloqueou o hostname do túnel; teve que resolver pra IP na mão). Câmera atrás de DDNS/hostname/túnel
  não passa. Melhoria: aceitar hostname além de IP no passo de conexão.

## Promoção (GATE HUMANO — não pular)

Ordem: `develop` → (validar a-e no dev) → **GATE HUMANO** → `staging` → (PR) → `main`.

Só promover develop→staging **depois** que, no dev:
- [ ] `.m3u8` sai de 404 → 200 **sem ação manual** (lazy-start GR-6 funcionando).
- [ ] Vídeo **renderiza** no browser.
- [ ] Segmentos ficam **limitados** (janela deslizante) e **somem** ao fechar o player (cleanup GR-2).
- [ ] Dedup Redis OK (1 FFmpeg por câmera mesmo com multi-worker).
- [ ] Suíte verde (ruff + pytest cov≥60 + tsc) e smoke test 200.

Enquanto qualquer item acima falhar, **fica no dev** — não sobe pra staging/main.

## Referências

- `docs/product/VMS_MONITORING_UX.md` (live monitoring)
- `docs/decisions/adr/0027` (evidência cloud-first + reserved-space guard)
- Teste de campo 2026-07-05 (câmera Intelbras real via túnel pinggy → dev)
