# Harness — Documento Exploratório

> **Status:** rascunho para discussão (não é decisão fechada).
> **Autor:** sessão Cowork + Lucas.
> **Data:** 2026-06-02.
> **Objetivo:** pensar como aplicar a ideia de "harness" no Recognition em dois eixos que, no fundo, são o mesmo problema: (1) **operar a produção na RVB remotamente**, corrigindo o máximo da operação sem ninguém se deslocar a Blumenau; (2) **desenvolver com autonomia**, parando de copiar e colar código no VS Code e deixando o agente conduzir até o objetivo final que ele já conhece.

---

## 0. A intuição central

"Harness" (arnês) é um laço de feedback com fonte de verdade. Você dá ao sistema — seja um pipeline de inferência rodando na fábrica, seja um agente escrevendo código — um sinal confiável de "isto está certo / isto está errado", e a partir daí ele consegue se autocorrigir sem humano no meio.

Os dois pedidos seus são a mesma coisa vista de dois ângulos:

- **Operação remota** = harness sobre a *operação física* na RVB. A fonte de verdade é a telemetria do edge; as ações são comandos remotos; a autocorreção é self-healing.
- **Desenvolvimento autônomo** = harness sobre o *código*. A fonte de verdade são testes + CI + o harness de simulação; as ações são commits/PRs; a autocorreção é o agente reescrevendo até ficar verde.

A lição que vocês já pagaram caro nas Sprints 0.5/0.6 — "quem infere em vez de verificar, quebra" — vale para os dois. Autonomia sem fonte de verdade só acelera o erro. **Construir as fontes de verdade é o trabalho de maior alavancagem agora**, enquanto o hardware não chega.

---

# PARTE I — Harness de Operação (produção remota na RVB)

## 1. O problema concreto

O Mini PC vai morar na fábrica da RVB em Blumenau, atrás do NAT/firewall do cliente, processando 28+ câmeras. Quando algo der errado — pipeline travou, câmera caiu, FPS despencou, modelo errando, disco enchendo — você precisa **diagnosticar e corrigir de onde estiver**, sem pegar estrada. Ir presencialmente deve ser a exceção rara (hardware morto, cabo solto), não a regra.

A boa notícia: a arquitetura já foi desenhada outbound-only (`EDGE_AGENT_ARCHITECTURE.md`), com Cloudflare Tunnel + Tailscale decididos. Falta transformar isso num **plano de controle** completo: observar → diagnosticar → agir → autocurar → escalar pro humano só no que precisa.

## 2. As cinco camadas da operabilidade remota

### Camada 1 — Observabilidade (saber o que está acontecendo)

Você não conserta o que não enxerga. Três tipos de sinal:

- **Métricas/telemetria** — já existe a fundação: a tabela `edge_heartbeats` (migration 053 da Fase 1) carrega CPU/mem/GPU/disco, FPS de inferência, latência, câmeras online/total, profundidade de fila, banda, status (`healthy|degraded|critical|offline`) e versão do edge. O edge-sync-agent emite isso periodicamente; o cloud guarda e exibe num painel. Isso é o "sinal vital" do site.
- **Logs estruturados** — o edge manda logs (JSON, sem PII) em batch pro cloud, com nível e componente. Erros e warnings ficam pesquisáveis sem SSH.
- **Eventos de saúde** — quando um pipeline crasha, uma câmera fica N minutos offline, ou o buffer SQLite passa de um limiar, o edge emite um evento de saúde (não um alerta de EPI — um alerta *de operação*).

> Decisão em aberto: usar um stack pronto (Sentry pra erros, Grafana/Prometheus pra métricas — a trilha S3 já cita Sentry) ou começar simples com a própria tabela `edge_heartbeats` + um painel no frontend admin. Recomendação: começar simples (tabela + painel admin), plugar Sentry cedo (barato), e só ir pra Grafana quando o volume justificar.

### Camada 2 — Acesso remoto seguro (entrar na máquina quando precisar)

Já decidido no plano: **Tailscale SSH** (rede mesh, `ssh user@rvb-blumenau-01` de qualquer lugar, sem abrir porta) + **Cloudflare Tunnel** (expõe a API/live-view LAN do edge pro cloud sem inbound). Isso te dá o "modo manual" remoto: quando o diagnóstico automático não basta, você entra na máquina como se estivesse na fábrica.

Princípio: acesso humano remoto é a rede de segurança, não o fluxo normal. O fluxo normal deve ser comandos estruturados (Camada 3).

### Camada 3 — Controle remoto (agir sem SSH)

Aqui mora o coração do seu pedido. Em vez de entrar por SSH e rodar comando na mão, o cloud tem uma **fila de comandos** que o edge consome por polling (mesmo padrão HTTP polling + idempotência da comunicação edge↔cloud já decidida — ADR-0004). Você clica num botão no painel admin, o cloud enfileira um comando, o edge busca, executa, e reporta o resultado de volta.

Comandos típicos que cobrem 80% das intervenções de campo:

- Reiniciar um pipeline / o stack inteiro do edge.
- Trocar/recarregar o modelo (hot-swap — já é cenário 3 da Fase 9).
- Recalibrar ou ajustar zona/sensibilidade de uma câmera (o módulo Operations já tem hot-reload via Redis).
- Re-enrollar / rotacionar device token.
- Puxar um pacote de diagnóstico (últimos logs, snapshot de métricas, frame de teste de uma câmera).
- Mudar FPS, resolução, ou desligar/ligar uma câmera específica.
- Forçar drain do buffer SQLite ou limpar disco.

Cada comando precisa ser **idempotente, versionado e auditado** (quem mandou, quando, resultado). Isso é o que transforma "preciso ir lá" em "resolvo do celular".

### Camada 4 — Auto-cura (o edge se conserta sozinho no trivial)

O melhor chamado remoto é o que nunca acontece porque o edge se recuperou sozinho:

- **Supervisão de processo** — systemd/supervisord reinicia container/pipeline que morreu. Restart policy no docker-compose.
- **Watchdog de câmera** — reconnect automático com backoff (o `camera_manager` já faz isso: reconecta a cada 2s).
- **Autonomia offline** — internet caiu, inferência continua, alertas locais disparam, eventos vão pro SQLite, sincroniza quando volta (já é princípio do design + cenário 2 da Fase 9).
- **Circuit breakers** — se a GPU está a 100% e a fila estoura, derruba FPS automaticamente antes de travar tudo, e emite evento de saúde.
- **Auto-update controlado** — o edge poda logs, rotaciona, e pode aplicar update de config/modelo validado por checksum sem intervenção.

### Camada 5 — Escalonamento pro humano (saber quando te chamar)

Quando a auto-cura não resolve, o sistema **te procura** (não você descobrindo tarde): notificação (e-mail/WhatsApp/Slack) com o pacote de diagnóstico já anexado. Regra de ouro: o alerta chega com contexto suficiente pra você decidir a ação remota em segundos, não com "deu erro, vai ver".

## 3. Níveis de operação remota (onde você quer chegar)

| Nível | O que significa | Custo de uma falha |
|------|------------------|--------------------|
| **N0** | Vai presencialmente resolver | Uma viagem a Blumenau |
| **N1** | SSH remoto manual (Tailscale) | Seu tempo, mas sem deslocamento |
| **N2** | Painel com comandos remotos estruturados | Minutos, do celular |
| **N3** | Auto-cura no trivial + alerta com diagnóstico no resto | Quase zero no comum |
| **N4** | Agente de operação decide e executa a correção remota sozinho, te avisando | Supervisão, não operação |

A meta realista pro go-live da RVB é **N2 com pedaços de N3**. N4 (um agente operando a planta) é aspiracional e conversa com a Parte II — mas só depois que a telemetria e os comandos forem confiáveis.

## 4. O que dá pra corrigir remoto vs. o que exige mão física

Honestidade pra calibrar expectativa. **Remoto resolve:** software travado, modelo errado, config de câmera, parâmetros de zona, rotação de credencial, disco cheio, restart, update, rede do edge. **Exige alguém na fábrica:** cabo de rede/energia solto, GPU/PC morto, câmera fisicamente quebrada ou desalinhada, troca de hardware. O objetivo do harness de operação é empurrar o máximo de incidentes pra primeira coluna — e, pra segunda, dar diagnóstico tão preciso que um técnico local (ou o próprio pessoal da RVB) resolve seguindo um runbook, sem você ir.

---

# PARTE II — Harness de Desenvolvimento (autonomia, sem copy-paste)

## 5. O problema concreto

Hoje o fluxo é: a gente escreve um prompt → você cola no VS Code → o Claude Code executa → você revisa → repete. O copy-paste é o gargalo, e você quer que o agente **conduza sozinho até o fim**, porque o objetivo final (Recognition rodando plug-and-play na RVB) está documentado e ele "sabe onde queremos chegar".

Dá pra fazer. Mas autonomia de verdade exige duas coisas que o copy-paste esconde: um **sinal de verdade** que diga ao agente se ele acertou, e **trilhos** que impeçam estrago irreversível. Vocês já têm boa parte dos trilhos.

## 6. A peça que falta: a fonte de verdade (o harness de simulação)

A Fase 9 do plano já especifica um `tests/harness/` que simula edge + cloud em containers: MediaMTX servindo vídeos sintéticos como RTSP, fault injection (derruba cloud, latência, perda de pacote), e 8 cenários (baseline, offline-recovery, model rollout, carga 42 câmeras, multi-tenant isolation, rotação de token, enrollment, dual mode), com um subset rápido rodando no CI a cada PR.

**A jogada:** antecipar esse harness. Ele é, ao mesmo tempo, (a) o que valida a operação antes do PC chegar e (b) a fonte de verdade que permite o agente desenvolver sozinho. Sem ele, um agente autônomo só acumula código não verificado — exatamente o modo de falha das Sprints 0.5/0.6. Com ele, o agente tem um "passou/não passou" objetivo a cada iteração.

As camadas de verdade, da mais barata à mais cara:

1. **Estática** — ruff, gitleaks, tsc, mypy. Rápido, roda sempre.
2. **Testes unitários/integração** — pytest, incluindo migrations contra um Postgres efêmero (docker) em vez de inferir schema.
3. **Harness de cenário** — o `tests/harness/` da Fase 9, subset rápido no CI.
4. **Banco real** — o `railway run psql` que vocês firmaram, pra validação final pré-merge.

## 7. Como o agente roda sem você colar código

Três mecanismos, do mais simples ao mais autônomo:

- **Claude Code headless** — `claude -p "<tarefa>"` em modo não-interativo, com lista de ferramentas permitidas e permissões pré-aprovadas. Roda a tarefa do começo ao fim e para nos checkpoints. Já elimina o copy-paste pra uma tarefa fechada.
- **Hooks** — o Claude Code dispara comandos em eventos (ex: rodar testes depois de cada edit, bloquear commit se o lint falhar). É como você "programa" o comportamento de verificação sem ficar pedindo.
- **Driver/loop (Agent SDK ou script)** — um orquestrador que pega a próxima tarefa de uma fila, chama o agente, roda o harness, e decide: verde → commita e segue; vermelho → devolve o erro pro agente tentar de novo (N tentativas); irreversível → para e te chama. É isto que vira "desenvolve sozinho até o fim".

## 8. Níveis de autonomia de desenvolvimento

| Nível | Fluxo | Humano entra em |
|------|-------|------------------|
| **L0** | Copy-paste no VS Code (hoje) | Tudo |
| **L1** | Headless, uma tarefa fechada por vez | Revisar cada PR |
| **L2** | Loop sobre fila de tarefas, auto-retry no vermelho | Revisar PRs + checkpoints |
| **L3** | Auto-merge em `develop` atrás de CI verde | Só checkpoints irreversíveis |

Vocês já têm ~70% do que L2/L3 exige: `CLAUDE.md` com as regras, os checkpoints de irreversibilidade do handoff, e o CI de 4 checks. Falta o harness de cenário (Parte II.6) e o driver (II.7).

## 9. Os trilhos (sem isto, autonomia é perigosa)

- **Checkpoints de irreversibilidade** (já definidos): nunca autônomo em `DROP`, `main`, force-push, dados de cliente, `create_tenant_schema()`, migration contra produção, dependência nova.
- **Spec-driven** — contratos OpenAPI/AsyncAPI em `shared/proto/` (ADR-0009) são o "norte" que o agente segue: ele implementa contra o contrato, e o harness valida contra o mesmo contrato. Isso reduz drift e dá ao agente um alvo inequívoco.
- **Branch protection + PR obrigatório** — o agente nunca toca `main`; tudo passa por PR com CI verde.
- **Orçamento e parada** — limite de tentativas/custo por tarefa; se estourar, para e escala.

---

# PARTE III — Onde os dois harness se encontram

Não são dois projetos: são o mesmo plano de controle.

- O **harness de operação** (telemetria + comandos + fault injection na RVB) usa os mesmos componentes que o **harness de simulação** da Fase 9 (synthetic RTSP, injeção de falha, asserções de "evento chegou", "isolamento multi-tenant"). O que simula a RVB no dev é o que monitora a RVB em produção.
- O **agente de desenvolvimento** que escreve o edge-sync-agent é o mesmo tipo de laço que um eventual **agente de operação** (N4) que decide reiniciar um pipeline. A diferença é só a fonte de verdade (testes vs. telemetria) e o raio de ação (repo vs. planta).

Visão de longo prazo, sem compromisso agora: um agente que **desenvolve** o sistema contra o harness de simulação e, quando o sistema está em produção, **opera** o sistema contra a telemetria real — sempre com humano nos pontos irreversíveis. O caminho pra lá é construir as fontes de verdade primeiro.

---

# PARTE IV — Proposta faseada de aplicação

Pensada pra extrair valor já, com o hardware ainda a caminho.

### Agora (sem o Mini PC) — construir as fontes de verdade

1. **Harness de migrations** — Postgres efêmero em docker; aplica `infra/migrations/*.sql` num banco limpo e valida o schema resultante (em vez de inferir). Resolve a classe de bug das Sprints 0.5/0.6 de uma vez. *Pequeno, alto retorno.*
2. **Synthetic RTSP + esqueleto do `tests/harness/`** — MediaMTX servindo um vídeo loop como câmera fake; um cenário 1 (baseline) e um cenário 5 (multi-tenant isolation) já dão muito sinal. Antecipa parte da Fase 9.
3. **Driver headless L1→L2** — um script que roda Fases 1/2/4 (software puro) em modo headless contra o harness, abrindo PR pra `develop`. Você vê a autonomia funcionando com rede de segurança.

### Quando o PC chegar — ligar a operação real

4. **Telemetria viva** — edge-sync-agent emitindo `edge_heartbeats` reais; painel admin com os sinais vitais do site.
5. **Plano de comandos (N2)** — fila de comandos idempotentes + botões no painel (restart, troca de modelo, ajuste de câmera).
6. **Auto-cura (N3)** — supervisão de processo, watchdogs, circuit breaker de GPU, alerta com diagnóstico.

### Pré go-live RVB — fechar o laço

7. **Cenários de fault injection verdes** — offline-recovery com zero perda, isolamento multi-tenant, hot-swap de modelo. Subset no CI, completo manual antes do go-live.
8. **Runbook de operação remota** — pra cada classe de incidente, a ação remota correspondente; e o subconjunto que (raramente) exige mão física na fábrica.

---

# PARTE V — Riscos, limites e decisões em aberto

- **Não dá pra automatizar o que não dá pra verificar.** Fases 5/6 (DeepStream, TensorRT, GPU Blackwell) não têm fonte de verdade local sem o PC. Autonomia ali é perigosa até o hardware existir; lá o harness é parcial e o humano decide.
- **Autonomia amplifica boas e más decisões.** Um agente em L2/L3 com harness fraco produz lixo verde (passa no teste errado). Investir na qualidade dos cenários é o que separa autonomia útil de dívida automatizada.
- **Comando remoto é superfície de ataque.** A fila de comandos edge↔cloud precisa de device token RS256 com escopo, auditoria e rate limit (trilha S de segurança). Um comando "restart" sequestrado é incidente sério.
- **Custo de operar agentes** — loops autônomos consomem tokens; precisa de orçamento e parada por tarefa.

### Decisões em aberto pra discutir

1. Stack de observabilidade: começar com `edge_heartbeats` + painel admin, ou já plugar Sentry/Grafana?
2. Qual o primeiro cenário do `tests/harness/` a implementar — baseline ou multi-tenant isolation?
3. Nível de autonomia alvo pra Fase 2: rodar headless L1 (revisa cada PR) ou já L2 (loop com auto-retry)?
4. Onde mora o driver autônomo — script local, GitHub Actions, ou um serviço dedicado?
5. Canal de escalonamento pro humano em produção: e-mail, WhatsApp, Slack?

---

## Apêndice — glossário rápido

- **Harness** — laço de verificação automática que dá ao sistema um sinal de "certo/errado" pra ele se autocorrigir.
- **Headless** — rodar o Claude Code sem interface interativa (`claude -p`), pra automação.
- **Fault injection** — introduzir falhas de propósito (derrubar rede, latência) pra testar recuperação.
- **Self-healing** — o sistema se recupera sozinho de falhas comuns sem intervenção.
- **Plano de controle (control plane)** — a camada que observa e comanda o sistema, separada do que ele faz no dia a dia.
- **Idempotente** — rodar a mesma operação 2x dá o mesmo resultado de rodar 1x (essencial pra comandos e migrations).
