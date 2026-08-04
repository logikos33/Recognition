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
| D-33 | **RunPod é o provedor do primeiro treino real de visão** (Vast nunca funcionou) | 04/08 | 🔄 |
| D-34 | Limite de login por CONTA (complementa o limite por IP fraco do D-32) | 04/08 | ✅ |
| D-35 | Nenhum caminho de treino jamais funcionou — é peça a construir, não a fiar | 04/08 | 📌 constatação |
| D-36 | **Fluxo do dataset: anotação semente → propagação → aprovação humana → RunPod** | 04/08 | 🔄 |
| D-37 | `Vitor@devlogikos.com` é conta **Logikos com impersonação**, não usuário da RVB | 04/08 | 🔄 |
| D-38 | DINO+SAM roda **no RunPod, sob demanda** | 04/08 | 🔄 |
| D-39 | Toda anotação carrega **procedência** (humana / proposta / aprovada / rejeitada) | 04/08 | 🔄 |
| D-40 | Causa do congelamento do live view: sessão no tenant errado, não buffer/rede/capacidade | 04/08 | ✅ |
| D-41 | "4 reinícios da API em 25 min" eram churn de deploy, não falha de plataforma | 04/08 | ✅ |
| D-42 | `_refresh_wanted` do edge: reconhece câmera que ganha espectador durante transmissão | 04/08 | ✅ |
| D-43 | Segmentos HLS isolados do blocklist de JWT — `SEGMENTS_REDIS_URL` setada | 04/08 | ✅ |
| D-44 | Sessão única por câmera no live view — grade pausa quando drawer da mesma câmera abre | 04/08 | ✅ |
| D-45 | Canal 6 da RVB está fisicamente OK — transmite | 04/08 | ✅ |
| D-46 | Credencial RTSP em texto no `argv` do ffmpeg no box | 04/08 | 📌 dívida |
| D-47 | R2 CORS bloqueado por falta de permissão da credencial — ação do Vitor | 04/08 | 📌 dívida |

---

## Adendos de 04/08 (pós-rodada #288–#292)

### D-33 · RunPod é o provedor do primeiro treino real de visão
**04/08 · Vitor (AskUserQuestion) · 🔄**

Descartadas: consertar o caminho Vast.ai (mantém o pior cenário de LGPD) · treino local no Orin
(1-2 dias + concorrência térmica com a inferência) · decidir depois de anotar (trava no degrau seguinte).

**Razão principal, e ela é jurídica antes de ser técnica:** a Vast.ai é **marketplace** de GPU —
datacenter, empresa e país desconhecidos, suboperador **impossível de nomear** em contrato. A RunPod tem
datacenters próprios e identificáveis. Some-se a isso que a conta já existe e funciona (fine-tune do
assistente).

**Efeito no contrato:** resolve a pendência "suboperador de GPU". O documento passa a poder nomear
RunPod — mas **só depois de implementado**. Enquanto o dispatch apontar para a Vast, é a Vast que está
descrita pela realidade.

**Dívida que nasce junto:** o caminho Vast vira código morto com enum de aparência viva
(`GpuProvider.VAST_AI`, `training/vast/`, `_dispatch_vast_ai`). É a mesma classe de armadilha que já nos
custou uma rodada inteira de confusão de nome. **Remover ou desativar duro, não deixar dormindo.**
⚠️ `gpu_provider` é coluna com valores gravados (migration 097) — renomear é migração de dados.

### D-35 · Nenhum caminho de treino jamais funcionou
**04/08 · constatação · 📌**

Consolidando os quatro achados: `LocalProvider` era `_simulate_training` · a Vast.ai é o código real e
**a única tentativa deu 404 em 12/07** · o fallback treinava no dataset público do Roboflow fingindo ser
o do tenant · o `dataset_version_id` não chegava ao job.

**O degrau "treinar" nunca executou com sucesso, por provedor nenhum.** Isso reordena o flywheel: a volta 1
não é "fiar o que existe", é **construir a peça**. Anotar antes de existir caminho de treino trava no
degrau seguinte.

### D-36 · O fluxo do dataset — anotação é semente, não o dataset inteiro
**04/08 · Vitor · 🔄 · a implementar depois das câmeras ao vivo**

```
1. Vitor acessa as imagens da RVB           → conta Logikos + impersonação (D-37)
2. Anota ~N frames à mão                     → SEMENTE
3. DINO+SAM propaga                          → acha semelhantes e propõe a caixa (D-38)
4. Humano aprova ou rejeita cada proposta    → o portão de qualidade
5. Aprovadas formam o dataset                → pacote exportado para o R2
6. RunPod treina                             → modelo (D-33)
```

**A anotação manual é semente, não o dataset.** Dezenas anotadas à mão viram centenas propostas pela
máquina e aprovadas pelo humano. É o que tira a anotação do caminho crítico — com 8 câmeras produzindo
~136 frames/dia, anotar tudo à mão não escala.

**Onde vive o quê:** caixas e rótulos no **Postgres** (dado estruturado pequeno) · imagens no **R2**
(já vão) · **pacote do dataset no R2**, que é de onde o RunPod baixa.

⚠️ **Confrontar a ADR-0031 antes de assumir que a propagação funciona.** O DINO+SAM foi removido em maio
por "custo × qualidade ruim" — mas provavelmente numa tarefa diferente. Detectar "pessoa sem capacete"
do zero é difícil; **propagar a partir de uma caixa que o humano já desenhou é muito mais fácil** — o SAM
é feito para "dado este ponto, me dê a máscara", e o DINO para "ache imagens parecidas com esta".
Leitura de 10 minutos que decide se o passo 3 é viável.

### D-37 · `Vitor@devlogikos.com` é conta Logikos com impersonação
**04/08 · Vitor (AskUserQuestion) · 🔄**

Descartadas: usuário permanente dentro do tenant RVB (**contradiz a §9 do dicionário do contrato** —
criaria acesso permanente e não auditado de pessoa da Logikos dentro do cliente, e o contrato teria de
ser reescrito) · duas identidades (humana + serviço), adiada por não ser necessária ainda.

Usa a impersonação do #279, já viva: token de 30 min, `impersonated_by`, banner permanente, auditoria.
**Mantém a história de LGPD coerente com o que vai para a advogada dia 6.**

### D-38 · DINO+SAM roda no RunPod, sob demanda
**04/08 · Vitor (AskUserQuestion) · 🔄**

Descartadas: Railway (não tem GPU — roda em CPU, lento e caro; foi assim que virou "custo × qualidade
ruim" em maio) · Orin (compete com a inferência, que é o trabalho nº 1 do box, e propagação é trabalho
pesado em rajada).

**Ganho decisivo:** mesma conta e credencial do treino (D-33) ⇒ **um único suboperador para nomear no
contrato**, em vez de dois. E as duas coisas usam a mesma peça de dispatch, que já está no plano.

### D-39 · Toda anotação carrega procedência
**04/08 · Claude · 🔄**

Cada anotação registra de onde veio: `humana` · `proposta_automática` · `auto_aprovada` ·
`auto_rejeitada`.

Sem isso não se consegue **medir se o propagador está acertando**, **excluir propagação ruim do treino**,
nem **explicar depois no que o modelo foi treinado** — que é pergunta de contrato, não só de engenharia.

É a mesma família do treino que mentia: **dado sem procedência envenena silenciosamente**.
⚠️ **Tem que existir desde o primeiro registro gravado** — retroagir procedência em anotação já feita é
impossível.

### ↩ Correção de método · propaguei correção sem verificar
**04/08 · Claude**

Em 04/08 o Vitor corrigiu "não usamos Vast, usamos RunPod". **Aceitei sem verificar**, reescrevi o prompt,
atualizei este registro (D-16) e marquei a pendência do contrato em cima disso.

A verificação do Code mostrou o contrário: `vast_client.py` fala com `console.vast.ai` de verdade; a
conexão RunPod é do **fine-tune do chatbot assistente**, sistema diferente, fora do pipeline de visão.

**O erro de método é o mesmo que este projeto vem combatendo:** tratei uma fonte como verificada porque
ela era confiável. Memória do dono do projeto é fonte como qualquer outra — precisa de `file:line`.

**Onde quase machucou:** se a pendência tivesse ido à advogada nomeando RunPod, o contrato descreveria
errado quem processa imagem de trabalhador identificável. Reunião dia 6.

**Regra que fica:** correção verbal reabre a pergunta, não a fecha. Vai para o prompt como *"verificar e
reportar"*, nunca como fato.

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

### D-34 · Limite de login por CONTA (D-32 tinha só o limite por IP)
**04/08 · ✅ implementada**

D-32 registrou que o limite por IP fica fraco atrás do ProxyFix (`x_for=1` acumula por conexão, não por
cliente real) — brute-force distribuído por várias conexões escapa. Correção complementar (sem mexer em
`x_for` nem no limiter por IP, que segue como defesa em profundidade): contador de falhas **por conta**
(`login_fail:{email normalizado}`) em Redis, `app/core/login_account_limiter.py`. Teto 10 falhas / janela 15
min (`LOGIN_ACCOUNT_MAX_FAILURES` / `LOGIN_ACCOUNT_WINDOW_SECONDS`, env-configuráveis). Sucesso reseta o
contador (OWASP). Fail-open: Redis indisponível nunca bloqueia nem derruba o login (mesma filosofia de
`request_metrics.py`/`session_service.py`) — disponibilidade de login vence rigor do contador quando a
infra de contagem está fora. Mensagem ao usuário é genérica (não revela que a conta específica está
bloqueada, evita enumeração). Teste reproduz o cenário exato do D-32 (15 falhas para a mesma conta, cada
uma de um IP/conexão distinto) e prova que quem dispara o 429 a partir da 11ª é o limite por conta, não o
por IP.

---

## Rodada de 04/08 — Live view fluido + canal 6

### D-40 · Causa do congelamento do live view: sessão no tenant errado, não buffer/rede/capacidade
**04/08 · Claude → aceito · ✅ vigente · PR #296**

O superadmin (`vitor@devlogikos.com`, tenant DEV `22222222…`) abria a grade com as 8 câmeras da RVB
(`63c219d8…`) **sem assumir o contexto**. `stream_info` recusava o cross-tenant com 404 (C-01, correto),
o token de playback expirava, e a imagem congelava sem explicação na tela. O playback seguia rodando
enquanto o token antigo valia — override por role superadmin em `build_stream_url` — o que mascarava a
causa real por minutos.

Descartadas por medição: buffer, rede, capacidade — GPU a 0%, segmentos em 30–50ms no momento do
congelamento.

Correção: falha **visível** na tela + CTA "assumir contexto", sem afrouxar o 404 do cross-tenant
(ADR-0017, C-01 preservados — nenhuma exceção nova de tenant).

### D-41 · Os "4 reinícios da API em 25 min" eram churn de deploy, não falha de plataforma
**04/08 · Claude → aceito · ✅ vigente**

O padrão start→SIGTERM~7s no log de 04/08 entre 16:29 e 16:53 era o Railway subindo container novo e
desligando o antigo a cada merge (#288–#292) somado aos redeploys manuais da rodada anterior. Não houve
OOM nem healthcheck reprovando. Confirmado: API estável e `/health` 200 desde 16:49Z; a janela sem
gunicorn depois de 16:53 foi só o fim da sequência de deploys, não um crash.

Lição: **correlacionar reinício com a timeline de deploy antes de suspeitar de crash de plataforma.**

### D-42 · `_refresh_wanted` do edge só reconhecia câmera nova quando TODAS estavam ociosas
**04/08 · Claude → aceito · ✅ vigente · PR #294**

Bug: a supressão do poll de `wanted` usava `any(transcoder rodando)` — com 1 de N câmeras já transmitindo,
o poll ficava suprimido, e uma câmera ociosa que ganhasse espectador durante a transmissão das outras
nunca subia até **todas** perderem espectador. Corrigido para `all(câmeras conhecidas transmitindo)`.

Nota operacional: o ciclo OTA reinicia só o `edge-sync-agent.service`, não o `edge-live-view.service` —
aplicar essa mudança no box exige `systemctl --user restart edge-live-view` manual. Dívida a resolver no
updater (ver D-46/D-47).

### D-43 · Limite de segmentos HLS isolado do blocklist de JWT — `SEGMENTS_REDIS_URL` setada
**04/08 · Claude → aceito · ✅ vigente**

No DEV, `SEGMENTS_REDIS_URL=${Redis.REDIS_URL}/1` (DB 1) separa o keyspace dos segmentos
(`epi:edge_hls:*`) do `revoked_jti:*` do blocklist de JWT — verificado que os segmentos passaram a gravar
no DB 1. Política da instância ajustada para `volatile-ttl` + `maxmemory 512mb` (**nunca** `allkeys-lru`,
que despejaria tokens revogados sob pressão de memória — reabriria um buraco de segurança).

Ressalva: o Redis do Railway roda sem arquivo de config, então `CONFIG SET` é runtime — não sobrevive a
restart do serviço. Durabilizar via `startCommand` do serviço Redis é follow-up.
Runbook: `docs/runbooks/REDIS_SEGMENTS_SEPARATION.md`.

### D-44 · Sessão única por câmera no live view — card da grade pausa quando o drawer da mesma câmera abre
**04/08 · Claude → aceito · ✅ vigente · PR #298**

Causa das sessões de playback duplicadas (dois tokens vivos baixando o mesmo `.ts`, ~457s de gap): grade
e drawer montavam, cada um, seu próprio `useLiveView` + `CameraPlayer` para a mesma câmera, sem
coordenação entre si. Corrigido por composição em `MonitoringPage` (prop `suppressed`), sem tocar em
`useLiveView`/`CameraPlayer`.

**Não era consequência do cross-tenant (D-40)** — confirmado como causa independente.

### D-45 · Canal 6 da RVB está fisicamente OK — transmite
**04/08 · verificado no box · ✅ vigente**

A suspeita de defeito físico/NVR no canal 6 foi descartada: uma única sondagem `ffmpeg` no box (canal 6 =
câmera `4e261bef…`) retornou exit 0, e a câmera aparece com imagem no soak das 8. A sondagem respeitou o
limite de **uma** tentativa (anti-lockout, D-09). Status: sem ação necessária.

### D-46 · Credencial RTSP em texto no `argv` do ffmpeg no box
**04/08 · Claude (achado) · 📌 dívida**

Qualquer processo com `ps` no Orin vê a senha do gravador na URL RTSP (`rtsp://user:pass@host/...`) — a
credencial trafega em texto claro na linha de comando do processo ffmpeg. Pré-existente, não introduzido
nesta rodada. Mitigação sugerida: passar a credencial via variável de ambiente do processo ffmpeg em vez
de embuti-la na URL. **Não corrigido agora — registrado.**

### D-47 · R2 CORS bloqueado por falta de permissão da credencial — ação do Vitor
**04/08 · Claude (achado) · 📌 dívida**

No boot, `PutBucketCors` retorna `AccessDenied` — a credencial R2 usada é de escopo *object-level*, sem
permissão de gerenciar o bucket (confirmado: `Get` e `Put BucketCors` negados no DEV). Hoje **não** quebra
a exibição de imagens de anotação (a tag `<img>` não dispara preflight CORS), mas **vai** quebrar upload
direto do browser e leitura via canvas/`fetch`.

Resolver antes da etapa de anotação: ou dar permissão de bucket à credencial no dashboard Cloudflare R2,
ou configurar o CORS do bucket fora da aplicação. **Ação do Vitor** — não automatizável sem token
Cloudflare.
