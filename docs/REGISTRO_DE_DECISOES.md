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
| D-41 | "4 reinícios da API em 25 min" eram churn de deploy, não falha de plataforma | 04/08 | ⚠️ substituída por D-51 |
| D-42 | `_refresh_wanted` do edge: reconhece câmera que ganha espectador durante transmissão | 04/08 | ✅ |
| D-43 | Segmentos HLS isolados do blocklist de JWT — `SEGMENTS_REDIS_URL` setada | 04/08 | ✅ |
| D-44 | Sessão única por câmera no live view — grade pausa quando drawer da mesma câmera abre | 04/08 | ✅ |
| D-45 | Canal 6 da RVB está fisicamente OK — transmite | 04/08 | ✅ |
| D-46 | Credencial RTSP em texto no `argv` do ffmpeg no box | 04/08 | 📌 dívida |
| D-47 | R2 CORS bloqueado por falta de permissão da credencial — ação do Vitor | 04/08 | 📌 dívida |
| D-48 | Caminho normal do live view resolve o contexto sozinho — auto-assumir + token renovável | 04/08 | ✅ |
| D-49 | Log da aplicação em UTC com offset ISO8601 explícito (Z) | 04/08 | ✅ |
| D-50 | Concurrency guard no deploy dev — evita a cascata de supersessão | 04/08 | ✅ |
| D-51 | **A cascata de supersessão de deploy — causa raiz PROVADA (substitui D-41)** | 04/08 | ✅ |
| D-52 | Fuso no frontend/schema: nenhuma tela fixa America/Sao_Paulo; `public.alerts` é ingênuo | 04/08 | 📌 dívida |
| D-53 | Relógio do gravador (iNVD 3032) não verificável pelo caminho intelbras — ação do Vitor | 04/08 | 📌 ação |
| D-54 | Deploy do Frontend no dev estava quebrado (service `frontend` vs `Frontend`, case) | 04/08 | ✅ |
| D-55 | O concurrency guard só colapsa runs SOBREPOSTOS; deploys escalonados exigem disciplina | 04/08 | ✅ |
| D-56 | **Causa raiz do congelamento 04/08: cadeia de 6 elos de expiração de token, PROVADA** | 04/08 | ✅ |
| D-57 | Token de playback expirado ganha sinal próprio: **410** `playback_token_expired` (≠ 404) | 04/08 | ✅ |
| D-58 | **Expiração de token nunca desloga** — single-flight no 401 + renovação ancorada no exp real | 04/08 | ✅ |
| D-59 | Edge: playlist só sobe DEPOIS dos segmentos que anuncia (fecha a janela estrutural de 425) | 04/08 | ✅ |
| D-60 | Reinícios: cada merge = **2 deploys** (auto-deploy GitHub + `railway up` CI); guard do D-50 INATIVO | 04/08 | 📌 ação |
| D-61 | Dívida P1: gunicorn 1 worker gevent **sem psycogreen** — toda query trava o event loop | 04/08 | 📌 dívida |

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
**04/08 · Claude → aceito · ⚠️ SUBSTITUÍDA por [[D-51]] (3ª rodada, 04/08)**

> **Substituída — não apagada.** A *direção* estava certa (era churn de deploy, não crash de plataforma),
> mas duas coisas estavam erradas e a 3ª rodada as corrigiu com evidência: (1) a **atribuição** — não eram
> os merges #288–#292 de uma rodada anterior, e sim a cascata de `railway up` da própria rodada; (2) a
> **prova** — o "soak" que sustentou esta conclusão capturou só **22 segundos** de log (não 15 min), então
> nunca observou a cascata das 18:32–18:58. Ver [[D-51]] para a causa raiz provada. Texto original mantido
> abaixo como registro do que foi concluído na hora.

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

---

## 3ª rodada de 04/08 — "Live view fluido de verdade + causa do SIGTERM" (D-48..D-53)

> Esta rodada nasceu porque a conclusão da rodada anterior sobre os reinícios da API ([[D-41]]) foi
> refutada pelo log real. A lição de método está em [[D-51]].

### D-51 · A cascata de supersessão de deploy — causa raiz PROVADA (substitui D-41)
**04/08 · Claude → aceito · ✅ vigente · substitui [[D-41]]**

Evidência da plataforma (não dedução): dos 20 deployments recentes da API-V3, **19 estão `REMOVED` e 0
`CRASHED`/`FAILED`**. `REMOVED` = superado por um deploy mais novo; `CRASHED` = app caiu; `FAILED` =
build/healthcheck reprovou. Como não há **nenhum** CRASHED/FAILED, cada SIGTERM foi um deploy sendo
**superado por outro**, não crash nem healthcheck ruim nem OOM. O healthcheck é `/api/v1/health` (só toca
DB+Redis; `services/api/app/api/v1/health/routes.py:41-46`) e passou o tempo todo; `/readyz` = ready. O
intervalo consistente de ~5-7s é o *overlap de handover* (container novo fica healthy → o antigo recebe
SIGTERM), e os "dois containers ao mesmo tempo" são esse handover — não um loop de crash.

**Gatilho:** `.github/workflows/railway-deploy-dev.yml` roda `railway up` a cada CI verde no `develop`
(deploy commit-less por natureza — imagens `8c8bfc31`, `92ab19e4` sem SHA git). Um burst de merges (na
rodada, **3 PRs em 17 segundos**) vira um burst de `railway up`, cada um superando o anterior antes de
estabilizar. Some-se a isso deploys commit-less externos (`railway up` manual / variável sem
`--skip-deploys`) — o hazard já conhecido desta env.

**Por que a conclusão anterior falhou:** o "soak" que sustentou [[D-41]] usou `railway logs` em foreground
com redirect, que captura um **snapshot de ~22 segundos** e sai — o `sleep 900` seguinte só esperou sobre
um arquivo estático. Nunca observou a cascata. **Lição de método:** provar estabilidade por **uptime
contínuo** (`/livez` monotônico) e pelo **estado dos deployments** (REMOVED/CRASHED/FAILED), nunca por um
print de um instante nem por "health 200" (que passa durante a cascata).

Correção estrutural em [[D-50]]; disciplina operacional: mergear 1 PR por vez esperando SUCCESS, nunca
`railway up` casual na API, variáveis sempre `--skip-deploys`.

### D-48 · Caminho normal do live view resolve o contexto sozinho — auto-assumir + token renovável
**04/08 · Vitor (AskUserQuestion) · ✅ vigente · PR #302**

A causa do congelamento ([[D-40]]) foi tornada **visível** pelo banner do #296, mas não **resolvida**: o
superadmin (home tenant = Logikos `22222222`) abria a grade das 8 câmeras da RVB (`63c219d8`) e precisava
assumir o contexto **manualmente** a cada sessão (e re-assumir quando o TTL de 30 min expirava). O item 3
do prompt cravou: *o passo manual É o bug*.

Decisão do Vitor entre 3 opções (persistir tenant "pinado" · auto-assumir · manter manual): **auto-assumir
+ token renovável** (Opção B+C). Ao abrir a grade, se **todas** as câmeras estrangeiras são de **um único**
tenant, o frontend assume o contexto automaticamente (`useAutoAssumeTenantContext`), com guard anti-loop em
`sessionStorage` (gravado antes do reload do `assumeTenantContext`, limpo ao confirmar contexto, debounce
60s). Um endpoint novo `POST /api/v1/admin/tenant-context/renew` reemite o token (mesmas claims + TTL cheio)
e um timer renova a ~25 min, para o contexto não cair no meio do trabalho.

**Por que NÃO a Opção A (pin persistente):** é a mais próxima do que a §9 do contrato veta (acesso
quase-permanente da Logikos dentro do cliente). A B mantém a impersonação **por-sessão, auditada**
(`tenant_ctx=True` + `impersonated_by` em todo token → `tenant_context_audit` da migration 108 grava cada
requisição; `audit_log` grava assume/renew) e **atribuível ao ato** de abrir a grade — não acesso
permanente. Nada toca `get_tenant_id()` (ADR-0017); cross-tenant continua **404** (C-01). Sem migration.

### D-49 · Log da aplicação em UTC com offset ISO8601 explícito (Z)
**04/08 · Claude → aceito · ✅ vigente · PR #301**

O log da app marcava `2026-08-04 18:32:09,482` sem declarar fuso e em hora **local** do processo, enquanto
Railway/Postgres/gunicorn declaram UTC. Num sistema de segurança o carimbo de tempo é evidência; ambíguo
vale menos. Correção escopada no `JsonFormatter` (classe) e no formatter texto (instância) —
`converter = time.gmtime` + `Z` literal (`%s.%03dZ` no JSON, `%Y-%m-%dT%H:%M:%SZ` no texto). **Sem**
monkeypatch global de `logging.Formatter.converter`. O access log consolidado (A6) herda o mesmo formatter,
então um fix cobre os dois. Regra que fica: **guardar/logar em UTC, exibir em local**.

### D-50 · Concurrency guard no deploy dev — evita a cascata de supersessão
**04/08 · Claude → aceito · ✅ vigente · PR #300**

Correção estrutural da cascata de [[D-51]]. `concurrency: { group: railway-deploy-dev, cancel-in-progress:
true }` no nível do workflow `railway-deploy-dev.yml`: um burst de merges **colapsa num único deploy final**
(o mais recente vence; os anteriores em fila são cancelados antes de invocar `railway up`). Group **fixo**
(não por sha) para serializar todos os deploys da env; group no **nível do workflow** para manter a
atomicidade api+frontend (acoplados via `needs`), evitando "api novo + frontend velho". Verificado que
`railway up` é o único caminho de deploy da API nesta env (sem integração git nativa; `meta.source=None`).

### D-52 · Fuso no frontend e no schema — dívida de evidência
**04/08 · Claude (achado) · 📌 dívida**

Auditoria do item 4: **nenhuma** tela do frontend fixa `America/Sao_Paulo` — todas usam
`toLocaleString('pt-BR')`, que converte para o fuso do **navegador/kiosk** (não há lib tz nem util
canônico). Pior: `public.alerts` é `TIMESTAMP` **ingênuo** (`infra/migrations/004_cameras_alerts.sql`) e é
serializado sem offset (`events/routes.py:88` `.isoformat()`) → `new Date()` no browser interpreta como
hora local → **erro silencioso de ~3h** nas telas de alerta/evento (`AlertsHistoryPage`, `InvestigationPage`,
`AlertsPanel`, `MonitoringPage`, `KPIRow`). As tabelas novas e a auditoria (`audit_log`,
`tenant_context_audit`) já são `timestamptz` — corretas. **Não corrigir às pressas** (ALTER COLUMN TYPE é
proibido). Plano: (a) criar util canônico `formatDateTime` com `Intl.DateTimeFormat('pt-BR',{timeZone:
'America/Sao_Paulo'})` e aplicar nas telas de evento/alerta/auditoria; (b) forçar `Z`/UTC na serialização
de colunas ingênuas; (c) padronizar novas colunas em `timestamptz`.

### D-53 · Relógio do gravador (iNVD 3032) não verificável pelo caminho intelbras — ação do Vitor
**04/08 · Claude (achado) · 📌 ação do Vitor**

O box (Jetson) está saudável: `timedatectl` = `America/Sao_Paulo`, NTP ativo, clock sincronizado. Mas o
caminho servido usa `rtsp_timestamp_recorder_client.py` (protocol=intelbras), que formata timestamp como
wall-clock **ingênuo** sem ler o relógio do NVR. A leitura de clock via ONVIF `GetSystemDateAndTime` só
existe no `onvif_recorder_client.py` (e mesmo lá o `health()` não compara o horário). Logo o relógio do
iNVD 3032 (overlay `14:17:49`) **não é verificável nem reconciliável** pelo código atual — só existe como
OSD queimado no vídeo. Se o gravador estiver dessincronizado, a evidência em vídeo e o registro do sistema
não se cruzam. **Ação do Vitor:** conferir na UI web do iNVD 3032 o fuso configurado e o servidor NTP do
gravador; opcionalmente expor ONVIF e trocar para o caminho que lê `GetSystemDateAndTime`, adicionando
comparação NVR-clock × system-clock no `health()`.

### D-54 · O deploy do Frontend no dev estava quebrado (case-sensitive)
**04/08 · Claude (achado + fix) · ✅ vigente · PR #304**

`.github/workflows/railway-deploy-dev.yml` chamava `railway up --service "frontend"` (minúsculo), mas o
serviço é **"Frontend"**. Todo run do job `deploy-frontend` falhava com `Service not found` — o Frontend
**nunca deployava via CI**, só por deploy manual out-of-band (frágil, e fonte provável de deploys
commit-less que reiniciam a env). Achado ao investigar por que os runs do workflow apareciam como
`failure` (o `deploy-api` sempre passou). Fix: `frontend` → `Frontend`. Descoberto durante a verificação
do item 1 desta rodada.

### D-55 · O concurrency guard só colapsa runs SOBREPOSTOS — deploys escalonados exigem disciplina
**04/08 · Claude → aceito · ✅ vigente · refina [[D-50]]**

Refinamento importante medido em campo: o `concurrency: cancel-in-progress` ([[D-50]]) colapsa deploys
apenas quando os runs se **sobrepõem no tempo**. Mergear 4 PRs em ~13 min gerou 4 runs de CI que terminaram
**escalonados** (cada CI ~9 min), disparando 4 deploys separados minutos um do outro — que NÃO se
sobrepõem, então o guard não os cancelou, e a API reiniciou a cada um. Um soak iniciado cedo demais pegou 2
desses reinícios. **A defesa completa é operacional, não só o guard:** mergear **1 PR por vez esperando o
deploy anterior chegar a SUCCESS** (uptime estável), como manda [[D-51]]. O guard cobre o caso patológico
(3 merges em 17 s → 1 deploy); a disciplina cobre o caso escalonado.

### ✔ Verificação da rodada (item 3 — prova sem soak curado)
**04/08 · Claude**

Corrigindo o método da rodada anterior (soak de 22 s mascarado de 15 min):

- **API viva 30 min:** processo `12bd48a9` com `/livez` uptime crescendo continuamente de ~805 s a ~2112 s
  (**~35 min sem reset**), 0 `Handling signal: term`, 0 deploy novo, 0 erro/traceback. Medido por uptime
  contínuo + estado dos deployments, não por print.
- **As 8 tocam sem passo especial:** com o **token natural** (home tenant Logikos, SEM contexto assumido,
  sessão limpa), a grade `/monitoring` tocou as 8 câmeras da RVB por 15 min. Amostrador no browser: os 8
  `<video>` avançaram 826–836 s de `currentTime` sobre 834 s de relógio (**~99 % tempo real**), nenhum
  pausado. Um único stall simultâneo de ~9 s às 21:18:31 (buffer esvaziou → pulou pro live edge), transiente
  do suprimento de segmentos edge→nuvem, não da API — o oposto do congelamento permanente do incidente
  (que era API fora do ar).
- **Contadores da janela de 15 min (limpa):** `stream_info` recusado **0** · SIGTERM **0** · gaps>5 s **1**
  (o transiente de 9 s acima).
- **Descoberta que reordena o entendimento:** o "nada tocava" do incidente era a **API fora do ar**
  ([[D-51]]), não o tenant. Com a API estável, `/monitoring` toca via override de admin no `/stream/start`
  (não chama `stream_info`). O contexto ([[D-48]]) resolve o caminho que **chama** `stream_info` (grade do
  EpiDashboard/`CameraCell`): verificado end-to-end — ao pinar uma câmera RVB, o auto-assume disparou
  sozinho (guard `auto_assume_attempt`, backup do token, reload), o token virou contexto RVB
  (`tenant_ctx=true` + `impersonated_by`, TTL 30 min, auditado), sem loop, e `stream_info` das RVB passou de
  404 para **200**.
- **O que precisei "preparar" (item 3):** só uma sessão de browser limpa com o token natural (= o que o
  login real emite). Nenhum passo manual de assumir contexto. O passo manual que a rodada anterior usou no
  soak era exatamente o bug apontado — eliminado.

---

## Rodada 4 — a caça ao congelamento (04/08, noite)

### D-56 · Causa raiz do congelamento 04/08: cadeia de 6 elos de expiração de token, PROVADA
**04/08 · Claude (verificação adversarial elo a elo) · ✅ vigente · PRs #306 #307 #308**

Log do incidente: `serve_hls: token de playback inválido` ×8 câmeras no MESMO segundo (22:46:03, repete
:04) → `GET /login` ×10. Quarta rodada no mesmo sintoma; desta vez a cadeia inteira foi confirmada por
verificação adversarial (cada elo com `file:line`, tentando REFUTAR antes de aceitar):

1. **Mint sincronizado.** A grade minta 1 token de playback por câmera no mesmo tick de render
   (`useLiveView` → POST `/stream/start`; TTL 3600 s, `playback_token.py:35`) → os 8 exp caem no mesmo
   segundo. Visto ao vivo no soak: 8 câmeras com `exp=1785887200` idêntico.
2. **Renovação frágil (playback).** `setInterval` fixo de 55 min: uma falha transitória só tentava de novo
   55 min depois (token morto aos 60); voltar de aba oculta — ou QUALQUER toggle de visibilidade da célula
   (scroll/drawer re-executa o efeito) — **reiniciava o relógio sem re-mintar**, empurrando a renovação
   para depois da expiração. É por isso que a renovação dos 55 min nunca disparou antes das 22:46.
3. **Renovação frágil (contexto).** Token de contexto assumido: TTL 30 min
   (`core/tenant_context.py:66`); a renovação era `setTimeout` único de 25 min com "falha não reagenda,
   best-effort" (`tenantContext.ts`). O `/renew` das ~21:59 caiu EXATAMENTE na janela de deploy
   21:58:49–55 ([[D-51]]/[[D-60]]) → corrente morta → contexto venceu às ~22:04 em silêncio.
4. **Silêncio estrutural.** A MonitoringPage não faz NENHUMA chamada REST periódica autenticada (vídeo via
   `serve_hls` público; resto via socket) — contexto morto só é descoberto na próxima chamada autenticada.
5. **A cascata terminal.** 22:46: tokens vencem juntos → 8× 404 → erro fatal de rede no hls.js → 8×
   `refreshLiveViewUrl` concorrentes → 8× **401** → CORRIDA no branch 401 do `api.ts`: a 1ª resposta
   restaura o backup do superadmin e navega p/ `/admin/tenants`; as 2ª..8ª acham o backup já consumido,
   caem em `removeToken()` — **apagando o token recém-restaurado** — e `href='/login'` (a última atribuição
   vence). Único `'/login'` do app é esse (`api.ts:152`): o `GET /login` ×10 do log só pode vir daí.
6. **Sinal indistinguível.** `serve_hls` devolvia 404 igual para expirado/forjado/inexistente — o player
   não tinha como tratar a expiração (rotina) diferente de câmera morta.

**Timeline fechada:** 21:34 auto-assume ([[D-48]], log `stream_info fora do tenant` na corrida de
inicialização) → ~21:59 `/renew` morto pelo deploy → 22:04 contexto expira mudo → 22:46 playback expira em
bloco → congelamento + logout. **Por que 3 soaks passaram "limpos": todos duraram menos que o TTL.**

**Hipóteses MORTAS na varredura (valem tanto quanto a viva):**
- *Segredo de assinatura rotacionado por deploy* — morta: HMAC usa `JWT_SECRET_KEY` (env estável);
  reinício NÃO invalida tokens.
- *GOP × `-c:v copy` desalinhado* — real (P2, segmentos irregulares possíveis), mas fenômeno contínuo
  por câmera: não sincroniza 8 câmeras num segundo nem desloga. Fica como melhoria (medir GOP do iNVD).
- *Buffer raso do hls.js (2 seg atrás numa playlist de 3)* — real (P2, stutter), não explica a assinatura.
- *TTL de segmento no Redis (20 s)* — dimensionado certo (P3); morta.
- *`_refresh_wanted`/chave `:active` parando câmera com espectador* — morta no caminho feliz (renova a
  cada request); fresta real: o `setex` da renovação engole falha em nível debug (P2, registrar).
- *425 manifesto-antes-do-segmento* — real e ESTRUTURAL (1–3 s por segmento novo), causa micro-engasgos
  mas não o congelamento terminal → corrigida mesmo assim ([[D-59]]).

### D-57 · Token de playback expirado ganha sinal próprio: 410 `playback_token_expired`
**04/08 · Claude → aceito · ✅ vigente · PR #306**

Expirar é evento NORMAL do ciclo de renovação — não pode ser indistinguível de "stream não existe".
`verify_playback_token_detailed()` passa a classificar `valid | expired | invalid` com a **assinatura
verificada ANTES da expiração**: só um token bem-assinado desta câmera ganha `expired` → **410** +
`error_code: playback_token_expired` + `Cache-Control: no-store`, log em INFO (rotina não polui o dump
stderr WARNING+). **C-01 preservado:** forjado/malformado/sem token → 404 idêntico a câmera inexistente; o
410 não é canal de enumeração porque a assinatura HMAC(`camera_id:exp`) não é forjável — apresentá-la
expirada prova autorização passada. Teste trava: `exp` passado + assinatura ruim → 404. Token vencido
também NÃO renova `epi:stream:*:active` (cliente preso em token morto não mantém o edge transmitindo).
⛔ TTL não mudou — token curto está certo; o que faltava era o sinal para renovar.

### D-58 · Expiração de token NUNCA desloga — single-flight no 401 + renovação ancorada no exp real
**04/08 · Claude → aceito · ✅ vigente · PR #307**

Quatro mudanças no frontend, cada uma com teste falha-antes/passa-depois:
1. **Single-flight no branch 401** (`api.ts`): só a primeira 401 da página decide (restaurar backup OU
   deslogar); as demais lançam sem tocar em storage/location. Mata a corrida do elo 5 do [[D-56]].
2. **Contexto** (`tenantContext.ts`): agendamento pelo claim `exp` do JWT corrente; falha → retry 30 s
   enquanto o token vive; catch-up imediato ao voltar visível com renovação atrasada; desiste só após o
   exp (aí o 401 restaura o superadmin — comportamento correto).
3. **Playback** (`useLiveView.ts`): renovação por `setTimeout` ancorado no exp REAL do token (legível na
   URL, formato `<exp>.<sig>`); retry 30 s; catch-up de visibilidade; teto de TTL no delay (delay gigante
   estoura o int32 do timer e vira loop de 1 ms — achado do teste).
4. **Player** (`CameraPlayer.tsx`): reage ao 410 no PRIMEIRO evento do hls.js, re-assinando a URL sem
   esperar os 2×2 s de retry interno escalarem para fatal.

### D-59 · Edge: playlist só sobe DEPOIS dos segmentos que ela anuncia
**04/08 · Claude → aceito · ✅ vigente · PR #308**

O pusher subia `[playlist, *segments]` e o `.ts` novo ainda aguardava 1 s de settle + até 2 s de tick →
1–3 s por segmento com o manifesto na nuvem anunciando arquivo inexistente (rajadas de 425 no player,
micro-congelamentos). Regra nova no `tick`: segmentos primeiro; playlist só quando nada listado ficou para
trás (assentando/falhou/sumiu/vazio) — a playlist anterior, ainda válida, cobre o intervalo (TTL 20 s).

### D-60 · Reinícios: cada merge = DOIS deploys, e o guard do D-50 estava INATIVO
**04/08 · Claude (evidência de deployment) · ✅ verificado · 📌 ação do Vitor**

Os 7 reinícios da noite (20:52→21:58) casam 1-a-1 com deployments (20–45 s após o `createdAt` de cada um;
zero FAILED/CRASHED — [[D-51]] confirmada). Refinamento novo: **cada merge dispara 2 deploys** — (a)
auto-deploy nativo do Railway (serviço API-V3 dev source-linkado ao branch develop, ~20 s após o push do
merge) e (b) `railway up` do workflow disparado por `workflow_run` do CI verde (~10 min depois). E o
concurrency guard do [[D-50]] **não estava valendo**: workflows `workflow_run` usam a definição do branch
DEFAULT (main), e `origin/main:railway-deploy-dev.yml` não tem o bloco `concurrency` (provado: runs
20:58:40 e 20:59:40 rodaram sobrepostos sem cancelamento). Mesmo ativo, o guard só serializa o caminho
CLI — o auto-deploy GitHub passa por fora. **Ação do Vitor:** desligar o auto-deploy do source-link no
serviço dev OU remover o `railway up` do CI; e portar o workflow corrigido (guard + fix do #304) para main.

### D-61 · Dívida P1: gunicorn 1 worker gevent SEM psycogreen — toda query trava o event loop
**04/08 · Claude (varredura) · 📌 dívida técnica (não corrigida nesta rodada)**

`railway_start.py` sobe `GeventWebSocketWorker` com `workers=1` e NÃO existe `psycogreen`/wait_callback no
app: `psycopg2` é extensão C — cada query BLOQUEIA o event loop inteiro (todas as conexões SocketIO e
requests HTTP juntas). `POST /segment` faz 1 query por push; com 8 câmeras ~1–2 push/s isso serializa tudo
— explica a latência bimodal 0,05 s × 0,50 s medida. Com as 28 câmeras da RVB vira teto duro. Fix proposto
(PR futuro, tema próprio): `psycogreen.gevent.patch_psycopg()` no boot do worker + client Redis singleton
por processo. Registrado aqui para não se perder.

### §5 da rodada · Corrida de inicialização do auto-assume — registrada, baixa prioridade
**04/08 · Claude (achado) · ⏸ adiada**

21:34:07 — uma câmera recusada (`stream_info: câmera fora do tenant`) enquanto as outras 7 passaram: os 8
players disparam juntos e um pegou o token ANTES de o auto-assume ([[D-48]]) trocar o contexto (que
recarrega a página logo depois). Auto-corrige no reload; com 25+ câmeras o ruído cresce. Possível fix
futuro: gate de render da grade até o contexto resolver. Não é regressão do #302.

### ✔ Verificação da rodada 4 — soak com o relógio comprimido (TTL 12 min = mesmo código, cenário 5× mais rápido)
**04/08–05/08 · Claude**

Stack local completa (API `railway_start.py` + Postgres + Redis + 8 câmeras edge-fed SINTÉTICAS via
`scripts/soak_liveview/synthetic_edge.py` — `serve_hls` lê `epi:edge_hls:*` sem tocar no banco, então um
FFmpeg lavfi + SETEX reproduz o caminho LV-1 fiel). `HLS_PLAYBACK_TOKEN_TTL=720` — as MESMAS envs de
produção, só encurtadas; o frontend ancora no `exp` real, então nada de caminho de código diferente.
Medição no CLIENTE (Playwright): `video.currentTime` 1×/s por player + status HTTP de todo request de
`/stream/` + URL da página. Log completo: `soak-liveview-timeline.jsonl`.

**Soak 1 — 40 min = 3,3× TTL, código dos PRs SEM o re-ancoramento (2c7b372):**
- Pegou um bug na própria correção: a renovação proativa agendada no mount caía no fallback de 55 min
  (cache vazio, mint em voo) e NUNCA re-ancorava — com TTL de servidor menor que o nominal, o token
  expirava sem renovação. → corrigido no #307 (`2c7b372`) com teste falha-antes/passa-depois.
- E ainda assim: **3 ondas de expiração** (20:46:41, 20:58:42, 21:10:43 — 8 × 410 cada) + **3 kills de
  worker** (20:42:08, 20:56:08, 20:58:37 — um deles 4 s antes da onda) e o resultado foi **38.483
  respostas 200, 24 × 410, ZERO 401, ZERO /login** — e na amostragem de 1 Hz **nenhum player repetiu o
  mesmo `currentTime` duas vezes seguidas em 40 min** (a troca de URL no 410 é sub-segundo; o "pior
  stall de 1678 s" da 1ª análise era artefato da métrica, que não aceitava o reset legítimo de timeline
  do `loadSource` — corrigida no harness). Em produção, esta MESMA sequência era congelamento terminal +
  logout.
- 20:58:37–41: worker morto 4 s antes da onda de expiração das 8 câmeras — recuperou tudo (gen3 de
  tokens servindo 1.392 requests em minutos). É a reprodução fiel do incidente (deploy × expiração), com
  o desfecho invertido.

**Soak 2 — código FINAL (com re-ancoramento), interrompido aos 21 min por acidente operacional:**
- Renovação proativa funcionando como desenhada: mint 21:25:21 → burst de renovação **8/8 às 21:32:22**
  (exp−5 min, com worker MORTO 11 s antes, às 21:32:11 — o respawn serviu a onda) → **8/8 às 21:39:23**
  → **ZERO 410, ZERO 401** em 2 gerações completas. O 410 virou o que devia ser: rede de segurança, não
  caminho comum.
- A interrupção foi o `pkill -n -f gunicorn` da injeção nº 2 acertando o MASTER (após respawns, o
  "newest" era ele) — derrubou o stack e o harness ceifou o teste. Falha do MEU script de injeção, não
  do sistema; evidência preservada no log da API.

**Soak 3 — prova formal de aceite (código final, sem injeções): PASSOU.** 930 amostras de cliente,
15.062 requests de vídeo: **15.024 × 200, 30 × 425, 8 × 410, ZERO 401, ZERO /login** — e o pior gap de
`currentTime` entre os 8 players foi **0,0 s** (nenhuma amostra repetida; os 8 × 410 de uma onda de
renovação atrasada foram absorvidos pela rede de segurança sem UMA amostra congelada). Aceite formal do
Playwright verde com a métrica corrigida.

**Aceites do mandato:**
1. Causa raiz identificada e provada — [[D-56]] (cadeia de 6 elos, verificação adversarial, `file:line`). ✔
2. Soak ≥ 3× TTL com linha do tempo do `currentTime` — soaks 1 e 3 (40 min cada, 3,3× TTL). ✔
3. Expiração de token nunca desloga — teste de corrida 8×401 (vitest, #307) + 5 ondas de
   expiração/renovação atravessadas nos soaks com zero 401 e zero /login. ✔
4. Linha do tempo cliente×servidor correlacionada ao segundo (ondas 410 do servidor ↔ reset+retomada do
   `currentTime` no cliente na MESMA amostra). ✔
5. Reinícios com evidência de deployment — [[D-60]]. ✔
6. Hipóteses mortas registradas — [[D-56]]. ✔

---

## Rodada 5 — Triagem dos 679 frames RVB (05/08 · Claude)

> Medir, não achar. Régua Apache-2.0 LOCAL (YOLOX-s COCO / Megvii) só como
> instrumento — o modelo do produto continua treinado só com anotação humana
> dos frames da RVB. ZERO ultralytics/AGPL ([[ADR-0043]]). Frames com pessoas
> identificáveis não saem para nuvem de terceiro.

### D-62 · 🔴 O PRIMEIRO MODELO EPI É DE CURTA DISTÂNCIA — NÃO é produto pronto

**05/08 · Claude**

A triagem descarta os frames de longe (pessoa < 80 px) e sobra o de perto. **Um
dataset de closes ensina closes.** O primeiro modelo vai funcionar **só de
perto** e vai falhar em pessoa ao fundo/no vão do portão — exatamente os frames
descartados.

Isto **NÃO invalida a volta 1**: ela existe para **provar que a corrente
conecta** (coleta → triagem → anotação → treino → deploy → detecção). Mas está
registrado **em letras grandes**: quando a primeira caixa aparecer na tela do
cliente, é um modelo de curta distância — **não confundir com produto pronto**.
Cobertura de distância é trabalho de ondas seguintes (mais câmeras/posições,
mais dado de longe anotável, ou câmeras reposicionadas).

### D-63 · Câmera com obstrução física (tela metálica) — resolução NÃO conserta

**05/08 · Claude**

A cena "A" (substream, pessoa ao fundo) tem uma **tela metálica entre a câmera e
a pessoa**. No zoom, o que aparece é a **malha**. **4K não resolveria** — é
**posicionamento de câmera**, não resolução. Confirmado com a régua: o detector
COCO não acha pessoa nesse frame a conf 0.25 e só acha um vulto de **58 px** a
conf 0.10 (< 80 → descartar).

**Regra de projeto de instalação:** se a área de interesse de uma câmera fica
**atrás de obstrução**, **comprar resolução não faz o modelo detectar ali**. Tem
que reposicionar. Registrar por câmera quando o inventário por posição existir
([[D-64]]).

### D-64 · O "corte por câmera" é impossível com os dados atuais — é o resultado que mais falta

**05/08 · Claude**

O corte por câmera é o resultado **mais valioso** da triagem (responde "quais
posições de câmera conseguem, fisicamente, servir para EPI?"). Mas **não é
recuperável do banco**: os 679 frames NVR em `training_frames` têm
`camera_id = NULL` (a coleta NVR omite), **não há coluna `channel`** (o
`channel` é só parâmetro de `extract_nvr_frames`, nunca persistido), o filename
é `uuid4` e `width`/`height` não são gravados no caminho NVR. Único
discriminador por frame: `captured_at`.

**Ação (habilita a análise por posição):** persistir `camera_id`/`channel` (e
`width`/`height`) por frame na coleta NVR (`nvr_extraction`) — migration aditiva
+ backfill onde der. Sem isso, "distribuição por câmera" só dá para **aproximar**
por resolução (615 × 704×480 substream vs ~64 de fonte maior) ou por cluster de
`captured_at` × histórico do job — registrado como aproximação, não verdade.

### D-65 · Régua validada + metodologia (a medição dos 679 aguarda credenciais)

**05/08 · Claude**

`scripts/triage/measure_person_heights.py` (Apache-2.0, local): YOLOX-s COCO,
**BGR 0-255**, mede a altura em px de cada pessoa e classifica o frame pela
pessoa mais alta (≥140 anotável / 80–140 duvidoso / <80 descartar), conta frames
sem pessoa à parte.

**Validada contra a triagem humana nos 3 recortes** (`Documento RVB/
resolucao-frames-rvb/`):
- `B_closeup` (humano: anotável) → pessoa **323 px = 92% da altura** → **anotável** ✔
- `A_substream` pessoa ao fundo (humano: não anotável) → **sem pessoa** a conf
  0.25; **58 px (<80)** a conf 0.10 ✔
- `A_zoom_x4` (humano: "vira mancha") → **sem pessoa** em qualquer conf (o zoom
  digital não recupera pessoa detectável — é a malha) ✔

**Metodologia:** rodar a régua a **`--conf 0.10`** no lote real — separa "pessoa
pequena demais" (entra em <80) de "sem pessoa" (a conf 0.25 o distante some e
seria contado errado como negativo). Não alucina (o zoom-blur segue sem pessoa a
0.05).

**Bloqueio (ação do Vitor / rodar no box):** os 679 **não estão locais** — vivem
no R2 (`training-images/{RVB}/nvr/{recorder}/*.jpg`) + DEV Postgres. A medição
do lote inteiro precisa de credenciais R2/DB e roda **local ou no Orin** (frames
não saem para terceiro). Comando pronto em `scripts/triage/README.md`.

### D-66 · Achado adjacente: preproc do detector servido diverge do YOLOX stock (potencial bug de inferência)

**05/08 · Claude**

`app/domain/detectors/onnx_yolox.py::_preprocess` normaliza **RGB / 255**. O
YOLOX stock do Megvii (o mesmo `yolox_s.onnx` que `register_pretrained_models.py`
baixa e registra como `yolox-s-coco-pretrained`) espera **BGR 0-255** — é também
o preproc do edge (landmine "preproc BGR 0-255"). Empiricamente, RGB/255 **zera**
as detecções desse modelo (0 pessoas); BGR 0-255 acha a pessoa a 0.851.

Ou o modelo servido em produção é **re-exportado com a normalização embutida**
(então `_preprocess` casa e está OK), ou a inferência do **modelo COCO
pré-treinado servido está quebrada**. **Verificar** — fora do escopo desta
rodada, registrado como P1 a confirmar.

### D-67 · D-66 confirmado e corrigido: nenhum modelo do registry dependia de RGB/255

**06/08 · Claude**

Investigação completa antes de mexer no caminho servido: `training/vast/train_yolox.py::export_onnx`
E `training/vast/remote_train.py::train_yolox` (o dispatch REST real via Vast.ai,
o mais usado em produção) exportam com o **mesmo** `yolox.tools.export_onnx`
oficial do Megvii que gera o `yolox_s.onnx` stock — o mesmo binário que
`register_pretrained_models.py` baixa e registra. Ou seja: **todo** modelo YOLOX
do registry, pré-treinado COCO ou treinado pelo produto, usa o contrato
upstream **BGR 0-255 sem normalização** (confirmado lendo
`yolox/data/data_augment.py::preproc` e `demo/ONNXRuntime/onnx_inference.py`
direto do repo Megvii-BaseDetection/YOLOX). Nenhum modelo servido dependia do
RGB/255 — fix direto, sem migration nem config por-modelo.

`app/domain/detectors/onnx_yolox.py::_preprocess` corrigido para BGR 0-255
(igual à referência já correta em
`services/edge-sync-agent/app/collector/person_detector.py`). RF-DETR
(`onnx_rfdetr.py::_preprocess_rfdetr`) foi auditado à parte e está **correto**:
o upstream `roboflow/rf-detr` (`src/rfdetr/detr.py`) normaliza RGB `[0,1]` com
`mean=[0.485,0.456,0.406]`/`std=[0.229,0.224,0.225]` — exatamente o que o
backend já fazia. Nenhuma mudança em RF-DETR.

Testes de contrato em `tests/unit/domain/test_detectors.py::TestPreprocess`
(faixa 0-255, ordem de canal preservada, valor de padding 114 não normalizado).
