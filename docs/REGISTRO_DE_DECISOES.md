# Registro de Decisões — Recognition

**Criado em:** 2026-08-04 · **Dono:** Vitor Emanuel (Logikos)

## Para que serve e como se usa

Este arquivo existe porque **informação estava se perdendo entre rodadas**. Decisões eram tomadas em
conversa, viravam parágrafo dentro de um prompt, e três rodadas depois ninguém lembrava o que tinha sido
decidido nem por quê.

**Regras:**

1. **Append-only.** Nunca edite nem apague uma entrada anterior.
2. **Mudou de ideia?** Acrescente uma entrada nova e marque a anterior como `↩ substituída por D-NN`.
   O erro fica registrado — é ele que impede repetir.
3. **Toda decisão entra aqui**, inclusive as pequenas. Se coube num prompt, cabe aqui.
4. **Decisão de arquitetura com alternativas e consequências vira ADR** (`docs/decisions/adr/`).
   Este registro é o índice do que foi decidido; o ADR é o porquê longo.

**Status:** `✅ vigente` · `🔄 em execução` · `⏸ adiada` · `↩ substituída` · `❌ revertida`

---

## Índice rápido

| # | Decisão | Data | Status |
|---|---|---|---|
| D-01 | Não migrar de infraestrutura agora — Railway mantida | 02/08 | ✅ |
| D-02 | Corrigir o desperdício antes de medir qualquer custo | 02/08 | 🔄 |
| D-03 | Super admin vê o cliente por **impersonação**, não por visão cross-tenant | 03/08 | ✅ |
| D-04 | Câmeras: cadastro manual agora + fatia mínima da ADR-0058 | 03/08 | ✅ |
| D-05 | Ordem de merge #277→#278→#280→#279→#281 | 03/08 | ✅ |
| D-06 | `"staging": ProductionConfig` explícito + fallback levantando erro | 03/08 | ✅ |
| D-07 | Guarda de CI contra colisão de numeração de migration | 03/08 | ✅ |
| D-08 | Teste de regressão do lado do cliente é obrigatório | 03/08 | ✅ |
| D-09 | Sondagem de gravador: ONVIF primeiro, do Orin, anti-lockout estrito | 03/08 | ✅ |
| D-10 | Capacidade só vale medida **sob carga real**, sem extrapolação | 03/08 | 🔄 |
| D-11 | Os 2 gravadores extras e as ~21 câmeras: **fora de escopo** | 04/08 | ✅ |
| D-12 | Flywheel: portão humano antes de construir ferramenta | 03/08 | ✅ |
| D-13 | Anotação com ferramenta própria; **SaaS de terceiro proibido** | 03/08 | ✅ |
| D-14 | Deploy do celery-worker no DEV: fazer | 04/08 | ✅ (D-26) |
| D-15 | Treino não pode mentir — simulação nunca por fallback | 04/08 | ✅ (D-29) |
| D-16 | **O provedor de GPU é RunPod, não Vast.ai** | 04/08 | ↩ D-31 |
| D-17 | Câmeras entram com nome provisório; renomeadas pela imagem | 04/08 | 🔄 |
| D-18 | Senha não circula — cadastro pela impersonação do superadmin | 04/08 | 🔄 |
| D-19 | Pré-anotação: levantar, não ligar | 04/08 | 🔄 |
| D-20 | Nenhuma câmera nova entra com alerta ligado | 03/08 | ✅ |
| D-21 | Contrato: anexo de escopo de câmeras + cláusula de ampliação | 04/08 | ✅ |
| D-22 | Contrato: seção de acesso da Logikos às imagens | 04/08 | ✅ |
| D-23 | ADR-0059 (vídeo local-first, sessão única): Proposta, sem aceite | 02/08 | ⏸ |
| D-24 | Rate limit atual (300/min por IP) **inviabiliza 8 câmeras** — corrigir antes de subir | 04/08 | ✅ (D-27) |
| D-25 | Log duplicado por requisição: manter um só | 04/08 | ✅ (D-28) |
| D-26 | celery-worker deployado no DEV — desbloqueia treino/dataset/extração | 04/08 | ✅ |
| D-27 | Rate limit em buckets dedicados (OPTIONS, vídeo, API geral); auth intocado | 04/08 | ✅ |
| D-28 | Log de acesso em uma linha (7 campos) + severidade por stream | 04/08 | ✅ |
| D-29 | Treino honesto: simulação e nuvem de terceiro exigem opt-in explícito | 04/08 | ✅ |
| D-30 | Anotação destravada para frames NVR sem vídeo pai | 04/08 | ✅ |
| D-31 | Provedor de GPU do modelo de visão é Vast.ai (código); RunPod é outro sistema (LLM) | 04/08 | ✅ |
| D-32 | ProxyFix/limiter: chave por-IP é o edge da conexão, não o cliente real — follow-up | 04/08 | ⏸ |

---

## Infraestrutura e custo

### D-01 · Não migrar de infraestrutura agora — Railway mantida
**02/08 · Vitor · ✅ vigente**

Estudo de Hostzera e alternativas arquivado em `docs/ESTUDO_CUSTO_INFRA_E_HOSTZERA.md`.
Motivo: o driver de custo é **egress**, não memória (~8,9 TB/mês projetados com 25 câmeras ≈ US$ 445).
Migrar infraestrutura agora compete com entregar para o cliente.
**Retomar quando:** o desperdício estiver corrigido (D-02) e o egress de 1 câmera estiver medido.

### D-02 · Corrigir o desperdício antes de medir custo
**02/08 · Vitor · 🔄 em execução**

Watchdog derrubando o stream, loop de FFmpeg condenado, 425 repedidos, abas duplicando download.
Tudo isso é CPU e egress pagos que não entregam imagem. Medir antes de corrigir seria medir desperdício
e projetar em cima dele.

### D-10 · Capacidade do Orin só vale medida sob carga real
**03/08 · Claude → aceito · 🔄 em execução**

A primeira medição rodou com a câmera **ociosa** (sem tráfego RTSP) — mediu custo parado.
O número 1,1–1,8 pp GPU/câmera veio de 2 câmeras + streams sintéticos e **não pode ser extrapolado**
para 8. Rampa de +2 por degrau, **medindo cada degrau** com tráfego real.

---

## Segurança e multi-tenancy

### D-03 · Super admin enxerga o cliente por impersonação
**03/08 · Vitor (AskUserQuestion) · ✅ vigente · PR #279 mergeado**

Descartadas: visão cross-tenant agregada (superfície de vazamento nova) e tenant fixo na conta
(quebra no segundo cliente).
Desenho: token curto (30 min) com o schema do alvo + claim `impersonated_by`, banner permanente,
log de auditoria (migration 108).
⛔ **Restrição inegociável:** não mexer em `get_tenant_schema()` / `get_tenant_id()`. Se a solução
precisar tocar neles, está errada. Fallback de tenant continua banido (ADR-0017).

### D-18 · Senha não circula — cadastro pela impersonação
**04/08 · Claude → aceito · 🔄**

A senha do admin do DEV não é enviada ao Claude, nem colocada em prompt, log, commit ou `argv`.
Caminho: a conta superadmin `vitor@logikos.com` assume o contexto da RVB (D-03) e cadastra de lá.
Alternativa: fluxo de recuperação de senha (ADR-0042 Fase 1) — confirmar se está na `develop`.

### D-09 · Sondagem de gravador: ONVIF primeiro, do Orin, anti-lockout estrito
**03/08 · Claude → aceito · ✅ vigente**

A sondagem roda **do Orin**, nunca da nuvem — a VLAN de câmeras é isolada (ADR-0020) e sondar da nuvem
devolve timeout, que seria lido como "não há câmera".
**Uma credencial, validada uma vez. Qualquer 401/403 encerra a sessão — sem retentativa, sem variante.**
O gatilho de lockout é falha de autenticação, não volume.
Resultado 04/08: iNVD 3032, 8 canais, 7 requisições, zero 401/403, RTSP nunca necessário.

### D-11 · Os 2 gravadores extras e as ~21 câmeras ficam fora de escopo
**04/08 · Vitor · ✅ vigente**

`.210` / `.211` (iMHDX 3132) e ~21 câmeras ONVIF que não pertencem ao NVR conhecido.
**Não serão usados agora. ⛔ Zero requisição a eles.** Documentados no PR #284.
Titularidade a confirmar com a RVB antes de qualquer sondagem futura.

---

## Câmeras e edge

### D-04 · Cadastro manual agora + fatia mínima da ADR-0058
**03/08 · Vitor (AskUserQuestion) · ✅ vigente · PR #281 mergeado**

Descartadas: manual sem a fatia (repete SSH a cada câmera) e ADR-0058 completa primeiro (atrasa a coleta).
Entregue: mapa de canais via `config/poll`, divergência banco×edge visível no heartbeat.
Efeito colateral bom: expôs que o box rodava código anterior ao #281 e o `Permission denied` no cache de
config — corrigido com `EDGE_CONFIG_CACHE_PATH`.

### D-17 · Câmeras entram com nome provisório
**04/08 · Claude → aceito · 🔄**

Cadastrar os 8 canais como `Canal 1`, `Canal 2`… O Vitor renomeia depois **olhando a imagem ao vivo**,
que é a forma natural de identificar onde cada câmera está.
**Desbloqueia o live view sem esperar o mapa canal ↔ posição física.**

### D-20 · Nenhuma câmera nova entra com alerta ligado
**03/08 · Claude → aceito · ✅ vigente**

Não existe modelo treinado para elas. Alarme falso antes do go-live custa a confiança da RVB no produto.
Câmera nasce sem alerta por construção — confirmar que segue assim a cada rodada.

### D-24 · 🛑 O rate limit inviabiliza 8 câmeras — corrigir antes de subir
**04/08 · Claude (achado em log) · 🔄**

Medido no DEV em 04/08, 15:06–15:08: `ratelimit 300 per 1 minute (ip:…) exceeded`, com **429 em `.m3u8`,
`.ts` e até no `OPTIONS` de preflight**.

Três causas independentes:

1. **3 sessões simultâneas por câmera** (tokens nascidos com 39 min e 65 s de intervalo, todos vivos),
   baixando o **mesmo** segmento — o PR #285 (teardown) resolve e está aberto sem merge.
2. **A conta não fecha nem limpa:** ~1,5 req/s por câmera ⇒ **8 câmeras ≈ 720 req/min**, contra um teto
   de 300. Não é ajuste fino, é aritmética.
3. **A chave é o IP.** Numa fábrica todos saem pelo mesmo IP público — o limite é dividido pela operação
   inteira e um usuário derruba os outros.

Decidido: isentar `OPTIONS` · bucket separado para o caminho de vídeo · chave por usuário/tenant (com
teto de IP alto) · mergear o #285 primeiro.

⚠️ **Sem isso, o aceite "8 câmeras ao vivo" falha por motivo alheio às câmeras.**

### D-25 · Log duplicado — consolidar em uma linha, sem perder campo
**04/08 · Claude (achado em log) · 🔄**

Cada requisição gera duas linhas (`app.core.middleware` + `geventwebsocket.handler`), tudo em stderr.
Com 8 câmeras: ~1.440 linhas/min ≈ **2 milhões/dia**. Custa na Railway e inutiliza o log para
diagnóstico — que é onde os bugs têm sido achados.

↩ **Correção da própria decisão, no mesmo dia.** A primeira redação dizia "manter só o do middleware".
**Errado:** as duas linhas não são redundantes. O middleware tem `rid`; o gevent tem **bytes da resposta**
e **IP do cliente** — exatamente os números que sustentam a medição de egress (ADR-0059) e a investigação
de rate limit / sessão duplicada (D-24). Apagar a linha do gevent destruiria a evidência que estamos
usando para decidir arquitetura.

Decidido: **consolidar numa linha só** com `rid · método · rota · status · duração · bytes · IP`, e só
então silenciar o access log do gevent. Mais: INFO/DEBUG em **stdout**, WARNING+ em stderr — hoje o
Railway marca tudo como `[err]` e o filtro por severidade não serve para nada.

⚠️ Verificar cobertura antes de silenciar: nos 429 o middleware sai com `rid=-` e `(-0.000s)`, sinal de
que a requisição é barrada **antes** dele. Se a linha consolidada não cobrir esse caso, os 429 somem do
log — e são o que estamos investigando.

### Constatação · A câmera 2 voltou a funcionar
**04/08 · verificado em log**

`17bbada9` entrega segmentos reais (201 no `POST /segment`, `.ts` de 260–290 KB). Ela estava fora do
`RECORDER_CHANNEL_MAP` por decisão de 03/08. **Confirmar o que mudou** — decisão anterior não vale mais.
O `config/poll` segue em `cameras=2`: as 6 novas ainda não existem no banco.

### "Uma antes de seis"
**03/08 · prática adotada · ✅ vigente**

Validar caminho novo com **uma** câmera antes de aplicar a seis. Pagou imediatamente: achou dois furos
reais (OTA defasado, cache sem permissão) que teriam gerado seis câmeras fantasma.

---

## Flywheel de treino

### D-12 · Portão humano antes de construir ferramenta
**03/08 · Claude → aceito · ✅ vigente**

Se a ferramenta de anotação não existir, isso é **projeto, não item de lista**. O Code entrega diagnóstico
e proposta, e para. Respeitado na rodada de 04/08.

### D-13 · Ferramenta própria; SaaS de terceiro proibido
**03/08 · Vitor · ✅ vigente**

A ferramenta da ADR-0048 existe e é LGPD-safe. **Nada de CVAT/Label Studio** — a nossa existe.
⛔ **Frames com pessoas identificáveis não vão para ferramenta SaaS na nuvem de terceiro.**
Anotação é offline, então não conflita com a regra AGPL-zero do caminho servido (ADR-0043).

### D-14 · Deploy do celery-worker no DEV
**04/08 · Vitor · 🔄**

Nunca teve deploy no DEV (produção tem). Sem ele nada assíncrono roda e o treino não dispara.
Verificar o que mais volta junto: extração, retenção, evidência.

### D-15 · O treino não pode mentir
**04/08 · Claude → aceito · 🔄**

Hoje: `LocalProvider` é `_simulate_training` (`training.py:915-946`) — sleep e métricas fabricadas.
E `dataset_version_id` não chega ao job (`training_service.py:23-50`), então **cai em simulação
silenciosamente** e devolve número inventado.

**Terceira aparição da mesma doença** (após `.get(chave, ProductionConfig)` e o fallback de tenant da
ADR-0017): degradação silenciosa em vez de falha alta.

Decidido: simulação só por flag cujo nome diz simulação · dataset ausente = **erro** · artefato de
simulação marcado de forma indelével no banco, no nome do arquivo e na tela · métrica simulada nunca no
mesmo lugar e formato da real.

**Motivo de ser P0:** o Vitor disse que vai validar quando rodar o primeiro treino. Ele não consegue
validar um sistema que mente.

### D-16 · 🔴 O provedor de GPU é RunPod, não Vast.ai
**04/08 · Vitor (correção) · 🔄**

> *"Nós não utilizamos Vast AI, utilizamos RunPod, e já tem uma conexão gerada."*

Os relatórios anteriores diziam "Vast.ai" porque **é o que está escrito no código**:

| Onde | O que diz |
|---|---|
| `config.py:41-43` | `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID` — comentados como *"fallback"* |
| `constants.py:130` | `GpuProvider.VAST_AI` — **não existe valor RUNPOD no enum** |
| `job_handlers.py:260-265` | `gpu_enabled` checa `VAST_API_KEY` / `VAST_AI_API_KEY` / `ULTRALYTICS_HUB_API_KEY` — **não checa `RUNPOD_API_KEY`** |
| `training/vast/` | os scripts reais de treino |
| `training_compute.py` | `_dispatch_vast_ai` / `_dispatch_hub` / `_simulate_training` |

**A validar:** onde está a conexão RunPod · o caminho `vast_ai` é RunPod com nome errado ou são dois
provedores · se o Vitor usa RunPod, `gpu_enabled` reporta GPU desabilitada e **a tela mente**.

⛔ Não renomear o enum agora — `gpu_provider` é coluna com valores gravados (migration 097); é migração
de dados, não refactor.

**Por que é P0:** o contrato vai **nomear o suboperador** que processa as imagens. Documento dizendo
Vast.ai com realidade RunPod = contrato errado sobre transferência internacional de dado pessoal.

### D-19 · Pré-anotação: levantar, não ligar
**04/08 · Claude → aceito · 🔄**

`SERVICE_TYPE=pre-annotation` (DINO + SAM) existe no `railway_start.py`, flag OFF, nunca ativado.
Se funcionar, sugere as caixas e o humano só corrige — diferença entre 3 h e 30 min para 50 frames, e
entre o gargalo humano ser administrável ou não (~136 frames/dia com 8 câmeras).
Nesta rodada: só o levantamento. O caminho manual não espera por ele.

### Constatação · Dataset é pool por módulo+tenant
**04/08 · verificado no código**

Não é por câmera. Isso muda a aritmética da coleta: 8 câmeras × ~17 frames/dia = ~136/dia no pool comum,
não 59 dias por câmera. **A coleta deixa de ser gargalo; a anotação passa a ser.**
Registrado no `docs/ROADMAP_GO_LIVE.md` como cronograma de pessoa, não de código.

---

## Processo e qualidade

### D-05 · Ordem de merge #277→#278→#280→#279→#281
**03/08 · Claude → aceito · ✅ executada**

Inertes primeiro (config, testes), depois o fix visível ao usuário, depois os dois com migration.
`#281` só rebaseia **depois** do `#279` na develop, senão a renumeração 108→109 se perde.

### D-06 · `"staging": ProductionConfig` explícito + fallback levantando erro
**03/08 · Claude → aceito · ✅ · PR #277**

`_configs.get("staging", ProductionConfig)` fazia o **DEV rodar como produção sem ninguém saber**.
Resolvido: `DevelopmentConfig` **herda** de `ProductionConfig` com 4 divergências explícitas — dissolve a
tensão entre ambiente honesto e fidelidade de produção.
⚠️ Ordem obrigatória: mapear explícito → corrigir a env → só então fazer o fallback falhar.
Inverter derruba o DEV.

### D-07 · Guarda de CI contra colisão de numeração de migration
**03/08 · Claude → aceito · ✅ · PR #282**

Terceira aparição da família (ADR-0021 é sobre isso). E o risco **aumentou por decisão de processo**:
worktrees paralelas criando migrations independentes é a receita da colisão — a recomendação de
paralelismo foi do Claude, então a guarda também é responsabilidade dele.
Vigilância não escala; check de CI, sim.

### D-08 · Teste de regressão do lado do cliente é obrigatório
**03/08 · Claude → aceito · ✅ · PR #283**

O servidor tinha teste; o cliente não. O bug estava no cliente (`CameraPlayer.tsx:155-170` recarregando
URL morta). Essa família de bug já voltou uma vez.

### Prática · Hipótese é hipótese até a medição
**estabelecida 03/08 · ✅ vigente**

Quatro hipóteses do Claude foram derrubadas por medição (contenção de RTSP no NVR; watchdog apagando
`/tmp/hls`; watchdog apagando `:active`; "havia código ONVIF autenticado para portar").
Uma sobreviveu (laço no cliente) — e sobreviveu porque foi escrita como **hipótese falsificável com a
medição associada**, não como diagnóstico fechado.
**Regra:** o prompt nunca diz "já diagnosticado, só implemente". Diz a hipótese e a medição que a mata.

### Prática · Economia de token não vale onde o pior caso é incidente
**estabelecida 03/08 · ✅ vigente**

Fable para worktrees e git · Haiku para extração de dados · Sonnet para implementação · Opus só para
decisão de segurança irreversível ou diagnóstico contraditório.
**Exceção explícita:** a sondagem do gravador ficou em Sonnet apesar de parecer levantamento. Economize
onde o pior caso é token desperdiçado, não onde o pior caso é derrubar o NVR do cliente.

---

## Contrato e jurídico

### D-21 · Anexo de escopo de câmeras + cláusula de ampliação
**04/08 · Vitor · ✅ · seção 8 do dicionário**

Escopo contratado: 8 câmeras (canais 1–8 do iNVD 3032). Fora: os 2 gravadores extras e ~21 câmeras.
**Visibilidade técnica não implica autorização de uso.**
Ampliação futura **prevista como possibilidade** via aditivo ou ordem de serviço simples — incluir câmera
não deve exigir renegociar o contrato inteiro.
Se o preço for por câmera, o anexo é também a base de faturamento.

### D-22 · Seção de acesso da Logikos às imagens
**04/08 · Claude → aceito · ✅ · seção 9 do dicionário**

A impersonação (D-03) é acesso da Logikos a imagem de pessoa identificável do cliente. Precisa estar
**descrita no contrato**, não só implementada: finalidade, pessoas autorizadas, direito de auditoria do
cliente, e enquadramento LGPD no acordo de tratamento de dados.

### ⚠️ Pendente · Suboperador de GPU no contrato
**04/08 · aberto**

Depende de D-16. O contrato precisa nomear **quem** processa as imagens em GPU externa, e enfrentar que
marketplace de GPU pode significar datacenter, empresa e país desconhecidos — transferência internacional
para suboperador não identificado.
**Prazo: reunião com a advogada no dia 6.**

### D-23 · ADR-0059 (vídeo local-first + sessão única): Proposta
**02/08 · ⏸ adiada**

Sem aceite. A Parte A tem pré-condição explícita: **não implementar antes de o live view estar
comprovadamente estável** — mexer no caminho do vídeo com ele instável mistura as causas.
Registro importante: a Parte B (sessão única) **não** resolve o egress duplicado de abas — é o mesmo
usuário, mesmo dispositivo, abas diferentes.

### D-26 · celery-worker deployado no DEV
**04/08 · ✅ vigente**

Decisão do Vitor (Bloco C3): o worker nunca teve deploy no env Desenvolvimento — sem ele nada assíncrono
roda (dataset COCO, treino, extração de frames, retenção/evidência). Deployado e `celery@… ready`
consumindo todas as filas. **Achado ao subir:** `railway_start.py` fazia `os.chdir('backend/')` — diretório
extinto no monorepo (ADR-0010/0014) — crashando qualquer deploy novo em loop; produção só sobrevivia num
snapshot antigo. Corrigido (PR #289) resolvendo o pacote `app` nos dois layouts reais (checkout
`services/api/` e imagem `Dockerfile.worker` com `services/api/` na raiz). Também: `DATABASE_URL` do worker
no DEV apontava para credencial inválida — corrigido por referência `${{Postgres.DATABASE_URL}}`.

### D-27 · Rate limit em buckets dedicados
**04/08 · ✅ vigente · conclui D-24**

O bucket único de 300/min por IP (`tenant-api-global`) inviabilizava 8 câmeras (~720 req/min) e barrava até
`OPTIONS` de preflight. Separado (PR #291) em: OPTIONS 2000/min/IP; vídeo `.m3u8`/`.ts` 240/min por **token
de playback** + piso 6000/min/IP; API geral 300/min/usuário + piso 900/min/IP sempre ativo. **Não afrouxou
segurança:** login (10/min/IP), register/recuperação (5–10/h) e `progress-callback` (60/min) intocados e
estritos. Chave é "usuário **E** IP", nunca "em vez de". Validado no DEV: zero 429 no caminho de vídeo;
login barra a partir do 11º (10×401 → 429). Ver [[D-32]] sobre a granularidade real da chave por-IP.

### D-28 · Log de acesso consolidado
**04/08 · ✅ vigente · conclui D-25**

Duas linhas por requisição (middleware + `geventwebsocket.handler`), tudo em stderr, ~2M linhas/dia com 8
câmeras. Consolidado (PR #290) em **uma linha no middleware** com os 7 campos (`rid·método·rota·status·
duração·bytes·IP`), access log do gevent silenciado (só o INFO; erros de protocolo preservados), e
severidade por stream (INFO→stdout, WARNING+→stderr). Os 429 seguem visíveis (o handler de 429 preenche
rid/tempo). Confirmado no ar: uma linha, IP real do cliente via primeiro hop do X-Forwarded-For.

### D-29 · Treino honesto — fim do fallback silencioso para simulação
**04/08 · ✅ vigente · ADR-0060**

O treino caía em simulação (`_simulate_training`, métricas fabricadas) sem avisar quando faltava dataset ou
provider — terceira aparição da doença do fallback silencioso (ADR-0017). Corrigido (PR #292): simulação só
com `TRAINING_SIMULATION_ENABLED=true`; dataset ausente = erro alto; artefato simulado nasce marcado
(`metrics.simulated`, prefixo `SIMULATED_`, badge vermelho na tela); nuvem de terceiro gateada por
`training_third_party_cloud_enabled` (padrão OFF). **4º caminho encontrado** além dos três mapeados: o
fallback Vast→legado treinava no dataset público do Roboflow fingindo ser do tenant — eliminado.

### D-30 · Anotação destravada para frames NVR
**04/08 · ✅ vigente**

A galeria mostrava os 679 frames NVR mas o clique só abria o anotador com `video_id` (NULL para NVR desde a
migration 094). Correção aditiva (PR #288): modo "frame direto" quando não há vídeo pai, sem quebrar o
caminho de frame-de-vídeo. Fiado também o `dataset_version_id` ponta a ponta (era placeholder `=job_id`).
Aceite (humano): abrir `/epi/training`, clicar num frame NVR, desenhar caixa, salvar, recarregar — persiste.

### D-31 · Provedor de GPU: Vast.ai é o do código; RunPod é outro sistema
**04/08 · ✅ vigente · resolve a pendência "Suboperador de GPU no contrato"**

O Vitor disse usar RunPod. Investigação (C4): o código do treino do **modelo de visão** (RF-DETR/YOLOX) é
genuinamente Vast.ai — `vast_client.py` fala com `console.vast.ai/api/v0` real (não é RunPod renomeado); a
única tentativa real da integração retornou 404 em 12/07 (nunca funcionou de fato). A conexão RunPod
existe, mas em **outro sistema**: `training/finetune_assistant.py`, fine-tune do **chatbot assistente**
(LLM), script manual por SSH, fora de `training_jobs`. Zero chaves Vast/RunPod em qualquer ambiente Railway.
`gpu_enabled` não checa `RUNPOD_API_KEY` → a tela reporta GPU desabilitada mesmo com RunPod setado.
**Para o contrato:** o suboperador de GPU do modelo de visão, se e quando ligado, é a Vast.ai — não RunPod.
Renomear o enum `gpu_provider` (migration 097, valores gravados) é migração de dados, planejada, não feita.

### D-32 · Chave por-IP do limiter é o edge da conexão, não o cliente real
**04/08 · ⏸ follow-up**

Ao validar o login no DEV: 15 requisições em conexões separadas não dispararam 429, mas 15 na mesma conexão
TCP dispararam (10×401→5×429). Causa: o limiter usa `request.remote_addr` (ProxyFix `x_for=1` = **último**
hop do X-Forwarded-For = IP do edge da Railway, que varia por conexão), enquanto o log do A6 usa o
**primeiro** hop (IP real do cliente). Um browser real (conexões persistentes) acumula como o RVB acumulou;
requisições espalhadas por muitas conexões escapam. Implicação: proteção anti-brute-force é mais fraca que o
pretendido, e o cenário "fábrica atrás de um NAT" é menos severo que o temido. Ajustar `x_for` exige análise
própria (profundidade real do proxy Railway × o trade-off do NAT) — não mexido nesta rodada.
