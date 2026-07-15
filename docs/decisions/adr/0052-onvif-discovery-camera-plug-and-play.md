# ADR-0052 — Descoberta ONVIF/WS-Discovery: onde roda, formato de resultado, associação a câmeras cadastradas

**Status:** Aceito · **Data:** 2026-07-15 · **Autores:** Vitor Emanuel (Logikos) + Claude Code (task-096)
**Relaciona:** ADR-0020 (MikroTik/WireGuard), ADR-0050 (evidence trust-anchor RS256), ADR-0051 (cloud-only
trade-off de segurança de câmera)
**Depende de (hardware, não bloqueante para esta ADR):** task-095 (rede portátil, MikroTik físico) —
bloqueada em `tools/agent-driver/queue-hardware.txt`. O dono do projeto categorizou esta task-096 como "Bloco 7
(parte cloud)" na fila principal (`queue.txt`), separada das tasks de hardware: escopo é implementar e testar
tudo que não depende de subnet/hardware real, deixando a validação em rede física para quando o hardware
existir — mesmo padrão já aplicado nas tasks 090/091.

## Contexto

ADR-0020 estabelece o subnet de câmera fixo atrás do MikroTik como padrão de todo site cliente, e o objetivo de
"portabilidade de rede" (task-095) é o edge não quebrar quando muda de rede (bancada → cliente). Uma peça que
falta para isso funcionar sem operação manual: como o técnico (ou o próprio sistema) descobre quais câmeras
existem no subnet, sem digitar IP na mão — daí task-096, "descoberta ONVIF/DHCP".

### C-04 — o que já existia (investigado antes de construir)

Busca completa por qualquer código de descoberta ONVIF/WS-Discovery no monorepo (monolito `services/api` e
`services/edge-sync-agent`): **nada existia.** Greenfield.

O único código ONVIF que já existe é `services/edge-sync-agent/app/onvif_recorder_client.py` (task-091, porte
de `services/api/app/infrastructure/nvr/onvif_client.py`) — fala **ONVIF Profile G** (`GetSystemDateAndTime`,
`FindRecordings`/`GetRecordingSearchResults`, `GetReplayUri`) com o **gravador (NVR)**, cujo host já é conhecido
via `RECORDER_HOST`. Isso é um protocolo diferente do WS-Discovery (multicast UDP 239.255.255.250:3702,
`urn:schemas-xmlsoap-org:ws:2005:04:discovery`), cujo propósito é justamente encontrar dispositivos cujo IP
**não** é conhecido. Reaproveitamos a disciplina de segurança desse módulo (parsing defensivo por regex,
`RTSPUrlValidator` antes de qualquer URL de rede), não o código de protocolo em si.

`RTSPUrlValidator` já existe portado em `services/edge-sync-agent/app/rtsp_validator.py` (task-091) — reusado
aqui, terceira cópia não foi criada.

`probe_camera` (`services/api/app/api/v1/cameras/probe_handler.py`, monolito) já valida host/porta contra SSRF
(`_check_ip_ssrf`, `_resolve_and_pin`) antes de qualquer `ffprobe` — mesmo padrão de disciplina reaplicado aqui
para IPs vindos de uma resposta de rede não confiável (WS-Discovery), não copiado literalmente porque o
monolito não tem alcance de rede L2 até as câmeras do cliente (decisão 1, abaixo).

## Decisões

### 1. Onde o scan roda: `services/edge-sync-agent`, não o monolito

O scan WS-Discovery precisa de alcance multicast L2 até o subnet de câmera atrás do MikroTik. O monolito cloud
roda no Railway — nunca tem esse caminho de rede, mesma razão pela qual `RECORDER_HOST`/credenciais de gravador
já são config local ao edge (`recorder_factory.py`, task-091), não vêm do cloud. Implementado em
`services/edge-sync-agent/app/onvif_discovery.py`.

### 2. Protocolo: WS-Discovery UDP, testável com socket injetável

`discover_devices()` monta um probe SOAP mínimo (`urn:schemas-xmlsoap-org:ws:2005:04:discovery`, ação
`.../Probe`, escopado a `dn:NetworkVideoTransmitter`), envia para o grupo multicast, e coleta respostas
`ProbeMatch` até `timeout_seconds` (wall clock) OU `max_responses` (cap de datagramas), o que vier primeiro —
ambos os limites são independentes e obrigatórios (um sozinho não basta contra um subnet hostil: só timeout não
limita quantidade de trabalho por segundo de flood; só cap não limita quanto tempo se espera se a rede estiver
quieta).

`socket.socket` é injetável via `sock_factory` (mesmo estilo de `popen` injetável em `rtsp_clip_stream.py`,
task-091) — os testes usam um objeto fake com `sendto`/`recvfrom`/`settimeout`/`close`, nunca uma rede UDP real.

Parsing é **regex sobre o texto**, não `xml.etree`/DOM — mesma disciplina do `onvif_recorder_client.py`:
namespaces variam por fabricante (`wsd:`/`d:`/sem prefixo), e regex sobre leaf elements tolera isso sem match
exato de namespace. Efeito colateral desejado: **sidesteps XXE por construção** — nenhum parser DOM/SAX roda
sobre bytes vindos de um UDP não autenticado, então não existe superfície de DOCTYPE/ENTITY para desabilitar.
Confirmado que `onvif_recorder_client.py` já segue o mesmo padrão (não usa `xml.etree`), reusado aqui.

### 3. Formato de resultado (`DiscoveredDevice`) e como chega ao cloud/técnico

`DiscoveredDevice`: `source_ip` (IP de origem do datagrama UDP, conforme reportado pelo SO — mais difícil de
forjar de fora do path que o conteúdo do pacote), `xaddrs`/`types`/`scopes`/`endpoint_reference` (conteúdo do
pacote, potencialmente controlado por um atacante no subnet — surfaced só para exibição, nunca usado para
montar uma URL sem validação separada).

`discovery_api.py` expõe `GET /api/v1/edge/discovery/scan` — reusa o **mesmo mecanismo de auth RS256
trust-anchor da task-090** (`TrustAnchor`/`EvidenceScope`, ADR-0050), com um novo escopo `discovery:read`
adicionado ao enum existente em vez de um módulo de auth paralelo (ver docstring do enum em `evidence_auth.py`
para a análise completa dessa escolha — o mecanismo de verificação já era agnóstico de "evidência", só o nome
do enum carregava esse acoplamento). Acessível dos dois jeitos que o padrão task-090 já estabeleceu: LAN local
do site (ferramenta do técnico) OU cloud fazendo proxy pelo túnel WireGuard (ADR-0020), pelo mesmo código —
`main.py` registra o blueprint de descoberta no MESMO app Flask/porta da mini-API de evidência, não um segundo
processo.

**Decisão consciente de escopo: a API de descoberta retorna dispositivos crus, NÃO tenta associá-los a câmeras
já cadastradas.** A associação ("este IP já corresponde à câmera X do tenant") precisa ler `cameras`/
`ip_cameras` — tabelas do schema do tenant, que só existem no cloud. Este processo edge não tem (e não deveria
ganhar, por design de tenant isolation) acesso direto a esse banco. Construir um endpoint novo no cloud que
recebe um resultado de descoberta e casa contra `cameras.host`/`ip_cameras.host`/`ip` (um join trivial por
igualdade de string) é trabalho real e útil, mas **não foi construído nesta task** — não há evidência hoje de
que o fluxo do técnico precise disso automatizado versus o técnico olhar a lista descoberta e comparar
manualmente com o cadastro (mesma régua de contenção que a ADR-0051 aplicou para não construir um wizard de
onboarding sem evidência de necessidade). Quando esse endpoint for construído, o trabalho difícil (o scan em
rede real, com todas as defesas de parsing) já está pronto — o que falta é só o join.

### 4. `RTSPUrlValidator` antes de qualquer URL sugerida

`build_suggested_rtsp_url(source_ip, port=554)` monta `rtsp://{source_ip}:{port}/` e **valida via
`RTSPUrlValidator.validate()` antes de retornar** — nunca aceita host/porta de uma resposta de rede sem validar
(a resposta UDP pode ser forjada por qualquer dispositivo no subnet). Em caso de rejeição (IP de origem
loopback/link-local/multicast/reservado — cenário exatamente esperado de um pacote forjado), a função retorna
`None`, não a URL não validada — o chamador (`discovery_api.py`) DEVE tratar `None` como "não ofereça este
dispositivo para cadastro" (ADR-0017: sem fallback silencioso). Testado explicitamente contra os quatro casos
de IP de origem forjado (`test_suggested_rtsp_url_rejects_spoofed_source_ip`,
`services/edge-sync-agent/tests/test_onvif_discovery.py`).

Deliberadamente **não** tenta adivinhar o path RTSP específico do fabricante (`/cam/realmonitor?...` Dahua vs
`/Streaming/Channels/1` Hikvision) — WS-Discovery não informa fabricante/layout de canal; essa lógica já existe
em `services/api/app/api/v1/cameras/manufacturer_profiles.py` e é aplicada quando o operador confirma o
fabricante no cadastro. Esta função só prova "este host é seguro para apontar um client RTSP", não "este é o
path exato do stream".

## Security review (risk:security)

- **Parsing defensivo:** um datagrama malformado/truncado/não-UTF-8 é logado e pulado — nunca derruba o scan
  (`_parse_probe_matches` nunca propaga exceção; o loop em `discover_devices` também captura qualquer exceção
  de parsing por segurança extra). Testado com XML quebrado, bytes não-UTF-8, envelope vazio, e mensagem
  WS-Discovery de tipo errado (`Hello` em vez de `ProbeMatches`).
- **Sem parser DOM/XXE:** regex sobre texto, nunca `xml.etree`/`lxml`/SAX — não há superfície de
  DOCTYPE/ENTITY a desabilitar porque nenhum parser XML de verdade roda sobre o payload.
- **Timeout curto, nunca bloqueia indefinidamente:** `timeout_seconds` (default 3s) limita o wall-clock total;
  testado (`test_timeout_stops_scan_when_no_more_responses_arrive`).
- **Cap de respostas processadas (DoS):** `max_responses` (default 50) limita quantos datagramas são
  processados por scan, independente de quantos cheguem — testado explicitamente provando que o cap, não o
  timeout, encerra o scan (`test_max_responses_caps_datagrams_processed`).
- **`RTSPUrlValidator` obrigatório antes de qualquer URL sugerida** — decisão 4, acima.
- **`GetDeviceInformation` (enriquecimento opcional) também passa pelo `RTSPUrlValidator`** antes de qualquer
  requisição HTTP ao XAddr reportado no pacote (mesmo padrão de `onvif_recorder_client.py::_post_soap`) — um
  XAddr malicioso apontando para `http://127.0.0.1/...` é rejeitado antes de qualquer conexão ser aberta
  (`test_fetch_device_information_rejects_unsafe_xaddr`). Falha de um device específico (rede, resposta
  malformada, HTTP de erro) nunca derruba a descoberta dos demais — retorna `None`, não propaga.
- **Auth obrigatória em todo endpoint** — reuso do `TrustAnchor` RS256 (ADR-0050), sem endpoint aberto, mesma
  disciplina de `evidence_api.py`.
- **Nunca loga credenciais/conteúdo de pacote não confiável em nível INFO** — apenas contadores
  (`devices_found=%d`) e, em WARNING, mensagens de erro sem o payload cru.

## Sem hardware/rede real — nota importante

**Nenhuma chamada deste módulo foi exercitada contra tráfego multicast real ou uma câmera ONVIF física.** Não
há subnet isolado nem MikroTik físico disponíveis neste ambiente (task-095 está bloqueada por hardware,
`tools/agent-driver/queue-hardware.txt`). Toda a cobertura de teste usa um socket UDP fake
(`sock_factory` injetado) e um `http_client` fake para `GetDeviceInformation` — prova a lógica de
protocolo/parsing/defesa, não o comportamento real de uma câmera Intelbras/Hikvision respondendo WS-Discovery
em produção. Validação contra hardware real é explicitamente escopo de go-live (task-095/097), mesma disciplina
já documentada em `onvif_recorder_client.py`/`rtsp_clip_stream.py` (task-091).

## Não implementado nesta task (fora de escopo, documentado para não se perder)

- Endpoint cloud que recebe um resultado de descoberta e o associa automaticamente a `cameras`/`ip_cameras` já
  cadastradas do tenant (decisão 3, acima) — join trivial, mas não construído sem evidência de necessidade.
- Detecção de manufacturer/path de stream a partir do resultado WS-Discovery — decisão 4 explica por que isso
  fica com `manufacturer_profiles.py` no momento do cadastro confirmado pelo operador, não no scan.
- Loop periódico de descoberta / cache de resultados — `GET /scan` é síncrono, sob demanda, sem estado
  persistido entre chamadas.
- Suporte a DHCP discovery (mencionado no título da task original) — fora de escopo desta ADR: o subnet de
  câmera é fixo por design (ADR-0020/task-095), então descoberta por DHCP lease não se aplica ao caminho
  principal; WS-Discovery já resolve "achar câmera sem IP hard-coded" dentro desse subnet fixo.
