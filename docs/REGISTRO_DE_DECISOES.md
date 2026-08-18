# Registro de Decisões — Recognition

> ## 🧊 ARQUIVO CONGELADO — não acrescente aqui
>
> Decisões novas vão para **um arquivo cada** em [`decisions/`](./decisions/):
> `python3 tools/decisoes.py new "Título"`. Convenção:
> [`decisions/README.md`](./decisions/README.md) · Índice:
> [`decisions/INDICE.md`](./decisions/INDICE.md).
>
> **Motivo:** append-only num arquivo só = duas sessões escrevendo na mesma
> região. Deu **3 colisões de `D-` em 3 rodadas** (ver D-114 e D-115, renumeradas
> à força no merge #384).
>
> As 170 entradas `D-` daqui foram copiadas para `decisions/` **por script**,
> corpo verbatim (`tools/decisoes.py split`). **Nada foi apagado** — este arquivo
> permanece íntegro como histórico, inclusive o que não era entrada `D-`
> (constatações e notas de método, que só existem aqui).

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

---

## Rodada 06/08 — pipeline de treino (varredura R2, coleta, bloqueadores da anotação)

### D-67 · 🔴 Mudança de prioridade do produto: detecção + notificação; a GRADE sai de escopo

**06/08 · Vitor**

*"O sistema não precisa de um live view [em grade] — os registros precisam ocorrer
levantando as notificações após identificação de cada cenário pré-treinado. O que
precisamos agora é melhorar a qualidade das câmeras para conseguir realizar a
pipeline de treinamento."* A grade de 8 câmeras — que consumiu quatro rodadas de
investigação — **sai de escopo até o primeiro modelo treinado**. O cliente segue
vendo câmera **de forma unitária**. Decisão de produto, registrada para
rastreabilidade; o ganho colateral de custo está no [[D-70]].

### D-68 · Causa da parada da coleta PROVADA: meta 17 da encenação + parada invisível — e coleta religada em alta

**06/08 · Claude**

Evidência colhida no box + DB DEV (a medição vence):
- **Env efetivo do processo** (`/proc/<pid>/environ`): `COLLECTOR_TARGET_FRAMES_PER_CAMERA=17`
  — a meta da encenação de 31/07, nunca elevada. O histograma do banco fecha a conta:
  662 frames em 31/07, **1 em 02/08 + 16 em 03/08 = exatamente 17** após o restart de
  02/08 06:30, zero desde 03/08 08:48. O coletor **fez o que mandaram**.
- **Parada invisível**: journald do usuário retém **0 B** no box — o
  `collector_target_reached` era gritado para o vazio. Corrigido com drop-in
  systemd (`StandardOutput=append:~/recognition/logs/frame-collector.log`).
- **Agravante (dívida OTA em ação)**: o processo rodava a release `5e32dd0`
  **de um diretório já deletado** — o OTA só recicla `edge-sync-agent`
  (`ota/__main__.py:44`), nunca o coletor. Fix em PR próprio.
- **Surpresa boa**: `RECORDER_STREAM_SUBTYPE=0` — a captura **já estava no stream
  principal** (1080p); os 17 frames pós-restart devem confirmar na triagem. A
  migration de subtype-por-câmera do plano ficou desnecessária por ora.

**Religada em 06/08 20:13**: meta 500/câmera, release atual (`e1811d1`), log em
arquivo, e — pela primeira vez — **as 8 câmeras no channel map** (`cameras=8`,
o processo antigo era anterior ao cadastro das 8 e só coletava a câmera 1).

### D-69 · Correção do D-64 pela medição: os 679 TÊM `camera_id`

**06/08 · Claude**

O [[D-64]] afirmou `camera_id = NULL` nos 679. A consulta ao DEV mostra o
contrário: **679/679 com `camera_id` preenchido** — todos da `RVB Camera 1`
(canal 1), via `/edge/frames` (o coletor edge sempre persistiu). O corte por
câmera do lote atual é trivial (é UMA câmera) e o backfill one-off é
desnecessário. A ressalva do D-64 continua válida **só para o caminho cloud**
(`extract_nvr_frames`, `camera_id=None` por design) — corrigir lá quando/se a
colheita retroativa usar esse caminho.

### D-70 · Custo sem a grade: de ~US$445/mês para unidades de dólar

**06/08 · Claude**

Premissas do estudo (`docs/ESTUDO_CUSTO_INFRA_E_HOSTZERA.md`): ~137 KB/s de
egress por câmera assistida, US$0,05/GB. A projeção de **US$445/mês** era
**25 câmeras × 24/7** (video wall permanente ≈ 8,9 TB/mês). No modelo do [[D-67]]
(câmera unitária sob demanda): 1 câmera × 2 h/dia ≈ 1 GB/dia ≈ **US$1,50/mês**;
mesmo 5 sessões-hora/dia ≈ US$7,40/mês. Clipes de evidência (~5 MB × dezenas/dia)
somam centavos. **Duas ordens de magnitude** — o problema de custo de egress
praticamente desaparece com a grade fora de escopo.

### D-71 · Exceção pontual ao congelamento do `AnnotationInterface.jsx` (PR #317)

**06/08 · Claude**

O cabeçalho "CONGELADO — nunca modificar" protege contra reescrita, não contra
conserto de perda silenciosa de dados. PR #317 fez **3 correções cirúrgicas**:
shape da resposta de criar classe (`data.class` inexistente → classe fake
`Date.now()` que quebrava o save), erro de save de anotação visível (era
`// Silencioso`), erro de load de anotações visível. O congelamento segue
valendo para reestruturação.

### D-72 · LGPD da colheita retroativa: análise entregue + inconsistência RunPod×Vast.ai no contrato

**06/08 · Claude → decisão do Vitor**

Análise em `docs/negocio/ANALISE_LGPD_COLHEITA_RETROATIVA.md` (base legal
candidata: legítimo interesse com LIA documentado; minimização já embutida no
pipeline; tag de sessão/origem ANTES de colher para expurgo em lote; minuta de
aviso aos trabalhadores). **Decisão é do Vitor com a assessoria.**
Achado colateral que trava a cláusula de suboperador: o dicionário do contrato
nomeia **RunPod** (linhas 73/105/138) e o adendo D-33 (04/08) idem, mas o código
aponta **Vast.ai** (`constants.py::GpuProvider.VAST_AI`) — que o próprio registro
descreve como difícil de nomear em contrato. **Confirmar o provedor real antes
de assinar.**

### D-73 · D-66 resolvido: preproc do YOLOX servido corrigido para o contrato stock (PR #320)

**06/08 · Claude**

Investigação fechou o [[D-66]]: o upstream Megvii não faz BGR→RGB nem `/255`
(`yolox/data/data_augment.py::preproc`); **todos** os ONNX servidos ou treinados
pelo produto saem do export oficial (`register_pretrained_models.py` baixa o
binário stock; `training/vast/train_yolox.py` exporta via
`yolox.tools.export_onnx`) — **nenhum modelo depende do preproc errado**, então
o fix é direto, sem knob por-modelo e sem migration. RF-DETR auditado no mesmo
passo: já estava correto (ImageNet mean/std, RGB [0,1], conforme upstream).
Testes agora fixam o contrato certo (0-255, BGR, pad 114 sem normalizar).

---

## Rodada 08/08 — causa medida do congelamento cíclico + edge sai de caixa preta (D-74..D-77)

### D-74 · 🔴 Causa medida do congelamento cíclico do live view: uploader em rodízio (banda nunca foi o problema)

**08/08 · Claude**

- Uploader sequencial single-thread: `services/edge-sync-agent/app/live_view/live_view_loop.py:138-141`
  (for câmera a câmera), POSTs síncronos bloqueantes (:198, :226) num `httpx.Client()` compartilhado
  (:87), timeout 10s/request (`segment_pusher.py:24`).
- Ciclo medido no Railway (POST /segment, 01:21:24→01:21:50Z): as 8 câmeras visitadas em rodízio, ciclo
  ≈19s; um POST de 0,770s (câmera `2a683620`) contra 0,03s das demais.
- Segmento vivia 3s no disco (`hls_time 1` × `hls_list_size 3` + `delete_segments`) → ~16 de cada 19
  segmentos apagados antes de qualquer tentativa de envio. **Perda por projeto, não por congestionamento.**
- Rede medida no box: 37 Mbps entrando do gravador, 14 Mbps saindo pra nuvem; link RVB 726 Mbps down /
  401 Mbps up (speedtest com serviço parado) — uso de 3,5% da subida. **A internet da RVB tem 11× mais
  banda do que o sistema precisa.**
- Correção: push paralelo por câmera com teto configurável (`LIVE_VIEW_MAX_PARALLEL_PUSHES`, default 8),
  isolamento de câmera lenta, janela `hls_time 2` × `list_size 10` (20s de vida). Hipóteses mortas nesta
  rodada: banda da RVB, CPU do box (~4% em 2 dias), psycogreen sozinho ([[D-61]]).

### D-75 · Amplificador: TTL do Redis (20s) empatava com o ciclo do rodízio (19s)

**08/08 · Claude**

- `services/api/app/api/v1/edge/routes.py:87`: segmento subia e expirava da nuvem na iminência da visita
  seguinte do uploader ([[D-74]]); a playlist anunciava segmentos mortos → 425 permanentes em índices
  fixos (`stream242.ts`, `stream188.ts`) + congela-e-volta a cada ~15s no navegador (o sintoma relatado).
- Correção: `_HLS_SEGMENT_TTL` 20→30s (> janela de 20s anunciada pelo edge). Atenção: `SEGMENTS_REDIS_URL
  == REDIS_URL` no DEV (Redis compartilhado) — regime estimado ~140MB de segmentos; monitorar.

### D-76 · Edge era caixa preta: journald volátil e ilegível — log em arquivo pela unit

**08/08 · Claude**

- Achado: `/var/log/journal` ausente (`Storage=auto` → volátil em `/run/log/journal`, dir
  `root:systemd-journal`, `pandora` sem leitura) → `journalctl --user` vazio. Sem sudo não conserta o
  journald.
- Correção sem sudo: `StandardOutput`/`StandardError=append:%h/logs/edge-live-view.log` +
  `edge-log-rotate.timer` (copytruncate, gatilho 50MB). Comandos sudo pro journal persistente guardados
  no runbook (`docs/runbooks/edge-sync-agent-deploy.md` §Logs do edge) — decisão do Vitor: rodar quando
  quiser. Telemetria remota continua desligada (tema separado,
  `docs/edge/DIAGNOSTICO_OBSERVABILIDADE_2026-07-21.md`).

### D-77 · Os 8 ffmpeg 24h: o sob-demanda JÁ existe — há espectador contínuo

**08/08 · Claude**

- LV-3 funciona: ffmpeg para quando `epi:stream:{camera_id}:active` expira — TTL `HLS_VIEWER_TTL` default
  90s (`services/api/app/api/v1/cameras/stream_handlers.py:50`), renovado a cada fetch do player (:483).
  Logo 8 ffmpeg contínuos ⇒ espectador ~contínuo (provável: monitor do embarque RVB com a grade aberta).
- Ingestão 37 Mbps é LAN local (custo ~zero; CPU do serviço ~4%); o custo real (upload pra nuvem) já é
  sob demanda. Partida a frio estimada em 4-6s (probesize 32 + primeiro segmento preso ao GOP + settle 1s
  + push + gate da playlist). **Decisão: manter como está.**
- Decisões da mesma conversa (2026-08-08, Vitor): MediaMTX pro argv do ffmpeg **ADIADO** (redação de log
  já estanca o vazamento; mexer no caminho de captura de 8 câmeras estáveis não vale o risco agora);
  rotação da credencial segue **ADIADA**; troca pra `subtype=1` é decisão de custo separada, fora desta
  rodada.

### D-78 · Verificação da rodada D-74/D-75: números finais (antes → depois)

**09/08 · Claude**

- Deploy: PRs #325 (TTL 30s), #326 (logs), #327 (redação), #328 (push paralelo), #329 (fixup unit),
  #330 (playlist consistente) mergeados na develop; box RVB via OTA em `b75b37dc`, restart na janela
  autorizada (sábado ~22h30+).
- **Ciclo por câmera: ~19s → 0,8s** (mediana; p95 3,2s; 11.992 pushes, 8 câmeras, janela de 20 min).
- **Upload no NIC: 14 → 37,3 Mbps** (mediana; = o que o gravador entrega — zero perda por projeto).
- **Pushes aceitos: 11.996×201, 4×503** (0,03% falha, reabsorvida no tick seguinte).
- **425 no navegador: 2286 (17% das requests, contínuo) → 32, TODOS nos ~8s da junção fria** — zero em
  regime nos 20 min. A correção decisiva foi o #330: a decisão do gate era tomada na LISTAGEM mas os
  bytes da playlist eram lidos no PUSH — o ffmpeg atualizava o `.m3u8` no meio do job e a nuvem anunciava
  segmento que só subia ~1,7s depois (mediana medida da latência 425→200). Snapshot na listagem +
  truncamento do rabo ao prefixo já enviado = "anunciou ⇒ está no Redis" por construção.
- **Soaks (Playwright, 20 min cada, 8 câmeras, frontend DEV)**: zero navegação p/ /login, zero 401,
  cada player tocou ≥98,9% do tempo. Resíduo honesto: 2-3 eventos de 4-8s SINCRONIZADOS entre todos os
  players por soak, coincidindo com janelas de silêncio TOTAL de HTTP no navegador — e o log do box
  mostra push contínuo (10-15/s) nos mesmos segundos de parede. Veredito: caminho cliente↔Railway
  (Wi-Fi/conexão local do espectador), fora do sistema. Mitigação possível (tema futuro, custo =
  latência): aprofundar buffer do player (`liveSyncDurationCount`) + `hls_list_size` maior.
- Harness: Chromium bundled do Playwright NÃO decodifica o HEVC das câmeras (ver D-79) — soak roda
  headed com `channel: 'chrome'`. Primeira rodada headless "passou falso o portão inverso" (tráfego
  pleno, playback zero).

### D-79 · Stream principal das câmeras RVB é HEVC (H.265) — navegador sem decode de HW vê grade preta

**09/08 · Claude**

- Medido no NVR (canal 8, `subtype=0`): **hevc (Main), 1920x1080, 30 fps**. Com `-c:v copy` o HEVC
  atravessa o pipeline inteiro até o MSE do navegador.
- Chrome com decode por hardware (macOS VideoToolbox, Windows moderno) toca; **Chromium puro, Firefox e
  Linux sem VAAPI não tocam** — tráfego HLS integral com `currentTime` parado em 0 (grade preta sem
  erro). Explica também por que o harness headless não serve de espectador aqui.
- Reforça a decisão pendente do `subtype=1` (substream costuma ser H.264, universal) — além do custo de
  egress, há compatibilidade de navegador em jogo. Decisão segue com o Vitor (fora desta rodada).

---

## Rodada 10/08 — anotação destravada de ponta a ponta (D-80..D-84)

### D-80 · Anotador legado DELETADO por medição (não congelado)

**10/08 · Vitor (critério) + Claude (medição) · ✅**

Critério do Vitor: zero anotações de vídeo → deletar; uso real → congelar com prazo. A medição
no DEV fechou a questão: **0 frames com `video_id`, 0 anotações de vídeo, tabela `videos`
inexistente em `public`** — o modo vídeo nunca teve um dado. `AnnotationInterface.jsx`
(1.163 linhas, "congelado" desde D-71), o wrapper morto e o branch `video_id` da galeria saíram
no PR #334. Todo clique abre o **AnnotationStudio** novo (TSX, teclado-primeiro). Fim do risco
de dois anotadores para sempre.

### D-81 · Inventário R2: acervo RVB 100% íntegro · pesos SAM/DINO NÃO estão no R2

**10/08 · Claude · ✅ (PR #333, relatório `docs/quality/r2-inventory-2026-08-10.md`)**

7.241 frames no DB no momento da varredura: **7.151 com objeto que baixa (98,8%)**; os 90
faltantes são TODOS do tenant `e2e-fase-a-validation` (upload de 12/07) — **nenhum frame da RVB
está perdido**. GET de prova 30/30. 17 órfãos no R2 (janela upload↔linha da coleta ativa).
O "frame não encontrado" que abriu esta frente era a soma #313 (posse por tenant de casa) +
#322 (erro de R2 mascarado como 404) — ambos já corrigidos e agora provados por inventário.
Bucket inteiro varrido (7.168 objetos): **nenhum peso de modelo** (`.pth`/`.onnx`/sam/dino).
A lembrança de pesos "numa aba do epi-monitor" não corresponde ao bucket; o serviço
`pre-annotation` espera baixá-los por env (`PREANNOT_*_CHECKPOINT`) sob demanda (D-38).

### D-82 · O percurso e2e pegou o que 276 testes verdes não pegaram: useToast instável → 429 em cascata

**10/08 · Claude · ✅ (PR #335)**

Suíte inteira verde + tsc limpo, e mesmo assim a tela caía no 2º frame do percurso real:
`useToast()` devolvia **objeto novo a cada render**; em array de dependência de
useCallback/useEffect, o fetch de classes redisparava em loop na velocidade da latência, o
bucket do flask-limiter esgotava e o **429 derrubava classes + save + load de caixas juntos**.
Fix sistêmico: `useMemo` no retorno do hook (estabiliza estúdio, galeria e página de classes de
uma vez) + estado de erro com retry no painel. **Regras que ficam:** hook utilitário devolve
identidade estável; **tela nova só entrega roteiro depois do percurso e2e andado** — é a 3ª vez
que o caminho real acha o que a suíte não achou.

### D-83 · Teto conhecido do anotador: `<img>` + overlay de div — registrado, não resolvido

**10/08 · Claude · 📌 para a onda das 500**

A arquitetura atual (imagem em `<img>`, caixas como divs absolutos) está **certa**: mata o CORS
como bloqueio e serve bem até dezenas de caixas. O teto: com **zoom alto + muitas caixas por
frame**, overlay de div degrada (reflow por caixa, imprecisão subpixel na borda). Sinal de
troca: arrasto de caixa perceptivelmente lento com >30–50 caixas/frame ou zoom >4×. Rota quando
chegar lá: camada `<canvas>` **só para o render das caixas** (imagem continua `<img>` — o CORS
não volta). Não mudar antes do sinal.

### D-84 · Classes RVB unificadas · ordem de teclas por frequência · os 500 da propagação já existem

**10/08 · Vitor (decisões) + Claude (execução) · ✅**

- "**Protetor auditivo**" fica (termo da NR-6); as 5 caixas de "Protetor auricular" foram
  **reapontadas** (nada apagado) e "Protetor auricular" + "incluir blur" **arquivadas** —
  `scripts/ops/unify_classes_rvb.py` (env-gated, idempotente).
- **Ordem 1–4 por frequência** (dedo viaja menos × 500): 1=Protetor auditivo (7 caixas),
  2=Sem protetor de ouvido, 3=mascara, 4=Sem mascara; catálogo global depois. Reordenar pela
  tela de Classes muda a tecla — o Vitor confirma na tela.
- Pendência micro: **1 caixa** ainda aponta para "incluir blur" (arquivada) — preservada de
  propósito; revisar o frame pela tela.
- Para a próxima onda, registro: **os 500 da propagação já existem** — acervo em ~7,5k frames,
  8 câmeras, coleta ativa. Não há mais espera por acúmulo.

---

## Rodada 11/08 — inventário dos 32 canais do gravador (D-85)

### D-85 · iNVD 3032 inventariado: 29 canais ocupados, 21 câmeras novas, substream 100% H264 — inventário, NÃO ativação

**11/08 · Claude (sondagem do Orin) · ✅ inventário concluído · 🛑 ativação = decisão do Vitor, por aditivo com a RVB**

- **Como:** ONVIF `GetProfiles` via media2, do Orin (nunca da nuvem, ADR-0020), ~20h20 (fora do
  horário de operação). Protocolo anti-lockout cumprido: **1 credencial validada 1×, 34 chamadas
  SOAP sequenciais com pausa de 4 s, zero 401/403, somente leitura** — nada ativado, nada
  cadastrado, nenhum stream/snapshot baixado. Valida a ADR-0052 em hardware real pela 2ª vez.
- **O que tem lá:** **29 de 32 canais ocupados** (30–32 livres). Canais 1–8 = as 8 contratadas
  (§8 do dicionário). **Canais 9–29 = 21 câmeras além do contratado** — batem com as ~21 do
  WS-Discovery de 04/08; agora sabemos que estão plugadas neste gravador. Sem evidência de troca
  ou mudança de posição das 8 (canais 1–8 seguem H265 1080p30, compatível com D-79; pareamento
  canal↔posição física segue pendente para todos os canais).
- **Codec (o achado):** principal = 25× H265 (21× 1080p, 4× **2560×1440** nos canais 26–29) e
  4× **H264** (canais 13/15/16/17). A hipótese "as novas são H264" não se confirmou. Mas
  **o substream é H264 704×480@30 uniforme nos 29 canais** — a grade preta do D-79 é problema
  exclusivo do principal; `subtype=1` toca em qualquer navegador, em qualquer canal. Fortalece a
  troca da grade para substream (decisão segue com o Vitor).
- **Capacidade com 29:** principal ~119–134 Mbps + sub ~22–30 Mbps ≈ 35–41% do link de 400 Mbps
  (cabe); egress da grade 8h/dia ~**US$ 545/mês** (vs ~US$ 150 com 8, linear — bitrate igual em
  todos os canais, 4096k/1024k). **Sobe junto, antes de qualquer ativação:**
  `LIVE_VIEW_MAX_PARALLEL_PUSHES` (default 8 → rodízio volta) e bucket dedicado pro
  `POST /segment` (piso de 900/min/IP estoura com ~10 câmeras; 29 ≈ 2.610 req/min). **Pergunta
  aberta registrada, não medida:** inferência no Orin >8 streams — decide 1 Orin ou 2.
- **O lado bom:** 21 câmeras novas = a **coleta multi-câmera** que falta para a volta 2 (o pool
  de 31/07 é de 1 câmera só, D-68). Indícios de ângulo/área novos: canais 26–29 são 4MP (outra
  geração de hardware) e 13/15/16/17 outro lote (H264). Mapear canal→área com a RVB é o próximo
  passo — ângulo diferente vale mais que câmera a mais no mesmo lugar.
- **Regra que fica:** *"visibilidade técnica não implica autorização de uso"* — ativar **quais**
  e **quando** é decisão comercial (aditivo), com a tabela na mão: *21 câmeras a mais, ~US$ 545/mês
  de egress em grade 8h/dia, cabem no link, exigem 2 ajustes de software + 1 medição no Orin.*
  Relatório completo: `docs/edge/INVENTARIO_INVD_3032_2026-08-11.md`.

---

## Rodada 11/08 (noite) — as 21 entram como draft (D-86)

### D-86 · 21 câmeras cadastradas como draft · retenção do NVR é ~4,3 dias (a reextração de 31/07 já era) · coleta ganha eixo próprio de qualidade

**11/08 · Vitor (decisão) + Claude (execução) · ✅ cadastro executado no banco · 🛑 ativação = triagem do Vitor, pós-aditivo**

- **Decisão do Vitor:** *"pode incluir todas as câmeras novas que eu vou tirar as que não
  fazem parte do reconhecimento."* Executado no banco de **Desenvolvimento**: **21 câmeras
  (canais 9–29) cadastradas em lote**, todas `is_active=FALSE` — o estado *draft* que já
  existia (mesmo do import admin). Draft fica **fora do channel_map** que o ConfigPoller
  manda pro box ⇒ não transmite, não coleta, não infere (provado por consulta: 8 ativas,
  21 drafts, 0 sem site_id, 0 sem credencial). Credencial Fernet **copiada por
  INSERT..SELECT da câmera do canal 1 dentro do próprio banco** — plaintext nunca tocado;
  `site_id` herdado das 8 (sem ele a câmera é invisível pro edge). Idempotente: 2ª execução
  = 0 inseridas, 21 puladas. Script: `scripts/ops/import_nvr_channels_rvb.py` (PR #353,
  com a migration **113** `position_confirmed`).
- **Bloco 0 antes do cadastro** (PR #352): bucket dedicado `edge-live-ingest` pro
  `POST /segment` — **3.600/min** (32 canais × ~90 req/min + 25% de folga; sem ele o piso
  anônimo de 900/min estourava com ~10 câmeras e o 429 imitaria o congelamento de
  #325–#331) — e `LIVE_VIEW_MAX_PARALLEL_PUSHES` **proporcional ao site** (câmeras+2,
  piso 8): teto fixo envelhece. Prova: 29 câmeras ≈ 2.610/min (27% de folga); 32 ≈ 2.880
  (20%).
- 🔴 **Retenção do iNVD medida: ~4,3 dias** (FindRecordings: canal 1 main, earliest
  2026-08-07T15:41Z). **A encenação de 31/07 em 1080p JÁ FOI SOBRESCRITA** — a
  "oportunidade com prazo" expirou antes da rodada. **Regra que fica: material bom no
  disco do NVR tem ~3 dias úteis de vida — é extrair imediatamente ou perder.** (Vale
  para a próxima encenação: reservar a extração para o MESMO dia.)
- **Qualidade em DOIS eixos por câmera** (pedido do Vitor): OPERAÇÃO já existia
  (fps_target/quality_preset/live_view_subtype); nasce o eixo COLETA —
  `cameras.collection_subtype` (migration **114**), **default 0 = stream principal**:
  coleta é foto, custo ~zero, e 📌 **anotar em alta é melhor mesmo que o treino rode em
  baixa** — coordenada é normalizada; caixa precisa em 1080p continua precisa depois do
  downscale, caixa imprecisa em 480p é imprecisa para sempre. O edge aplica por câmera só
  no `capture_frame` (live view segue global/substream). UI avisa o desalinhamento
  (treino nítido × operação borrada → augmentation: downscale/blur/compressão no treino).
- **Resolução por frame: já estava resolvido desde a migration 094** — o upload grava
  width×height (PIL). Auditoria do acervo: **8.667 frames, 100% com resolução** (1.432
  cheios 704×480 + 7.235 crops de pessoa, tudo source=nvr) — **zero** a recuperar do R2.
- ⚠️ **Achado da auditoria de coleta: a cota re-arma a cada restart do coletor**
  (contador em memória, documentado no próprio collector_loop; visível no acervo: ~3,7k
  frames em 07/08 e de novo em 10/08 = cota 1000/câmera × 8 re-armada). Com 29 câmeras
  vira até **29k frames por restart**. Storage não é o problema (~2,3 GB/ciclo ≈
  US$ 0,03/mês no R2) — **acervo que ninguém anota é**. Persistir o contador (ou virar
  cota diária) é pré-requisito antes de ligar coleta nas 21. Coleta nas novas **NÃO foi
  ligada** (decisão do Vitor, com estes números).
- **Tela de triagem dos 29 canais** (PR próprio): preview **UM por vez** (draft ativa
  temporário e reverte ao fechar — ativar as 29 juntas é ~130 Mbps + 29 decodes HEVC),
  lote ativar/**arquivar** (nunca apagar), renome em linha ("Canal N" → nome de lugar),
  badge **"posição não confirmada"** para TODAS até o walkthrough (nem as 8 originais
  foram conferidas).

---

## Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha

> Numeração: D-85..D-88 estão sendo reivindicados por DOIS PRs abertos ao mesmo tempo
> (#343, rodada RunPod, e #354, inventário iNVD/rodada das 21). Esta rodada começa em
> **D-89** para não piorar a colisão — reconciliar quando os dois PRs landarem.

### D-89 · Prática do ledger: NÃO aplicar migration fora do runner

**12/08 · Vitor (prompt) + Claude (guarda) · ✅ (PR #360)**

A migration 113 foi aplicada com `psql -f` do arquivo versionado, mas **fora do runner** — não
entrou no ledger do DEV. Benigno neste caso (`ADD COLUMN IF NOT EXISTS` faz no-op e converge no
deploy), mas o padrão é o problema:

⛔ **Não aplicar migration fora do runner em ambiente que o runner gerencia.** O ledger é o
registro de o que foi aplicado onde; aplicação fora dele faz o ledger **mentir sobre o estado
do ambiente** — e a próxima pessoa que raciocinar a partir dele raciocina errado. É o C-04
aplicado ao banco. Se a coluna é necessária agora, faça o deploy — **a pressa de "preciso dela
já" é o que cria a deriva.** Se for inevitável, **grave a entrada no ledger junto**: migration
aplicada sem registro é estado invisível.

**Resposta à pergunta da rodada — o runner detecta?** Antes do PR #360, **não avisava em
nenhum caso**: no modo legado, "already exists" é tolerado por heurística todo boot (passa
batido por design); no modo ledger (`MIGRATIONS_LEDGER_CUTOVER=1`), migration idempotente
aplicada fora reaplicava como no-op e **convergia em silêncio**, e migration não-idempotente
**derrubava o boot** (`SystemExit(1)` em "already exists" desconhecido) — o caso benigno era
invisível e o ruim virava outage, nunca aviso. **Agora** (PR #360): primeira aplicação segundo
o ledger num banco estabelecido que gera `NOTICE ... already exists, skipping` → **WARNING de
possível deriva no startup**. Limite honesto: só statements `IF NOT EXISTS` emitem NOTICE.

### D-90 · Contador de cota persistido + interruptor durável de coleta

**12/08 · Claude · ✅ (PR #358) — fecha o buraco operacional apontado no D-86**

O contador `frames_uploaded` do coletor vivia em memória e **re-armava a cota a cada
restart** — prova viva no acervo: RVB Camera 1 com **1.679 frames** para alvo de 1.000.
Com a campanha das câmeras novas isso viraria multiplicador de custo. Agora:

1. **Contador persistido** em `collector_state.json` (`COLLECTOR_STATE_PATH`, mesmo diretório
   e disciplina do `config_cache.json`): carregado no boot, salvo por rajada, atômico,
   best-effort. No deploy do box, o arquivo é **semeado com as contagens reais do banco** —
   partir de zero re-daria cota cheia às 8 câmeras antigas.
2. **`COLLECTOR_ENABLED=0` no .env** = desligado durável: o processo sobe, avisa em WARNING e
   fica ocioso sem abrir nenhuma conexão. **Sobrevive a restart e reboot** — "a cota bateu"
   (memória) e `systemctl stop` (unit habilitada religa no reboot) não são desligamento.
   É o mecanismo do "parar TUDO para treinar" pós-campanha.

### D-91 · Campanha de captura das câmeras novas: orçamento, não cota por câmera

**12/08 · proposta Claude, número a confirmar com Vitor · 🔄**

Acervo real em 12/08: **8.757 frames, 345 anotados** (~4%). Acervo que ninguém anota não é
dado, é custo — a cota herdada (500-1000/câmera × 21 novas) geraria 10-21k frames, mais que
dobrando o acervo sem dobrar capacidade de anotação.

**Proposta: 150 frames/câmera nova, liberados em 3 janelas de 50** via
`COLLECTOR_TARGET_FRAMES_PER_CAMERA` (50 → 100 → 150, um restart barato entre janelas agora
que o contador persiste): manhã, meio-dia, fim de tarde. **Variedade de luz vale mais que
quantidade** — é exatamente o que o pool de 31/07 (uma câmera, uma janela) não tem. Teto se as
21 ficarem: **~3.150 frames** (+36% do acervo). As 8 antigas (988-1.679 cada) ficam paradas
pela cota semeada.

⛔ **Coleta só nas câmeras que o Vitor marcar na triagem** (`/epi/cameras/triagem`): draft
(`is_active=false`) não entra no channel_map do config poll — a trava é estrutural, não
convenção. Sequência: deploy → Vitor tria e nomeia → captura liga. Janela da campanha
combinada com o Vitor antes (⛔ não saturar o gravador — ele grava a fábrica).

### D-92 · Coleta contínua pós-v1: por incerteza + amostra aleatória (desenho, NÃO construído)

**12/08 · desenho registrado · ⏸ depende do modelo v1 existir**

A intuição do Vitor ("diminuir a captura e deixar o modelo se retreinar com cenários novos")
está certa, com um ajuste: o ganho não vem de coletar menos, vem de coletar MELHOR.

- **Hoje (sem modelo):** coleta ampla por amostragem — não há como saber o que é útil.
- **Depois do v1:** toda detecção vira candidata; guardar e anotar as de **baixa confiança**
  (active learning) — mesmo esforço humano rendendo várias vezes mais. Ciclo:
  `coletar → anotar → treinar → detectar → coletar onde errou → …`
- ⚠️ **Ressalva:** só incerteza concentra o dataset em poucas situações parecidas. **Misturar
  com amostragem aleatória** — câmeras diferentes, horários diferentes.
- O schema já espera por isso: `training_frames.uncertainty_score` e `priority_rank` existem
  desde a migration de active learning (011). O gatilho de construção é o v1 treinado — nada
  a construir antes.

### D-93 · Propagação semeada roda no EDGE por padrão (DEV) — guard de datas chaveia por destino

**11/08 · Vitor (decisão) + Claude (execução) · ✅**

Até aqui, a propagação semeada (DINOv2+SAM, "buscar imagens iguais") só rodava em pod RunPod
(nuvem de terceiro) — por isso as **216 anotações de operação real** (não-encenação) nunca
puderam virar semente: o guard fail-closed de datas existe especificamente porque a imagem
SAI da Logikos rumo a uma GPU de terceiro, e mandar footage real de cliente pra fora nunca foi
aceitável. Decisão: **rodar no Jetson do próprio site por padrão** (DEV) — como a imagem nunca
sai do site, a razão de ser do guard deixa de existir e o acervo de operação vira semente
válida. RunPod continua existindo, só que agora para **treino**, não mais como único destino
da propagação.

- **Guard por DESTINO, nunca por flag.** `app/constants.py::OFFSITE_PROVIDERS`
  (`runpod`/`vast_ai`/`colab`) vs `ONSITE_PROVIDERS` (`edge`/`local`) — união cobre o
  `GpuProvider` inteiro, checada na IMPORTAÇÃO do módulo (um provider novo sem classificação
  derruba o boot, fail-closed, nunca passa despercebido). `propagation_jobs.gpu_provider`
  (migration 116) grava o provider RESOLVIDO na criação; o **guard de datas**
  (`domain/services/propagation_pool.py::validate_pool_frames`, parâmetro
  `enforce_date_guard`) só se aplica quando offsite — tenant/câmera/r2_key continuam validados
  sempre, nos dois destinos (só a checagem de `captured_at` é que cai).
- **Rechecado no DISPATCH, não só no create.** `dispatch_propagation` relê `gpu_provider` DO
  JOB (nunca confia no que foi decidido na criação) — um job criado como edge cujo provider
  fosse trocado pra `runpod` entre os dois momentos faz o guard de data valer de novo e abortar
  sozinho, ao invés de mandar silenciosamente pra nuvem de terceiro o que só foi aprovado pro
  onsite. Testado nos dois sentidos (par obrigatório): job edge com frame de data de operação
  passa create+dispatch; o MESMO job com `gpu_provider` trocado pra `runpod` aborta no dispatch.
- **Resolução do provider:** `provider` explícito no request > env `PROPAGATION_GPU_PROVIDER` >
  default `runpod` (retrocompat — nenhum tenant que já usa a nuvem de terceiro muda de
  comportamento). DEV passa a ter `PROPAGATION_GPU_PROVIDER=edge` como configuração de
  ambiente, não como mudança do default de código.
- **Dispatch pro edge** vira um `edge_commands` (`command_type='run_propagation'`) pro site do
  tenant — resolvido automaticamente se houver exatamente 1 `edge_site` `status='active'`;
  zero sites ou mais de um exige `site_id` explícito no create (erro legível, nunca um palpite).
  O `edge-sync-agent` (`command_poller.py`) lança o MESMO executor
  (`training/propagate_seeded.py`, sem nenhuma mudança de lógica) como uma unit
  `systemd-run --user --scope`, orçada (`MemoryMax=6G`/`CPUQuota=400%` — live view do box nunca
  pode ser espremido). Envs (inclusive `CALLBACK_TOKEN`) só existem num arquivo `0600`, nunca em
  argv/log — `systemd-run --scope` não injeta ambiente (não tem `ExecStart`/`Environment=`
  próprios, herda do processo que o invocou), então o lançamento é um wrapper
  `bash -c 'set -a; . env; exec python executor'`.
- **Landmine real do box (achado do agente de hardware, mesma task):** a wheel torch 2.11
  jp6/cu126 precisa de `LD_LIBRARY_PATH` apontando pro `nvidia/cu12/lib` do venv +
  `/usr/local/cuda/lib64` ANTES de `import torch`, senão `libcudss.so.0: cannot open shared
  object` mesmo com `nvidia-cudss-cu12` instalado — registrado em
  `docs/edge/REGRAS_PLATAFORMA_JETSON.md` §3.5, replicado no arquivo de env que o
  `command_poller.py` escreve (`_derive_ld_library_path`, descoberto via `glob` no venv real).
  Números medidos no box: DINOv2 forward 0,39s + SAM predict 2,57s por imagem 704×480, pico
  CUDA 2,9GB, GPU 99%, live view intocado com o budget acima.
- **Sem watchdog Celery bloqueante** pro edge (diferente do RunPod) — o job fica `running` e a
  conclusão chega assíncrona via callback HTTP do próprio executor no box. Timeout honesto:
  `tasks/gpu_reconciler.py::reconcile_edge_propagation_timeouts` (beat, 5 min) marca `failed`
  um job `running` há mais que `EDGE_PROPAGATION_TIMEOUT_SECONDS` (default 7200s = 2h) sem
  callback final — não há pod pra matar, só honestidade de estado.
- **UI:** `PropagationStatusBar`/`SimilarSearchPanel` mostram "processando no equipamento da
  fábrica — as imagens não saem do site" e escondem custo/GPU quando `gpu_provider` é onsite
  (exposto no GET do job e no preflight). Fases de preparo (cold start de GPU, carregar modelo)
  colapsam numa única "Preparando referências (N caixas)" — sem cold start no box. **Desvio
  documentado do desenho original de 4 fases:** o executor não emite nenhum stage de "refino"
  separado — a UI nunca inventa uma fase sem sinal real por trás.
- **Migrations 116** (`propagation_jobs.gpu_provider`, `ADD COLUMN IF NOT EXISTS`) — sem
  colisão de numeração (115 era a última no momento).
- **Segue pendente / follow-up sugerido:** ADR dedicado (padrão da casa) se o Vitor quiser o
  "porquê longo" documentado à parte deste registro.

### D-94 · Propagação no edge RODOU DE VERDADE no Orin — medida, com live view ligado

**11/08 (noite) · Claude (execução e medição) · ✅ números reais, decisão de operação é do Vitor**

Dois jobs reais processados no box (DEV, tenant RVB, câmera 2a683620, frames de 11/08 —
**data de operação**, exatamente o que o provider edge desbloqueia), pool de validação de
**8 frames** (3 sementes/9 caixas + 5 alvos), propostas no banco via callback:

| Métrica | Medido |
|---|---|
| **Tempo total por execução** | run 1: **49,9s** · run 2: **46,8s** (8 frames cada) |
| **Por frame (fase pool)** | **≈3,3–4,0 s/frame** (SAM AMG + embeds DINOv2 + callback por frame) |
| Carga fixa por execução | pesos (R2+Meta, sha256 verificado): 6,4–8,3s · modelo+sementes: ~12s — **toda execução repaga** (o executor sempre rebaixa e reverifica os pesos, por desenho) |
| Pico de RAM do job (cgroup) | **2,1 GB** (MemoryMax=6G nunca pressionado) |
| Pico de GPU | GR3D **99%** em rajadas (25 amostras >20% em ~50s) |
| RAM do sistema no pico | 7,4 GB de 15,6 GB (MemAvailable nunca abaixo de **8,4 GB**) |
| **Impacto no live view (MEDIDO)** | POST /segment/min: **55,6 antes · 56,3 durante · 57,4 depois** — flat; **zero** respostas não-201; viewer sintético ativo pelo fluxo tokenizado durante todo o run 2 |
| Propostas | 1 proposta/run ("Botas", confidence 0,71) em `pre_annotations` — **fila de proposta, zero linhas em `frame_annotations`** |

**Projeção para 662 frames** (número do Vitor): 662 × 3,3–4,0s + ~15s de setup ≈ **37–45 min**,
**com o live view ligado** (impacto medido: nenhum) e dentro do timeout default de 2h.
Régua do prompt: ficou entre o cenário "~1s/frame · roda quando quiser" e "~5s/frame · roda com
live view parado" — pelo medido, **não precisa parar o live view**. A decisão é do Vitor.

**Falha legível do LD_LIBRARY_PATH (testada forçando caminho errado):** job 3 rodou com
`LD_LIBRARY_PATH` quebrado de propósito → `error_reason` na tela:
*"não foi possível carregar o modelo no equipamento da fábrica — biblioteca CUDA não encontrada
(libcudss.so.0). Caminhos de busca (LD_LIBRARY_PATH): /caminho/errado/... Ver
docs/edge/REGRAS_PLATAFORMA_JETSON.md §3.5"* — nunca mais traceback cru
(`humanize_startup_error`, commit e35739e).

**Quebras encontradas no caminho (cada uma corrigida e testada):**
1. **`pip install` incondicional do executor** clobberaria o torch jp6 do venv do box (wheel
   SBSA → iGPU morta, REGRAS §3.1/§3.5) → `ensure_dependencies()` instala só o que falta.
2. **`WORK_DIR=/root`** não é gravável no box (systemd --user) → override por env.
3. **🔴 URL presignada com `&` + wrapper `source` bash = env perdida em silêncio**
   ("MANIFEST_URL não definido" com o arquivo presente). Fix estrutural (commit 85739a5):
   lançador virou **serviço transiente com `-p EnvironmentFile=`** (systemd lê literal, sem
   shell, e é detached — não bloqueia o poller). Ack `failed` de `run_propagation` agora
   também derruba o job na hora (sem esperar o reconciler de 2h).

**O que foi contornado (e o que deixou de acontecer):** o box roda um release INTERMEDIÁRIO do
edge-sync-agent (variante `--scope`+source, anterior ao fix) — os lançamentos medidos foram
feitos manualmente com o MESMO `systemd-run`/budget/env-file 0600 que o handler corrigido usa;
o polling nativo do box tentou executar os mesmos comandos, falhou no bug do `&` (exit 1) e
ackou `failed`. O elo comando→launch nativo fim-a-fim ainda NÃO foi provado com o código
corrigido.

**🛑 Trava operacional até o próximo release OTA do box:** com o release atual, TODO job edge
criado no DEV será tentado nativamente pelo box, falhará no launch e o ack `failed` derrubará
o job (comportamento honesto, mas mata o job antes de qualquer execução manual). **Não criar
jobs de propagação edge no DEV até o box receber release ≥ 85739a5** — e esse release precisa
incluir o executor corrigido (e35739e), senão o `pip install torch` incondicional do executor
antigo quebra a iGPU do venv.

**Dívidas pequenas registradas:** callback_token não é revogado após estado terminal no
caminho edge (RunPod revoga; edge fica na coluna até sempre) · o executor rebaixa ~460MB de
pesos por execução (cache local por sha256 pouparia banda em lote grande).

### D-95 · Cota do coletor PROVADA: trava a CAPTURA (não só a contagem) — banco, R2, log e rede imóveis

**12/08 · Claude (medição passiva, DEV/RVB) · ✅ provado**

Medo específico do Vitor: *"câmera que bateu 1.000 não pode continuar mandando para o R2 —
parar de contar e continuar subindo seria pior que não ter cota"*. **Descartado com prova
empírica de ~9h** (janela natural, mais forte que os 30 min planejados):

| Evidência | T0 (11/08 23:10) | T1 (12/08 08:30) |
|---|---|---|
| Banco por câmera (8 originais, source=nvr) | 8.667 (988–1.679 cada) | **8.667 — idêntico, câmera a câmera** |
| Contadores no state file (8 originais) | 988–1.679 | **idênticos** |
| R2 `training-images/{tenant}/nvr/` | 9.000 objetos | 9.724 — crescimento **casado 1:1 com frames novos do banco, zero das 8** |
| Log (delta 4.520 linhas) | — | **0 linhas `collector_*` para os 8 UUIDs** vs 150–330/câmera nova (controle positivo: mesmo processo capturando ao lado) |
| Sampler 35 min (2s, fase 100% congelada) | — | **0 filhos ffmpeg, 0 conexões** do coletor (captura spawna ffmpeg — sem processo, sem RTSP) |

O pulo é **antes de abrir RTSP** (`collector_loop.py:275-276`); upload é síncrono, sem
fila/retry (`frame_uploader.py:31-67`) — não existe caminho de subir sem contar. State
(9.333) = linhas do banco (9.333), exato.

**As 3 perguntas da campanha (D-91):**
1. **Subir alvo reativa?** Sim, mecanicamente: `contador < alvo` reavaliado por tick; alvo é
   lido do env **uma vez no boot** → **cada troca de janela (50→100→150) exige restart da
   unit**. Corte exato no teto — hoje de manhã **10 câmeras novas pararam EXATAMENTE em 50**
   (`collector_target_reached` é a última linha de cada uma; burst re-checa por frame,
   `collector_loop.py:232`). As 8 antigas (988–1.679) não reativam com alvo ≤150 — **é o
   desenhado em D-91**.
2. **Novas começam do zero?** Sim (código: `collector_state.py:35-69`; empírico: restart de
   00:22 com 28 câmeras logou `frames_ja_contados=8667` = só as antigas; as 20 novas partiram
   de 0). Canal 9 segue draft → fora do channel_map (filtro no config_poller:209-214).
3. **Frame excluído conta na cota?** **SIM — e fica decidido que é o comportamento desejado
   por ora**: o contador é local, incrementa pós-upload e nunca decrementa nem consulta o
   banco; a cota mede **esforço de captura** (RTSP no gravador, banda, R2), não dataset
   curado. Empírico: 2a683620 tem 100 excluídas e o contador segue 988. Mudar (decrementar
   por comando, contar do banco) é decisão de produto futura — nada implementado.

**Anomalia registrada (não investigada):** R2 tem **391 objetos órfãos** sob `nvr/` sem linha
no banco (333 pré-existentes em T0, +57 entre 23:11–23:17 com o coletor comprovadamente
congelado — candidato: task cloud `nvr_extraction`, mesmo prefixo). Custo só de storage;
não afeta cota nem contagem. Fica para rodada própria.

### D-96 · Miniatura da triagem por snapshot ONVIF sob demanda — ativação temporária de draft REMOVIDA

**12/08 · Claude · ✅ mergeado na develop (PR #363; filtro de treinamento no PR #362)**

A triagem (`/epi/cameras/triagem`) "resolvia" imagem de draft **ativando a câmera
temporariamente** — mexia no channel_map, ligava HLS e deixava estado sujo em falha. Removido.
No lugar, o caminho do D-85: **`GetSnapshotUri` ONVIF no iNVD**, executado no box, fallback de
1 frame RTSP (`RtspTimestampRecorderClient.get_snapshot`) — código estruturado para ser
reutilizado pela coleta de ~17 fotos/dia.

- **Fluxo:** `POST /api/cameras/{id}/snapshot/refresh` (JWT, cross-tenant 404, idempotente)
  → `edge_command capture_snapshot` → box captura **sequencial com delay 2s** (⛔ não satura o
  gravador) → `POST /api/v1/edge/cameras/{id}/snapshot` (device auth, escopo novo
  `snapshot:write`, teto 5MB) → R2 `snapshots/{tenant}/{camera}/{ts}.jpg` → cache Redis
  (frescor 10 min — re-render **nunca** bate no gravador) → `GET .../snapshot` com presigned
  15 min. Frontend: lazy-load por viewport, fila de concorrência 2, botão atualizar, falha
  **com motivo** (sem sinal / timeout / auth), nunca as 29 de uma vez.
- **Anti-lockout (D-09):** `RecorderAuthError` tipado; primeiro 401/403 abre **circuit
  breaker até restart** — nenhuma nova tentativa no gravador; canal vazio/timeout ≠ auth.
- **Decisão de escopo de device:** o bearer do edge passa a ser assinado com a **união**
  identity ∪ enum do código implantado. Racional: o servidor não persiste grants por device
  (o enroll devolve o enum inteiro; a autorização lê claims do token auto-assinado, ADR-0019)
  — o identity.json era só cache do enum da época do enrollment. Deploy propaga escopo novo
  **sem reenroll/revogação**. Ressalva registrada no código: se escopos virarem grant por
  device no servidor, revisitar. Paridade do espelho do enum trancada por teste.
- **Pendente de validação em campo:** `GetSnapshotUri` nunca exercitado contra o iNVD 3032
  real (protocolo em uso na RVB é `intelbras`/RTSP — o fallback é o caminho que roda primeiro).

### D-97 · Elo nativo FECHADO: propagação disparada pela página, executada pelo box sozinho

**12/08 · Vitor (sequência) + Claude (execução) · ✅**

Sequência do "PODE" executada na ordem: PR #367 mergeado no develop (CI verde; única falha =
SCA npm audit do landing, pré-existente e não-bloqueante) → **OTA do box** pelo canal
(`PUT /admin/software-channels/dev` → `f8a3f1d`, updater timer, swap atômico 08:43, agente
reiniciado — release já com o executor `ensure_dependencies`; trava do D-94 removida) →
**duas rodadas nativas disparadas pela PÁGINA, zero intervenção no box**.

**A prova do elo (job `8e914792`, validação via UI):** estúdio de anotação → frame semeado do
Canal 8 (11/08) → painel "Buscar imagens iguais" (selo *"processando no equipamento da fábrica
— as imagens não saem do site"*, SEM linha de custo) → Iniciar busca → worker despachou
`edge_commands` → **poller nativo do box consumiu e ackou `done {launched: true, unit:
propagation-8e914792}`** → unit systemd orçada (6G/400%) rodou o executor → callbacks →
**`completed` em 10min23s (134 frames: 129 sementes embedadas + pool)** → barra na página:
*"✓ 1 proposta encontrada · Revisar"*. Recursos durante: job 2,1 GB, GR3D 38–99%,
MemAvailable ≥ 8,0 GB, live view intocado.

**Lote de 100 (job `9a764297`, pela página, opção "100 imagens"):** pool completo do dia
(208 frames, 211 caixas/129 frames de semente, top-100 resultados): **completed em 15min48s (948s), mesma esteira nativa (ack `done {launched: true}`), 1 proposta — 'Capacete', confidence 0,79, num frame-ALVO novo**. Ritmo bruto consistente nos dois jobs: ~4,6 s/frame incluindo o re-embed das sementes.

**🔴 O achado que muda a próxima conversa — rendimento do v1:** com 211 caixas de semente e
threshold 0,65, a validação produziu **1 proposta em 134 frames**; o lote de 100, **1 proposta em 208 frames (79 alvos novos)**. A infra
está provada e barata (equipamento da fábrica, sem custo por rodada); o gargalo agora é o
**recall do pipeline v1** (SAM AMG `points_per_side=12` + similaridade média por classe +
threshold 0,65). Antes de gastar horas no pool completo restante (~2.300 frames nas outras
fatias câmera×dia), calibrar: threshold menor / `points_per_side` maior / top-K por frame —
decisão do Vitor com a fila de revisão aberta na frente.

**Quebra achada e corrigida no caminho:** o api-v3 DEV estava servindo um deploy de 04:04Z
(`railway up` de árvore SEM a feature, da sessão paralela) — preflight sem `gpu_provider` e a
UI honestamente mostrando custo RunPod. Redeploy de `develop f8a3f1d` (api-v3 + worker +
frontend) restaurou. Regra que fica: **depois de merge, o deploy DEV precisa vir do develop
mergeado — duas sessões dando `railway up` de árvores diferentes se atropelam em silêncio.**

**Dívidas novas (próxima rodada, não esta):**
- Poller lança TODOS os comandos `run_propagation` pendentes de uma vez — 2 jobs simultâneos
  = 2×6G no box (OOM). Serializar (1 unit por vez) antes de qualquer fila de fatias.
- Env file 0600 fica no disco após job concluído (só é removido em falha de launch).
- Barra: "Preparando referências (129 **caixas**)" — `seed_count` conta FRAMES (211 caixas em
  129 frames); wording.
- Somam-se às do D-94 que ficam: callback_token pós-terminal, cache de pesos por sha256.
### D-98 · /monitoring: histórico mora NO BOX, egress só ao ver (sem Prometheus, sem jtop)

**12/08 · pedido do Vitor, arquitetura Claude · ✅ (mergeado para develop)** _(era D-93 nesta branch; renumerado no merge — D-93..D-97 ficaram com a rodada de propagação)_

O Jetson da operação era caixa-preta (journald volátil, sinks desligados de propósito, toda
investigação dependia de SSH aberto na hora). Pedido: visão total com histórico, **mas só
consumindo egress quando o Vitor estiver acessando**. Esse requisito decide a arquitetura:

- **Coletor residente no box** (`python -m app.monitoring`, unit `edge-monitoring-collector`
  com CPUQuota=10%/MemoryMax=128M/OOMScoreAdjust=300) grava as 7 camadas num **ring buffer
  SQLite local** com downsample (10s/2h · 1min/48h · 5min/30d) e guarda de reserva de disco.
  Zero conexão de rede no coletor — por construção.
- **Acesso = comando**: a página cria `monitoring.query|snapshot|logtail` na fila
  `edge_commands`; o box responde pelo **canal outbound que já existia** (ADR-0020 — nada
  inbound, nenhuma porta nova). Poll ocioso segue 60s; `monitoring.*` liga **burst de 2s por
  180s**. Página fechada → burst expira → regime idle.
- **Logtail redigido NO BOX** (`redact_url_credentials` antes de qualquer byte sair — senha
  de câmera vive nesses logs).
- **Gate por papel, não por obscuridade**: rota fora do menu E superadmin-only; não-superadmin
  recebe na API **404** e no front o MESMO comportamento de rota inexistente (C-01). Acesso
  auditado em `public.audit_log` (query/snapshot dedup 15min; logtail/thresholds sempre).
- ⛔ **Sem stack Prometheus/Grafana** (outro serviço para operar num box de 16GB, superfície
  nova) — fica no produto. ⛔ **Sem jtop/jetson-stats (AGPL-3.0)** — o agente edge é código
  distribuído ao site do cliente e o gate de licença do CI não olha esse caminho; fontes são
  `tegrastats` (binário NVIDIA, sem encargo, modo contínuo — nunca fork por amostra) + /sys +
  /proc + `systemctl --user show`. Throttling térmico vem dos cooling devices
  `*-throttle-alert` (cur_state>0), OOM kills de `/proc/vmstat` — ambos sem sudo.
- **Substitui o `edge-telemetry-collector` antigo** (JSONL sem teto — 230MB acumulados no
  box); a unit antiga sai de cena no deploy desta rodada. A nova entra nas
  `_DEFAULT_SECONDARY_UNIT_NAMES` do OTA (dívida D-42: unit fora da lista roda código velho).
- **Inferência (operação assistida)**: painéis desenhados AGORA; o runtime preencherá
  `inference.json` (contrato em `app/monitoring/sampler.py`). O indicador central é o
  **heartbeat de detecção** ("câmera X sem detecção há Y min") — na operação assistida,
  silêncio é indistinguível de pipeline morto.

Migration 117 (`edge_monitoring_thresholds`, harness 2x verde). Código: `app/monitoring/` no
edge-sync-agent, blueprint `/api/v1/monitoring`, página `/monitoring` no frontend.

### D-99 · "/monitoring abre e os indicadores não aparecem": DOIS problemas independentes (deploy sobrescrito + crash de render que apagava a página), fail-loud + gráficos dinâmicos + downsample

**12/08 · Claude · ✅ código mergeado para develop** _(era D-94 nesta branch)_

Diagnóstico dos 4 elos da corrente (dado real, não chute):

1. **Coletor grava (box)** — SAUDÁVEL para o sintoma: 726 amostras/2h no ring buffer
   (`~/edge-telemetry/metrics.db`, res 10s/1m/5m). ⚠️ Mas a unit `edge-monitoring-collector`
   entrou em **crash-loop** às 11:43 UTC — `No module named app.monitoring`: um OTA da rodada
   de propagação repontou `recognition/current` para o release `f8a3f1d4`, que **não continha
   `app/monitoring/`** (o módulo só existia em `feat/edge-monitoring`, agora mergeado). Há 2h de
   histórico — não é a causa do "vazio total", virou problema só 15 min antes.
2. **Comando nuvem→box — MORRIA AQUI.** A API-V3 do DEV **não servia o blueprint**
   `/api/v1/monitoring` (`GET /sites` → catch-all `{"frontend":"separate service"}` 200;
   `POST .../query` → 405) — deploy sobrescrito pela rodada paralela. **Zero comandos
   `monitoring.*` em 8h** (último sucesso 04:09 UTC, 2,1MB). Classe [[dev-api-singleton-race]];
   a saída definitiva foi o merge para develop (uma origem única de deploy).
3. **Box responde→API** — N/A (nenhum comando chegava).
4. **Front renderiza** — ALÉM do catch-all, havia um **bug de código que apagava a página
   INTEIRA**: `InferencePanel` lia `detections.chain.detection_to_ingest_s`, mas o contrato real
   aninha `chain` **por câmera** (`routes.py site_detections`) — `detections.chain` `undefined`
   → TypeError no render → o `<ErrorBoundary>` global trocava todo o conteúdo por "Erro
   inesperado". `usePolling(loadDetections)` dispara na montagem, então a página **branqueava no
   primeiro RTT** mesmo com API e box saudáveis. Este era o "200 e nada aparece".

Decisões/correções (código):

- **Vazio nunca mudo (a correção mais importante, independente da causa).** `ErrorState`
  (vermelho, ícone, motivo) **visualmente distinto** do `EmptyState` neutro; `PanelBoundary`
  por painel — um card que quebra no render degrada só a si mesmo com o motivo, **nunca derruba
  a página** (re-arma sozinho quando chega amostra nova). Banner de frescor distingue os quatro
  estados: coletando desde X · coletor parado há Y (vermelho) · não implementado (inferência) ·
  erro ao buscar (+ tentar de novo).
- **Fail-loud no envelope**: `monitoringService.unwrap()` — um 200 catch-all (deploy
  sobrescrito) vira erro diagnóstico *"a API não está servindo o monitoramento — verifique o
  deploy"* em vez de `undefined` silencioso. `loadDetections` ganhou try/catch (erro ≠ "sem
  detecção").
- **Contrato alinhado ao que o box/API realmente emitem** (C-04, verificado contra código e
  dado ao vivo): detecções `last_occurred_at`/`detections_in_window`/`chain` por câmera;
  `net.api_ok`+`api_status_age_s` (não `api_last_ok_ts`); `collection.available` (não
  `enabled`). Teste de regressão falha-antes/passa-depois (`EdgeMonitoring.contract.test.tsx`).
- **Gráficos dinâmicos** (recharts): domínio de tempo controlado, **zoom por arraste** +
  ctrl/alt-scroll, **pan** (shift-drag / modo mover), **tooltip com valor e timestamp**, **séries
  sincronizadas** (`syncId`) — cruzar throttling térmico × queda de FPS no mesmo instante.
  Navegação **sob demanda**: pan/zoom para antes do carregado sobe para a janela que cobre —
  só em interação do usuário, zero-egress preservado.
- **Downsample no BOX antes do egress** (`MetricsReader.query` honra `layers` + `max_points`,
  extrema-preserving): baseline 2h all-layers **1,79MB** → `layers=[hw,net] max_points=400`
  **262KB**; **30d `layers=[hw]` 290KB** (vs 57MB sem cap). O front pede
  `layers=[hw,net,collection]`+cap para a série (painéis usam o snapshot completo no `latest`).

Merge para develop unifica a origem de deploy: com o monitoring na develop, deploys baseados em
develop param de sobrescrever o coletor/blueprint. Falta redeploy da API-V3 DEV + OTA do box a
partir da develop atualizada (coordenar com a propagação, que também vive nesses singletons).

### D-100 · Ponytail adotado — reduz código, NUNCA verificação

**12/08 · Claude · 🔄 em execução (instalação pelo Vitor)**

Rodada de ferramenta (não de produto). Adotado o ruleset **Ponytail** (`DietrichGebert/ponytail`,
MIT) — "sênior preguiçoso", escada de 7 degraus antes de escrever código: 1) precisa existir? (YAGNI)
· 2) já existe no codebase? reusa · 3) stdlib faz? · 4) recurso nativo? · 5) dependência instalada? ·
6) uma linha? · 7) só então o mínimo que funciona. Lema: *"lazy about the solution, never about
reading"*. Combina com como o projeto já vinha decidindo na mão (reusar `remote_train.py`,
`GpuProvider`, seletor do #362). **Verificado (C-04, não marketing):** puramente local, **zero egress**,
sem chamada de rede; custo medido do `AGENTS.md` ≈ **~800 tokens/sessão** (arquivo único auto-contido);
escreve em `~/.config/ponytail/`; reversível (`/plugin uninstall`). Instala com 2 comandos que o Vitor
digita (`/plugin marketplace add DietrichGebert/ponytail` + `/plugin install ponytail@ponytail`) —
slash-commands não são executáveis por agente.

🔴 **GUARDA INEGOCIÁVEL — Ponytail pode cortar CÓDIGO, nunca VERIFICAÇÃO.** Independentemente do que o
ruleset sugira, continuam obrigatórios: percorrer o caminho no navegador antes de entregar roteiro
(D-82 — foi o que pegou o `useToast` que 276 testes verdes não pegaram); soak ≥3× o TTL antes de
declarar estabilidade; prova com número dos dois lados (banco **e** R2, antes **e** depois); nunca
`completed` sem artefato verificável; e as travas de segurança (guard por destino, C-01 cross-tenant→404,
ADR-0017 sem fallback de tenant, redação de credencial). **Em conflito, a regra do projeto vence e o
episódio é reportado** (é informação sobre a ferramenta).

### D-101 · Repowise só self-hosted local; hosted/prose/telemetria proibidos sem aceite

**12/08 · Claude · ⏸ adiada (indexação pós-1º modelo, em worktree limpa)**

Investigado o **Repowise** (`repowise-dev/repowise`, `pip install repowise` v0.41.0) — indexa o repo em
camadas (grafo/git/wiki/decisões/saúde) e expõe por MCP (11 tools: `get_why`, `get_overview`,
`get_dead_code`, `get_risk`, `get_health`, `search_codebase`…). **Egress verificado no `--help` da CLI
real (C-04), não em doc de marketing.** A ferramenta puxa ~90 deps, incl. clientes de LLM/embedding
(`openai`/`anthropic`/`google-genai`/`litellm`) e tem **modo hosted** (Postgres+R2 em repowise.dev) que
**sobe código proprietário** — ⛔ proibido sem aceite do Vitor. **Os defaults são footgun:** `init` roda
`--prose` (manda trechos de código a um LLM) **sempre que houver API key no ambiente**; a **telemetria é
opt-out (ligada por padrão)**. **Receita segura, obrigatória:** `repowise telemetry disable` →
`init --no-prose --mode fast` **sem nenhuma API key no ambiente** (determinístico, *"no model and no
key"*, zero egress de código) → busca semântica só com `--embedder ollama|mock` (nunca os de API) →
`.repowise/` no `.gitignore` (o `mcp` carrega `<repo>/.repowise/.env` com chaves).

🔴 **Risco C-04 estrutural:** um índice gerado e cacheado corre o mesmo risco que originou a C-04 (o
`CLAUDE.md` que descrevia `backend/`+13 microserviços inexistentes). Se o hook de reindex não estiver
ligado, o índice **envelhece calado** e vira "fonte confiável e desatualizada" — agora com aparência de
autoridade. Reindex é por git-hook/watch/manual; `status` mostra sync, mas staleness por timestamp não
foi confirmado. Custo fixo: 11 tools MCP no prompt de toda sessão (~1,5–3k tokens estimados; perfil
`--tools lean` = 6). ⚠️ Em rodada curta pode custar mais do que economiza → ferramenta de investigação,
não de toda sessão.

**Decisão (Vitor, 12/08):** indexar **depois do primeiro modelo**, em worktree limpa de `origin/develop`,
com a receita acima — não neste ciclo, para não atrasar treino/propagação/monitoramento. **`get_why` a
validar** nos 3 casos de resposta conhecida (401/superadmin restaura backup = corrida #306–310/D-56; bbox
`pointerEvents:'none'` = cicatriz, não preferência; playlist só publica pós-`.ts` = corrida #330) —
reportar a **resposta literal**; o achado-chave é se ele **inventa** razão plausível vs. diz "não sei".

**Regra desta rodada (vale para as duas ferramentas):** **regra do projeto vence regra de ferramenta,
sempre.** Em conflito: reportar, não resolver sozinho. Nenhuma credencial em índice, log ou config
commitada.

---

### D-102 · Volta 0 do flywheel — primeiro modelo treinado do RVB (RF-DETR base), com métrica por classe legível

**14/08 · Claude · ✅ concluído (modelo `8e8fedf7` no registry DEV, is_active=false)** · *(extraída do PR #375 — que será fechado; o D-102 preenche a lacuna que D-103/D-104 marcaram como "não localizado")*

🔴 **Aviso que acompanha este modelo:** com poucas centenas de caixas em poucas classes, vindas de poucas
câmeras, **o modelo detecta mal ou quase nada — é o resultado ESPERADO.** A Volta 0 prova que a corrente
conecta com procedência; qualidade é a próxima volta, com mais dado e variedade de ângulo.

**Contexto.** RF-DETR **base** Apache 2.0 (⛔ nunca XL/2XL, ADR-0044), RunPod RTX 3090 COMMUNITY, teto
US$2 / timeout 1h. Só anotação **humana** — 556 caixas, 100% `source='manual'` (gate D-39).

**3 bugs de export/executor achados e corrigidos (o disparo é que provou):**
1. **Categorias homônimas duplicadas** — a mesma classe chegava com dois `class_id` (catálogo <100000 e
   namespaced ≥100000). Canonicalizado em `versioning_v2._build_categories`.
2. **CUDA device-side assert** — RF-DETR descarta categoria com `supercategory=="none"`; o export marcava
   TODAS com "none". Corrigido (placeholder id 0 + reais 1..N com supercategory != "none") — **é o fix que
   entrou pelo #378** (`versioning_v2.py:402`).
3. **Executor sem pin** — `rfdetr` latest puxava transformers≥5.1 incompatível; pinado
   `rfdetr[onnxexport]==1.5.0`.

**Métricas por classe (migration 098, antes dormente) — populadas no worker:** suporte por classe/split
(determinístico, do COCO) + P/R/F1 no maior split held-out (best-effort, greedy IoU, nunca derruba o
artefato) + confusão + procedência. Split por câmera+dia (sem leakage): train 210 / val 6 / test 179.
⚠️ **A implementação de código dessas métricas segue no #375 (não extraída aqui) — ver recomendação.**

---

### D-103 · Taxonomia EPI da RVB são 6 classes — capacete e colete NÃO são EPI exigido

**14/08 · Claude · ✅ decidido (Vitor)**

*(D-102 não localizado no registro em 14/08 — número deixado para o Vitor; esta entrada usa D-103
conforme a rodada de procedência.)*

**Decisão (Vitor):** a taxonomia de anotação vigente da RVB tem **6 classes** — `Protetor auditivo`,
`Sem protetor de ouvido`, `mascara`, `Sem mascara`, `Uso incorreto de mascara`, `Botas`. **`Capacete`,
`Sem Capacete`, `Colete`, `Sem Colete` e `hardhat` saem em DEFINITIVO**: capacete e colete não são EPI
exigido na RVB. ⛔ Não viram "backlog" nem "classe futura" — manter as duas versões vivas é exatamente o
mecanismo que envenenou o prompt do TREINO 1.

**Por quê registrar:** a classe fantasma `Sem Capacete` — que **nunca existiu no banco** — sobreviveu em
**três rodadas de planeamento** porque a lista divergia entre documentos (`docs/ROTEIRO_ANOTACAO_VITOR.md`
dizia uma coisa, o prompt herdava outra). Corrigido em `CLAUDE.md` e `ROTEIRO_ANOTACAO_VITOR.md`; ambos
carregam agora o bloco marcado `<!-- RVB-EPI-CLASSES -->`, e o **gate de docs**
(`scripts/ci/check_docs_gate.py`, regra 6) **falha o CI se a lista divergir entre documentos**. A lista de
demo genérica do produto (helmet/vest/gloves em `apps/frontend`, landing, `constants.py`) é **outra
taxonomia** (marketing/demo), fora do escopo do D-103 — não confundir.

**Como aplicar:** ao mexer na taxonomia da RVB, edite o bloco `RVB-EPI-CLASSES` em **todos** os docs que o
carregam (o gate lista quais divergem). Fonte da verdade = este registro. Ver
`docs/decisions/PROCEDENCIA_DE_RELATOS.md`.

### D-104 · Matriz classe × câmera + metas de equilíbrio da base (Volta 1)

**14/08 · Claude · ✅ construído no DEV (sem disparar treino)**

*(Segue a D-103 — taxonomia de 6 classes, PR #376. D-102 segue não localizado; numeração para o Vitor.)*

**O quê.** Aba **Cobertura** na tela de treinamento + endpoint `GET /api/training/coverage-matrix`
(`coverage_service.py`): matriz **classe × câmera** com **células zeradas visíveis** (a classe que
aquela câmera nunca viu é a informação mais valiosa). Conta **idêntico ao export de treino** —
mesmo universo de `versioning_v2._fetch_annotations` (só `humana`/`auto_aprovada`, sem arquivada, sem
excluída, offset de classe decodificado). **Provado com número:** `scripts/ops/verify_coverage_matches_export.py`
extrai os DOIS SQLs do código-fonte e roda contra o DEV → **556 caixas / 377 imagens dos dois lados**.
Estende `DEV-FILTRO-CLASSES-PROMPT.md` (não duplica: aquela rodada entregou facetas câmera/status; a
matriz 2D + metas + ranking + aviso de órfã é nova).

**Metas (pintadas na matriz).** **≥100 imagens/classe, em ≥5 câmeras, nenhuma câmera com >50% da
classe.** Derivação: 100 img × 20% de validação = **20 positivos de val/classe → resolução de recall
≤5%** (contra passos de 17% a k=6, onde F1 0,07 é indistinguível de 0 — os números da Volta 0). ≥5
câmeras permite **validação com câmera retida** (mede generalização, não decorar ângulo). Teto de 50%
ataca a concentração. **Piso de interpretabilidade** (abaixo = ruído): ≥40 img em ≥4 câmeras.

**Estado medido (DEV, 14/08).** 556 caixas / 377 imagens / **100% humanas**. **7 de 28 câmeras** têm
anotação; **só *Protetor auditivo* bate a meta** (189 img, 6 câm, 48%). *máscara* e *Sem protetor* têm
câmeras suficientes mas passam de 50% numa só (concentração). *Uso incorreto* (22), *Sem máscara* (28) e
*Botas* (30) estão **abaixo do piso**. *hardhat* (1 caixa) é straggler fora do D-103 — **arquivar** (não
some da contagem: aparece marcado, para a soma bater com o export).

**Respostas da Volta 1 (sem disparar).** (1) A validação para de ser arredondamento quando cada classe
atinge **≥100 img em ≥5 câmeras** (X medido acima). (2) *Uso incorreto* e *hardhat* estão abaixo do piso;
*hardhat* deve ser arquivado (D-103). (3) Para quebrar a concentração da **Canal 8**, anotar as classes
concentradas nas câmeras-reservatório com backlog (**RVB Camera 1: 1398 · Canal 7: 1000 · Canal 3: 999**)
— ranking na tela. **Coleta parada:** as 20 câmeras com ~50 frames (Canais 10–29) esgotam antes da meta e
precisam de coleta nova (listadas em "Câmeras para voltar a coletar").

**Avisos que a tela dá (não degrada em silêncio).** 1 **caixa órfã** `class_id=0 "Capacete"` na Canal 8
(o fantasma do capacete removido no D-103) — o export descarta calado, a tela **avisa**. Arquivadas
confirmadas fora: *Protetor auricular* (17), *incluir blur* (1).

**Como aplicar.** Endpoint é read-only, por tenant do JWT (`get_tenant_id`, sem fallback). Célula/lacuna
clicada leva direto à galeria filtrada naquela câmera, não anotadas.

### D-105 · Janela do pod órfão: linkar por NOME fecha a janela; varredura por nome ALERTA, não mata

**16/08 · Claude · ✅ código no DEV (branch `claude/orphan-window-fix`, PR rascunho)**

*(Número D-105 sujeito a reconciliação no merge — a numeração colide entre sessões; conferir D-máx em
`origin/develop` no momento do merge.)*

**O problema, medido (não presumido).** Dos 23 pods RunPod faturados, **15 (65%) não têm linha em
`training_jobs`** — mas a maioria é **anterior ao tracking por ref** (07-30, 08-11) ou **manual/fora do
fluxo** (o pod de **43 h / $21,78**, `3bgpr5laetxigp`, 08-13→14, o incidente conhecido). O caminho de
dispatch de HOJE **grava** `gpu_instance_ref` após `create_pod` (`training.py:560` `_persist_instance_ref`;
`runpod_runner.py:352→362`): dos 6 jobs de 08-14, os 5 que criaram pod têm ref; os 2 sem ref falharam no
próprio `POST /pods`. **A janela real** é estreita: entre `create_pod` e o `UPDATE` do ref, o pod está
vivo com ref NULL → o job-lookup do reconciler filtra `IS NOT NULL` → **cego**.

**A descoberta.** A linha do job **já existe ANTES do pod** (`update_fn("running")` em `training.py:572`,
antes de `run_runpod_job`) e o **nome do pod embute `job_id[:8]`** (`recognition-{kind}-{job_id[:8]}`).
Então o elo durável (linha + nome) existe desde o primeiro instante — faltava o reconciler **usar o nome**.

**Direção A — fecha a janela (sem mexer no dispatch).** `_load_active_job_id_prefixes()` indexa os jobs
RunPod ATIVOS (incl. ref NULL) por `id[:8]`; um pod sem ref-match é linkado pelo sufixo do nome → **mantido**
(rodada legítima cujo ref só não linkou ainda), não morto.

**Direção B — guarda-corpo.** Órfão de verdade (sem job por ref NEM por nome) **ALERTA (log), NÃO
termina** por heurística de nome. Morte automática fica só para **sinal positivo**: job em estado terminal,
ou idade > deadline do tipo de carga (`started_at`). *Reverte* o comportamento anterior (o reconciler
matava órfão de cara — mataria a rodada legítima da janela). "Na dúvida: alerta, não mata."

**Prova.** Teste `test_true_orphan_is_alerted_not_terminated` **falha com o código de hoje** (órfão
terminado) e passa depois; `test_keeps_pod_of_active_job_linked_by_name_when_ref_not_written` cobre a
janela. Suíte do reconciler 29/29, infra 1216/1216, ruff limpo. Só o reconciler mudou — dispatch intacto.

**Não feito (de propósito).** Morte automática de órfão por idade (o "teto duro") exige a idade do pod, que
o objeto de `list_pods` não expõe hoje — ficaria adivinhando campo. O alerta é a rede; humano decide. *(A
raiz da invisibilidade do pod de 43 h era **não haver beat rodando o reconciler** — decisão de infra do
Vitor, fora desta rodada de código.)*

---

## Rodada RunPod 10/08 (PR #343 — renumerada de D-85..D-88 → D-106..D-109)

> ⚠️ Estas quatro entradas foram escritas como **D-85..D-88** no PR #343, mas D-85/D-86 já foram
> ocupadas pelo #354 (inventário iNVD) que landou antes. Renumeradas na reconciliação do merge:
> **D-85→D-106 · D-86→D-107 · D-87→D-108 · D-88→D-109** (referências no texto atualizadas).

### D-106 · Rodada RunPod: as sete decisões do Vitor — e a flag NÃO é o controle

**10/08 · Vitor (decisões) + Claude (execução) · ✅**

1. **`training_third_party_cloud_enabled` LIGA** para o RVB no DEV — mas registrado com clareza:
   **a flag habilita a capacidade; quem impede imagem de operação de sair é a lista
   materializada de `frame_id` do job de propagação** (guard fail-closed, D-108). Flag ligada +
   job mal configurado ≠ vazamento: frame fora da lista **aborta o job**.
2. **RF-DETR ponta a ponta** (Apache 2.0). Caminho Hub/ultralytics **deletado** (D-107).
   Variantes XL/2XL (licença PML, não-Apache) **travadas em código** — dispatch rejeita.
3. **Teto de gasto: US$ 2/job, timeout 1h**, RTX 4090 community — **por tipo de carga**
   (`RUNPOD_MAX_USD_TRAIN` / `RUNPOD_MAX_USD_PROPAGATE`).
4. **Vast apagado** (client + provider + legado; nunca entregou treino — 404 desde 12/07).
   `remote_train.py` preservado como executor. **D-72 fecha**: o dicionário do contrato nomeia
   RunPod e o código agora bate — **um único suboperador (D-38)** para treino E propagação.
5. **Sementes anotadas nos frames de 31/07** (encenação): as 17 caixas de frames de operação
   continuam válidas mas **não vão para nuvem** antes da conversa com a advogada.
6. **Fila de aprovação MVP nesta rodada, com status de rejeitada dentro do MVP** (sem ele a
   fila nunca esvazia e "não revisada" vira indistinguível de "recusada").
7. RunPod em **Pods on-demand** (reusa `remote_train.py` via onstart; zero build de imagem) com
   **3 camadas de garantia de morte**: timeout+trap no pod · watchdog Celery · reconciliador
   beat lendo o Postgres (sobrevive a restart da API). Serverless fica como endurecimento futuro.

Entregue em: #337 (split/linhagem) · #338 (aprovação) · #339 (SCA drift) · #340 (honestidade) ·
#341 (runner) · #342 (propagação) · ADR-0061 · ADR-0062.

### D-107 · Quatro caminhos de treino que mentiam — deletados, não desligados

**10/08 · Claude (auditoria + execução) · ✅ PR #340**

Os quatro: `_simulate_training` (dormia e inventava mAP), `_dispatch_vast_ai_legacy` +
`provision_and_train.sh` (treinava no Roboflow público e apresentava como do tenant),
`_dispatch_hub` (**nunca enviou o dataset do tenant ao Ultralytics Hub** — o `datasetId` era um
UUID interno que o Hub nunca viu) e `POST /dashboard/training-metrics` (**qualquer usuário
autenticado fabricava métricas** para qualquer `model_name` — este ganhou role + validação de
modelo real, é a via do seed legítimo). Saldo: **−5.127 linhas**. **Regra que fica (ADR-0061):
⛔ nunca `completed` sem artefato verificado no R2** — `verify_model_artifact` roda nos 3 pontos
que persistem sucesso; artefato ausente → `failed` com motivo. Achado lateral: **o retreino do
módulo Qualidade nunca funcionou** — `ImportError` (`run_quality_training` não existe) mascarado
por `except` genérico; corrigido. License-gate estendido a `training/` e `scripts/`; pesos
travados **por sha256** em `docs/WEIGHTS_LICENSES.md` (o caso DINOv2 — Apache e FAIR
Noncommercial no MESMO repo — é o motivo).

### D-108 · Volta 1 será um modelo de UMA câmera — e isso é esperado, não defeito

**10/08 · Vitor (decisão de produto) · 📌 para a próxima encenação**

O pool consentido de 31/07 são **662 frames de uma única câmera**. Consequência: a propagação
gera propostas de um só ponto de vista e o modelo da Volta 1 **não vai funcionar nas outras
sete** — o mesmo erro de leitura da resolução: ver o modelo falhar na câmera 3 e concluir que o
sistema não presta, quando ele nunca viu a câmera 3. **Decisão de produto registrada: a próxima
encenação (ou a autorização dos frames de operação) precisa cobrir várias câmeras**, senão a
volta 2 herda a limitação. Junto: ~15 caixas ÷ 4 classes ≈ 4/classe — Volta 0 prova a CORRENTE,
Volta 1 prova a PROPAGAÇÃO, modelo que serve ao cliente é a volta 2. Trava do pool: **lista
materializada de `frame_id` + critério gravados no job, revalidados no dispatch com hash**
(não existe entidade "sessão de coleta"; `recorder_id` é o NVR, igual em tudo — não identifica
sessão).

### D-109 · O export COCO devolvia ZERO anotações de classe custom — a Volta 0 teria saído vazia

**10/08 · Claude (achado em execução) · ✅ PR #337**

O JOIN de categorias do export não desfazia o offset do namespace
(`frame_annotations.class_id = 100000 + yolo_classes.id`) — **toda anotação de classe custom de
tenant caía fora silenciosamente**. As 17 caixas do RVB nunca teriam entrado em dataset nenhum.
Corrigido junto com: split por **câmera+dia** para frames de NVR (antes: `frame:{id}` = split
aleatório por imagem, a métrica mentiria), exclusão de classes arquivadas e de frames
`curation_status='excluida'`, e `r2_weights_key` finalmente persistido na linhagem.

### D-113 · Provisionamento de acessos do runner: conta E2E confirmada, R2 read-only preparado (não criado), beat ausente

**16/08 · Claude · ✅ verificado no DEV** · *(número D-113: o prompt sugeriu D-112, mas o #386 aberto reivindica D-112 — usei D-113 para não colidir; reconciliar no merge)*

- **Conta de teste JÁ EXISTE — não criei outra.** `e2e-anotacao@recognition.dev` ("E2E Anotacao
  (temporario)", ativa) casa com a variável `E2E_ANNOT_PASSWORD` (serviço API-V3, DEV). **Login
  confirmado** contra `POST /api/auth/login` no DEV via injeção por ENV (senha nunca impressa; só
  `success=true` + token presente). ⚠️ **Achado:** o usuário é **superadmin** (tenant 22222222), não o
  papel mínimo de anotador no RVB que o ideal pede — recomendo o Vitor rebaixar para papel mínimo, mas
  a regra "se existir, não crie outro" prevaleceu (não criei substituto). Falta `E2E_ANNOT_EMAIL` como
  variável (o e-mail não é segredo; runner precisa dele além da senha).
- **R2 read-only: PREPARADO, não criado.** ⛔ Agente não cria credencial de nuvem (acesso auto-concedido).
  Entregue: `docs/runbooks/R2_RO_TOKEN_PROVISION.md` (caminho de 60s — Object Read only, só bucket DEV,
  TTL 90d, cola `R2_RO_ACCESS_KEY`/`R2_RO_SECRET` no ambiente do **runner**, ⛔ não no Railway) +
  `scripts/ops/verify_r2_ro_access.py` (lê ENV, `list_objects_v2 MaxKeys=1`, sem baixar, sem imprimir
  chave; barra reuso do `R2_KEY` read-write). Verificação do R2 fica **pendente** até o Vitor criar o token.
- 🔴 **Beat do reconciler confirmado AUSENTE no DEV** (causa raiz do pod órfão de 43h): `railway_start.py`
  tem `SERVICE_TYPE=beat` como serviço separado (worker **não** usa `-B`, linha 527-529), mas **não há
  serviço `beat`** no projeto DEV (serviços: Frontend, celery-worker, API-V3, Redis, Postgres,
  landing-page). O `SAFE_BEAT_SCHEDULE` agenda `reconcile_runpod_pods` a cada 300s — que **nunca dispara**.
  ⛔ Não provisionei (infra = decisão do Vitor): falta **1 serviço Railway `SERVICE_TYPE=beat`** (mesmo
  repo/branch, réplica única).

*Segredo: nenhum valor de credencial foi impresso em log, relatório ou arquivo nesta rodada.*

<!-- entradas do #384 (aba Classificar) renumeradas para não colidir com a develop; ver notas em cada uma -->

### D-114 · Tela de classificação rápida por recorte + taxonomia estendida (adendo a D-103/D-104)
> ⚠️ Renumerado **D-105→D-114** na consolidação do merge #384 (D-105 já em uso na develop).

**Problema.** 22 de 29 câmeras têm zero anotação e desenhar caixa custa ~20 s. Anotação 100% automática
(SAM+DINOv2, 1005 propostas) **falhou** — metade das classes é AUSÊNCIA (*sem protetor*, *sem máscara*,
*uso incorreto*) e ausência não tem aparência para propagar. **Não repetir.**

**Decisão.** Nova aba **Classificar** em `TrainingPage` que tira o trabalho braçal do caminho do humano:
mostra UM recorte de pessoa (crop do bbox, via `crop_person` YOLOX-nano ONNX no edge) e o humano marca,
por **tipo de EPI**, um **estado** — em vez de desenhar. Evolução do `SearchFindingsPanel` (reusa
`cropStyle`, criação de classe inline), não uma segunda UI. Meta ≤3 s/recorte, teclado primeiro.

**Os 4 tipos e estados** (estados exclusivos DENTRO do tipo → impossível marcar "com" e "sem" na mesma
pessoa; multilabel ENTRE tipos):

| Tipo | Estados | Classe no banco |
|---|---|---|
| Proteção auditiva | Presente · Ausente · Não visível | `Protetor auditivo` / `Sem protetor de ouvido` ✅ |
| Máscara | Presente · Ausente · Uso incorreto · Não visível | `mascara` / `Sem mascara` ✅ · `Uso incorreto` ⚠ criar |
| Botas | Presente · Ausente · Não visível | `Botas` ⚠ · `Sem botas` (script r1a) ⚠ criar |
| Óculos de proteção | Presente · Ausente · Não visível | `Óculos` / `Sem óculos` ⚠ criar |

**Óculos entra** (decisão Vitor, 15/08) — presente e ausente. Nenhum outro EPI (luvas/uniforme/respirador
descartados). **Não visível / Não sei / Pular / Reprovar ⛔ não entram no dataset.** Aprovar grava 1
`frame_annotation` por estado presente/ausente ativo, todos no bbox da pessoa, `source='manual'` (D-39).

**Estado da tela ≠ classe do banco.** Mapa `estado→class_id` derivado em runtime de `GET /api/classes`
(`versioning_v2`), nunca hardcoded. Estado sem classe → tela **grava e sinaliza "classe a criar"**, e o
recorte **fica na fila** — jamais perde o julgamento do humano por falta de linha no banco.

**Classes novas.** `Sem botas` pronto via `scripts/ops/add_epi_classes_rvb.py` (env-gated, `CONFIRM_OPS=1`,
seed manual — não migration, D-84). `Óculos`/`Sem óculos`/`Uso incorreto`: **pendente de verificação no DB
real** antes de criar (a contagem só mostra classes com caixas; classe vazia não apareceria — risco de
duplicata). r1a documenta que `Óculos`(6)/`Sem óculos`(7) podem já existir como `module_classes` globais
anotadas — **Vitor confirma no banco e cria só o que faltar**, seguindo a convenção do par auricular.

**Como aplicar.** Deep-link da matriz de Cobertura (D-104): célula/lacuna (já carrega `class_id`+`camera_id`)
leva à fila de classificação daquela câmera/classe. Minerador do DVR (bloco 2) alimenta a fila com recortes
`source='nvr'`. Split de treino por câmera+dia já garantido (`versioning_v2._group_key`). O gate de docs
(regra 6, PR #376) ainda não está na develop; quando entrar, sincronizar a lista de classes em `CLAUDE.md`
e `ROTEIRO_ANOTACAO_VITOR.md`.

### D-115 · Correção de fato: a captura de 31/07 foi operação real, não encenação
> ⚠️ Renumerado **D-106→D-115** na consolidação do merge #384 (D-106 já em uso na develop).

**Fato (Vitor, 15/08).** *"Não existiu encenação controlada dia 31/07. Dia 31 foi operação real. Não tem
como encenar numa fábrica — ela precisa operar enquanto a gente trabalha aqui."* Os 662 frames de 31/07 —
e tudo que for extraído do DVR agora — são **trabalhadores reais em operação real**.

**Consequência (jurídica, não terminológica).** Prompts e docs anteriores afirmaram "risco de LGPD
reduzido porque seriam pessoas combinadas e cientes". **Premissa FALSA.** Todo raciocínio de LGPD apoiado
em "encenação" precisa ser refeito — inclui `docs/negocio/ANALISE_LGPD_COLHEITA_RETROATIVA.md`. O arquivo
`docs/PROTOCOLO_ENCENACAO_LOTE1_RVB.md` **existe e o nome contradiz o fato** — não é descrição do que
aconteceu; recebeu banner de correção no topo. ⛔ Não repetir o termo, ⛔ não propor "encenar" como solução
para falta de exemplo — a fábrica precisa operar.

### D-116 · Recon de viabilidade do minerador DVR no Orin (2026-08-16) — corrente pronta, faltam config e deploy
> ⚠️ Renumerado **D-107→D-116** na consolidação do merge #384 (D-107 já em uso na develop).

**Feito.** SSH read-only no pandora + probe que não imprime credencial/host/URL. **A corrente mecânica está PRONTA:**
`recorder_factory.build_recorder_client_from_env()` resolve para o `RtspTimestampRecorderClient` **real**
(playback RTSP `/cam/playback?starttime=…&endtime=…`, dialeto Intelbras), **deployado** em
`~/recognition/current`; **DVR TCP-alcançável** na :554; `yolox_nano.onnx` presente; disco 56 GB livres
(reserva intacta); identidade do device (`DEVICE_ID`/`ENROLLMENT_TOKEN`/chave) e credencial do DVR
(`RECORDER_HOST/USERNAME/PASSWORD`) presentes no env (Vitor já provisionou).

🔴 **Dois bloqueios impedem o lote 1 como especificado (canal 10 primeiro):**
1. **`RECORDER_CHANNEL_MAP` só tem o canal 1** (`{"eb15…":1}`) — **canal 10 (única fonte de AUSÊNCIA) e os
   demais canais aprovados não estão registrados como câmeras do gravador.** Sem `camera_id` mapeado, o
   minerador não tem como pedir playback do canal 10.
2. **`replay_miner.py` (orquestração desta rodada) não está no box** — vive só na PR #384 (não mergeada).
   O box tem o *client*, não o *minerador*. Precisa entrar por OTA (após merge) para rodar de verdade.

**Decisão — não puxei imagem real nesta sessão.** (a) Canal 10 é inalcançável (bloqueio 1), então o
pedido central do prompt — qualidade real da ausência — não teria resposta mesmo puxando; (b) primeiro
run real de playback num device de produção que a RVB usa pra live-view, com risco de vazar credencial no
comando ffmpeg, pede a porta deliberada do Vitor (`CONFIRM_MINE=1`), não improviso autônomo. Regra da
casa: na dúvida entre agir e reportar, **reportar**.

**Veredito de ausência (bloco 4, com dado).** O dry-run projeta **~209 crops de ausência no total** (canal
10, 8 dias × 2 turnos). A ausência se reparte em ≥4 classes (*sem protetor*, *sem máscara*, *sem óculos*,
*sem botas*). ⇒ **A meta de ≥100 imagens POR classe de ausência NÃO é alcançável só pelo canal 10** — 209
÷ 4 ≈ 52/classe no teto otimista. Ou se mapeiam mais áreas de convivência, ou a ausência precisa de fonte
além do DVR. **Confirmação empírica fica pendente do lote 1 real.**

**Para o Vitor rodar o lote 1 (canal 10) com segurança:** (1) registrar canal 10 (e os aprovados 8/11/12/19/23/28)
como câmeras do gravador → `RECORDER_CHANNEL_MAP` no DEV/env; (2) subir o `replay_miner` por OTA (merge #384);
(3) rodar no pandora com `CONFIRM_MINE=1` — anti-lockout e reserva de disco já embutidos.

### D-117 · Runner do lote 1 + corrente do DVR validada de verdade + 2 bloqueios de yield (corrige D-107)
> ⚠️ Renumerado **D-112→D-117** na consolidação do merge #384 (D-112 já em uso na develop).

**Entregue.** `scripts/ops/mine_lote1.py` (runner pronto pro Vitor): lê `RECORDER_*`/`EDGE_*` do env (nunca
argv), valida ANTES de puxar (`CONFIRM_MINE=1`? ffmpeg no PATH? canal mapeado? disco? identidade? DVR
responde?) com mensagem legível do que falta, monta plano mínimo (1 canal, 1 dia, 1 turno ≈ 50 recortes),
anti-lockout herdado do `mine()` (401/403 encerra o run, sem retry), modo inspeção (`LOTE1_SAVE_DIR`, salva
local sem subir). `ruff` limpo. Validado no box (recusa sem `CONFIRM_MINE`; roda com). Runbook em
`docs/runbooks/RUNBOOK_LOTE1_DVR.md`.

🔴 **Correções ao D-107 (estado antigo estava errado — C-04):**
- **Canal 10 (e 28 canais) JÁ estão mapeados** via `resolve_channel_map`/cloud_config (ADR-0058). O D-107
  leu o `RECORDER_CHANNEL_MAP` do `.env` (stale, só canal 1) em vez da fonte autoritativa. **"Bloqueio nº1"
  era falso.**
- **A corrente do DVR FUNCIONA de ponta a ponta:** `RtspTimestampRecorderClient` puxou playback real do
  iNVD 3032 (canal 1 e 10, ~3,4 MB por janela de 6 s). ADR-0034 era "mock-only"; agora é validado em
  hardware real.
- O único motivo de "0 crops" no 1º teste foi **ffmpeg fora do PATH** (vive em `~/.local/bin`, que os
  serviços systemd põem no PATH mas o shell de login não). O runner agora valida ffmpeg antes de puxar.

🔴 **Dois bloqueios reais de yield (o valor de "começar pequeno"):**
1. **Limiar de blur 3000 rejeita ~100% dos recortes reais.** Medido em campo: variância dos recortes reais
   = **141–259 (p50 155)**, contra o limiar 3000 → **0/23 passam**. O limiar foi calibrado só em fixture
   sintético (o próprio código avisa). Exposto via `LOTE1_BLUR_MIN`; recalibrar sobre recortes
   humano-aprovados, não no chute.
2. **O detector YOLOX-nano falso-positiva em estrutura fixa** — um poste do canal 10 virou "pessoa" em
   **23/23** amostras (recortes de ~128×168 de um poste preto no concreto). Baixar o blur admitiria mais
   poste, não pessoa. O fix é no detector (subir confiança / filtrar aspecto), não no blur.

**Recount da ausência (bloco 4 — a conta antiga só via o canal 10).** A pergunta certa é a **taxa de
não-conformidade por tipo de EPI, por canal aprovado** — e para isso **não há dado**: exige veredito humano
por recorte (aba Classificar), que ainda não rodou. **Resposta honesta: "não sei" — o lote 1 humano-
classificado é quem responde.** Direção qualitativa: com o veredito completo por recorte, AUSÊNCIA vem de
TODO canal, e produção (~6000 recortes) domina o canal 10 (~209) — **mas só depois de corrigir (1) e (2)**,
senão o yield real é ~0. Amostra desta sessão: canal 10 (convivência) na Sex tarde estava quase vazio
(poste + cena vazia); canal 8 (produção) deu 0 pessoas em 36 frames (amostra de 6 s é ruidosa demais para
medir yield).

**Precisa mapear mais áreas de convivência, ou a produção resolve?** **Nem uma coisa nem outra ainda** —
primeiro corrigir os 2 bloqueios mecânicos. Direção: **produção resolve, NÃO mapear mais convivência** (o
canal 10 mostrou-se vazio), mas confirmar com um lote 1 de **turno inteiro** num canal de produção, humano-
classificado, depois dos fixes.

**Segurança.** Nada foi subido à nuvem (modo inspeção); recortes reais de trabalhadores apagados do box e
local ao fim; nenhuma credencial/host/URL/connection-string impressa (o `stderr` do ffmpeg é redigido e o
runner só imprime categoria de erro, nunca a mensagem crua).

<!-- Consolidação dos PRs #385/#386/#388 (D-107..115,119 renumerados uma vez -> D-118..127; D-116/117/118 do #386 omitidas por obsolescência) + entrada da rodada. -->

### D-118 · Estágio 2 = classificação multilabel por RECORTE (a AWS valida a direção do doc dois-estágios)
> ⚠️ Renumerado **D-107→D-118** na consolidação dos PRs #385/#386/#388 (D-107 já em uso na develop).

**16/08 · Claude · 📄 análise (sem código de produto)**

**Medido.** O caminho servido é **single-stage** (`services/inference/inference/detectors.py:169-216`;
`config.py:23` `VIOLATION_CLASSES="no_helmet,no_vest,no_gloves"`) — um forward por frame, sem cascata. O repo AWS é a
implementação de referência de **recorta-pessoa → classifica-o-recorte-inteiro**, confirmando independentemente a
recomendação de `avaliacao-dois-estagios-classificacao-por-recorte.md`.

**Veredito: 🟡 adotar adaptado.** Protótipo/export `{recorte, multilabel}` **pode começar já** (363 recortes já
anotados; masked BCE p/ rótulo parcial). **Servir no edge ⏸️ ADIADO até** — condição, não data — o FPS do Estágio 2
estar medido no Orin mantendo os 28 cams com folga.

### D-119 · Ausência se resolve com veredito por-recorte FORÇADO, não com propagação mais esperta
> ⚠️ Renumerado **D-108→D-119** na consolidação dos PRs #385/#386/#388 (D-108 já em uso na develop).

**16/08 · Claude · 📄 análise**

**Medido.** 273/363 recortes anotados são **só-positivo** → não dá pra fabricar negativo; a propagação SAM+DINO deu
**1005 propostas, 100% rejeitadas** (ausência não tem aparência para similaridade). O repo torna `novest` uma **classe
cheia** e isso funciona **porque a UI exige um veredito por recorte** (arrasta pra vest OU novest; nada meio-rotulado
entra no treino). A cura da ausência é de **fluxo de anotação**, não de modelo.

**Veredito: 🟡 adotar adaptado.** Na anotação, exigir veredito por classe (present/absent/N-A) por recorte antes de
contar como rotulado; reusa o scaffold grade-de-recortes + seletor + promover de `SearchFindingsPanel.tsx:44`.
Preferível ao masked-BCE-sobre-parcial (dá negativo limpo); masked BCE fica de fallback.

### D-120 · Estágio 2 servido = loop síncrono; ⛔ sem fila / state-machine / tabela nova
> ⚠️ Renumerado **D-109→D-120** na consolidação dos PRs #385/#386/#388 (D-109 já em uso na develop).

**16/08 · Claude · 📄 análise (guardrail)**

**Medido/observado.** O repo faz os 2 estágios num Lambda **síncrono**, classificando pessoas em paralelo
(`Promise.all`, `source/api/lib/index.js:400-436`), **sem banco, sem fila, sem state-machine** — estado só em S3 + ARN.
O projeto já pagou caro por manter complexidade duplicada.

**Veredito: ✅ adotar como guardrail.** Quando o Estágio 2 for servido, manter loop recorta→classifica em paralelo; não
introduzir orquestração nova. A lição de infra do repo é a **minimalidade**.

### D-121 · ⛔ NÃO adotar AWS servida — a pergunta segue fechada, agora com a razão específica do repo
> ⚠️ Renumerado **D-110→D-121** na consolidação dos PRs #385/#386/#388 (D-110 já em uso na develop).

**16/08 · Claude · 📄 análise**

Reafirma decisão já fechada 2× (`AVALIACAO_REKOGNITION_PPE_NO_FLUXO.md`, `avaliacao-dois-estagios`). O repo, apesar de
"treine o seu classificador", usa **Custom Labels que não exporta o modelo** (colide com ADR-0043) e serve a
**US$4/h·endpoint**. O treino por-recorte fica **local** (RunPod/Vast). Nenhum frame foi ou vai à AWS (ADR-0048, D-72).

**Veredito: ⛔ não adotar.**

### D-122 · ⛔ NÃO adotar o esquema binário 1-classe-por-recorte do repo (não-transferível)
> ⚠️ Renumerado **D-111→D-122** na consolidação dos PRs #385/#386/#388 (D-111 já em uso na develop).

**16/08 · Claude · 📄 análise**

O repo classifica **vest/novest** (binário, 1 EPI). Nosso problema é **multilabel multi-parte**: 6 classes do tenant
RVB, até 3 estados por parte (`mascara` / `Sem mascara` / `Uso incorreto de mascara`). Copiar o fluxo binário de 2 zonas
quebraria o schema de rótulo.

**Veredito: ⛔ não adotar / não-transferível.** Registrado para evitar a terceira redescoberta.

---

## Rodada 16/08 (tarde) — mineração DVR Lote 1: realidade do código e bloqueios

Rodada de validação da mineração (puxar ~50 recortes do gravador RVB para semear o DEV e percorrer os 6
passos da anotação). **Resultado: Lote 1 NÃO executado — bloqueado em provisionamento (ato do Vitor).**
Nada minerado, nenhum frame puxado, nenhuma credencial impressa. Documento completo:
`docs/decisions/mineracao-lote1-realidade-e-bloqueios.md`. Branch anterior (D-107..D-111) salva em **PR #385**.

### D-123 · A campanha real de mineração é passo humano no box — `CONFIRM_MINE` não existe
> ⚠️ Renumerado **D-112→D-123** na consolidação dos PRs #385/#386/#388 (D-112 já em uso na develop).

**16/08 · Claude · 📄 análise (sem código)**

**Medido no código.** `grep CONFIRM_MINE` = vazio; o gate citado no prompt **não existe**.
`replay_miner.main()` (`services/edge-sync-agent/app/collector/replay_miner.py:811`) roda **só o dry-run**.
Ligar a mineração real exige escrever um script curto **no pandora** que constrói `RecorderClient` +
`PersonDetector` + `TokenSource` e chama `ReplayMiner.mine(plan)` — **por desenho** não há entrypoint
automático (runbook `DVR_REPLAY_MINER.md`). Correções de fato ao prompt: **canal 8 é `ceiling`** (teto 60,
82% Botas), **não** presença — presença = `full` (1,4,11,12,19,23,28); ausência = canal 10
(`replay_miner.py:106`).

**Veredito: registrar a realidade.** A campanha real é **ato humano deliberado no box**, não autônomo da
nuvem. Anti-lockout embutido confirmado (401/403 → aborta run inteira, sem retry, `replay_miner.py:533-542`).

### D-124 · Lote 1 bloqueado — o que o Vitor provisiona (com escopo mínimo)
> ⚠️ Renumerado **D-113→D-124** na consolidação dos PRs #385/#386/#388 (D-113 já em uso na develop).

**16/08 · Claude · 📄 análise**

**Medido.** Para o Lote 1 rodar e cair no **DEV** (não em prod), faltam, todos ato do Vitor: **(1) token de
device DEV com escopo `frames:write`** — o upload é `POST /api/v1/edge/frames` que exige device JWT
`frames:write` (`edge/routes.py:587`), e o box está enrolado em **produção**; **(2)** confirmar presença da
cred DVR no box (só presença, ⛔ nunca o valor); **(3)** `RECORDER_CLOUD_ID` + `channel_map` DEV; **(4)** conta
de teste DEV + `E2E_ANNOT_PASSWORD`; **(5)** R2 read-only bucket DEV; **(6)** DEV DB read-only (senha vazada,
rotacionar). Detalhe/revogação por item no doc §2. **Falta no código:** o miner não tem teto TOTAL de crops —
para "~50 e para" precisa moldar o plano ou somar um `max_total_crops` (mudança P).

**Veredito: ⛔ nada criado por mim.** Especificado; aguarda provisionamento.

### D-125 · Medição da razão de ausência é impossível esta rodada — duplamente bloqueada
> ⚠️ Renumerado **D-114→D-125** na consolidação dos PRs #385/#386/#388 (D-114 já em uso na develop).

**16/08 · Claude · 📄 análise**

**Medido.** O bloco 4 pressupõe a "tela forçando estado por EPI" — mas **D-108 não está implementado**
(`SearchFindingsPanel.tsx:44` ainda é por-caixa; foi só decisão). E o export **inclui** hoje
`curation_status='duvida'` ("não sei") no pool — só `'excluida'` é filtrada (`versioning_v2.py:18-19,80-97`),
então o **passo 4 do percurso ("não sei não vai pro dataset") é FALSO hoje**. A razão ausência÷recorte exige
recortes reais (bloqueados, D-113) **e** a tela de veredito (inexistente) → não medível. Projeção só como
fórmula no doc §3 (⛔ não é medição).

**Veredito: registrar a impossibilidade.** O ~209 do dry-run contava só o já-anotado, não o potencial.

### D-126 · Veredito da meta de ausência: indeterminado, com condição objetiva de desbloqueio
> ⚠️ Renumerado **D-115→D-126** na consolidação dos PRs #385/#386/#388 (D-115 já em uso na develop).

**16/08 · Claude · 📄 análise**

**Honesto.** A meta 100+/classe de ausência é **plausivelmente alcançável se a razão medida for ≥ ~1
ausência/recorte** sob veredito forçado — mas isso é exatamente o que falta medir. ⏸️ **Adiar o veredito
até:** (1) token DEV `frames:write` provisionado, (2) Lote 1 real de ~50 recortes, (3) D-108 implementado.
Só então a razão vira número. ⚠️ Adiamento com **condição, não data** (evita o sumiço estilo briefing Frigate).

**Veredito: ⏸️ adiar até as 3 condições acima.**

---

## Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119)

Clone limpo de `origin/develop` em `/private/tmp/recognition-clean-develop` (111 migrations, nº máx 122 — a
árvore errada do iCloud tinha 12). Doc completo: `docs/decisions/rodada-consolidacao-e-modelo-ordenador.md`.
**Nenhum segredo impresso. Nada minerado. Nenhum PR fechado. Zero código de produto alterado.**

### D-127 · Modelo `8e8fedf7`: avaliação bloqueada; ordenador (não rotulador) desenhado + descope do bloco 3
> ⚠️ Renumerado **D-119→D-127** na consolidação dos PRs #385/#386/#388 (D-119 já em uso na develop).

**17/08 · Claude · 📄 análise**

**Bloqueado.** Avaliar o modelo contra os 377 frames de verdade exige R2 (ONNX 108 MB + frames) e DEV DB
(anotações) — sem credencial de nenhum. Nada baixado; a linha `trained_models 8e8fedf7` nem foi confirmada (sem DB).
#387 é o verificador R2 que destrava. **Desenho registrado** (doc §3): batch inference → `model_order_score`
nullable → fila existente `order_by=model_score`; ⛔ jamais rótulo/proposta (lição SAM+DINO 1005/100%-rejeitadas);
medir ganho (rolagem p/ achar 50 anotáveis, aleatório vs modelo) e **desligar se < ~1,5×**. Bloco 3 (laço de revisão)
**descopado** (prioridade era DEV testável) — quando vier, estender `curation_status`, ⛔ sem tela nova.
**DEV está no ar** (API+DB+Redis+frontend 200), menos a aba Classificar (D-117).

**Veredito: ⏸️ avaliar quando R2+DB provisionados (condição, não data).**

### D-128 · Rodada mergear+detector+recorte (2026-08-17): fila cheia, 23-postes refutado, blur recalibrado

**Contexto.** Prompt pedia (a) fechar fila de PRs, (b) "consertar detector antes de recortar" e medir vs 377 anotados, (c) recortar o acervo. Clone limpo de `origin/develop` (111 migrations, máx 122). Fase 1 (plano) aprovada pelo Vitor com 2 decisões: bloco 2 reformulado + consolidar docs num branch fresco.

**O que o repo/DB disseram (divergências medidas, segui o repo):**
- 🔴 Os **9.649 frames `nvr` JÁ SÃO RECORTES** de pessoa (avg 363×435, produzidos pelo coletor edge ao vivo — `person_detector.py` YOLOX-nano). Full-frame não é retido → **não dá pra rerodar o detector nem "recortar o acervo" (já é recorte)**.
- 🔴 Os "377 anotados" são **489** frames, e são **caixas de EPI SOBRE recortes** (+89 uploads 640²), **não** caixa-de-pessoa em full-frame → **recall/precisão/IoU vs ground-truth de detecção é IMPOSSÍVEL** (não existe verdade de pessoa). `model_confidence` é NULL nos 9.207 → confiança nem é medível no DB.
- 🔴 **"23/23 postes" REFUTADO por medição visual** (montagem de 144 recortes): precisão real ~**80-85%**; os falsos-positivos são **estruturas fixas em 2 câmeras** (775c = tambor metálico embrulhado; 7ad4 = poste listrado + carros), aparecendo como **rajadas de quase-duplicatas** — não "23/23 em todo lote".

**Bloco 2 reformulado (aprovado):** medir precisão por amostra + calibrar blur real + quarentena reversível.
- **Blur:** `_DEFAULT_BLUR_VARIANCE_MIN` 3000→150 (`replay_miner.py`, PR #389). Medido com a própria `blur_variance` sobre n=224 crops reais: mediana=693, p05=199; o 3000 rejeitava **98%**. Só afeta mineração futura (miner não deployado).
- **Dedup/quarentena (bloco 3.2):** dHash≤6 por câmera sobre 8.843 crops → **1.602 quase-duplicatas (18%)** marcadas `curation_status='excluida'` (reversível, mantém 1 representante/cluster). Pega as rajadas de estrutura fixa. Restam **7.241** crops limpos não-anotados.

**Fila + DEV (bloco 4, provado, não presumido):** #384 mergeado → aba Classificar no ar. E2E DEV: login (conta E2E) → assumir contexto RVB → `GET /api/training/images` devolve **7.623 recortes active** ranqueados por `missing_class`. API+Frontend 200; "Classificar" no bundle.

**Fila de PRs:** #387 mergeado (verificador R2). #384 mergeado (merge de develop→branch, sem force; `supercategory: module_code` preservado em `versioning_v2.py:402`; entradas D-105/106/107/112 do #384 renumeradas → **D-114/115/116/117**). npm-audit(landing) é vermelho pré-existente e **não-required** (develop não-protegida) → não bloqueia; fix real é upgrade Astro 4→7 (3 majors breaking) → **task isolada, não drive-by**. **Recomendo fechar** (ato do Vitor): **#375** (pode reverter #378), **#293**, **#259** — valor extraído; e **#385/#386/#388** — docs consolidados aqui.

**Pendências do Vitor (inalteradas):** rotacionar senha Postgres DEV (vazou); rebaixar `e2e-anotacao` de superadmin→anotador; token R2 read-only dedicado; provisionar o beat; deploy OTA do miner + 6 itens pra rodar o Lote 1 real. Ver docs consolidados nesta rodada.

**Nenhum segredo impresso.** Zero staging/main/interchange. Zero DELETE (só flag reversível).

---

### D-129 · O acervo misto era 0,7%, não 13% — e o dano era ZERO

**Status:** ✅ vigente · **↩ corrige D-121** (que dizia 8.413 recortes vs 1.254 frames inteiros)

O número anterior saiu de um limiar errado (`width >= 640`), que classificou **recorte grande**
(818×581, 1437×698 — pessoa perto da câmera) como frame inteiro.

**Discriminador correto:** frame inteiro tem a resolução do stream, então a MESMA dimensão se repete
muitas vezes; recorte tem o tamanho da caixa da pessoa, logo dimensão praticamente única.

| | Antes (errado) | Medido |
|---|---|---|
| Frames inteiros no RVB | 1.254 | **615** (todos `704x480`, a única dimensão repetida) |
| Fila da aba Classificar | ~13% contaminada | **0,7%** — 51 de 7.222 |
| **Classificações caídas em frame inteiro** | a apurar | **ZERO** |

**Conserto aplicado:** parâmetro `only_crops` em `GET /training/images`, aplicado pela aba Classificar
(`FrameRepository.list_images_filtered`). Auto-detecta resolução de câmera nova sem deploy.
**Teto conhecido:** se o coletor passar a emitir recorte de tamanho fixo, ele seria excluído por engano —
aí vira coluna `frame_kind` gravada na ingestão.

**Não houve dano a reverter.** Nada foi marcado para revisão porque não havia o que marcar.

---

### D-130 · A aba Classificar NUNCA conseguiu salvar — 400 permanente, não falha de rede

**Status:** ✅ vigente · **causa raiz das "14 aprovações não sincronizadas"**

`AnnotationService._validate_class` rejeita o batch INTEIRO com 400 se `class_name` ou `module_code`
vierem vazios. O `buildApprovalPayload` da aba Classificar montava só `{class_id, x_center, y_center,
width, height}`. O Estúdio, que funciona, sempre mandou os dois (`boxToPayload`, studioTypes.ts:94).

**Por isso as 599 anotações do RVB vieram todas do Estúdio e nenhuma da aba Classificar.**

O erro **nunca foi transitório** — nenhum retry resolveria, e o desenho de persistência (localStorage
antes do POST, replay no mount) estava certo o tempo todo: guardava fielmente um payload que o servidor
sempre ia recusar.

**Consertado em três pontos** (caixa nova, anotação preservada, desfazer) + **reparo das pendências já
gravadas** no localStorage antes de reenviar, para que o trabalho já feito pelo Vitor não se perca.

**Correções de honestidade do aviso:** o banner dizia "nada foi perdido" sem dizer por quê. Agora diz
**a causa real** e que o trabalho está guardado no navegador. Retry com recuo só para erro transitório —
4xx é permanente e some do banner com o motivo, em vez de girar em silêncio.

⚠️ **A hipótese "está em memória e recarregar perde" era falsa** — sempre esteve em `localStorage`.

---

### D-131 · O export trocava o rótulo de 111 boxes e descartava 19 — não havia duplicata nenhuma

**Status:** ✅ vigente · **↩ corrige D-123**, que estava errada de ponta a ponta

D-123 afirmava que o mesmo conceito tinha dois `class_id` e que 78% dos boxes estavam partidos.
**Não existe duplicata.** O `class_name` gravado na própria linha mostra o que o humano escolheu:
`class_id` 0/1/4/5/6/7 são **classes do catálogo** (`module_classes`: Capacete, Sem Capacete, Luvas,
Sem Luvas, Óculos, Sem Óculos). `class_id` 100004+ são as classes do tenant. **Classes diferentes.**

O defeito estava só no **export**, que reconstruía o nome via `JOIN yolo_classes` — violando a regra que o
próprio repositório documenta (*"class_name é armazenado na própria linha (task-077), NUNCA reconstruído
via JOIN em yolo_classes"*):

| Verdade gravada | Exportado como | Efeito | Boxes |
|---|---|---|---|
| Óculos | **mascara** | rótulo trocado | 79 |
| Sem Óculos | **Sem protetor de ouvido** | rótulo trocado | 26 |
| Luvas | **Protetor auditivo** | rótulo trocado | 5 |
| Sem Capacete | **hardhat** (tenant `e2e`) | rótulo trocado **cross-tenant** | 1 |
| Sem Luvas | — | descartado (classe arquivada) | 18 |
| Capacete | — | descartado (join não acha) | 1 |

**130 de 599 boxes (21,7%)** corrompidos ou perdidos em todo export. O modelo aprenderia "mascara" a
partir de fotos de óculos.

**Consertado:** `class_name` vem da linha; o `LEFT JOIN` sobrou só para checar classe custom aposentada,
**escopado por tenant** (fecha a leitura cross-tenant, C-01).

⛔ **NENHUM `UPDATE` em `frame_annotations` foi executado** — as anotações estavam corretas.
Backup preventivo mesmo assim em `~/Logikos-mutirao/backups/frame_annotations_pre_remap_2026-08-17.csv`
(857 linhas, fora do repositório).

⚠️ **"Protetor auricular" tem ZERO anotações** — a mescla autorizada em `Protetor auditivo` ficou sem
objeto. Nada foi mesclado.

---

### D-132 · Redirecionar o botão Ativar não era "uma linha" — o endpoint com gate não fazia hot-reload

**Status:** ✅ vigente

Os dois caminhos de ativação divergiam em mais do que o gate:

| | `/training/models/<id>/activate` | `/api/v1/models/<id>/activate` |
|---|---|---|
| Gate campeão×desafiante | ⛔ não | ✅ 409 `eval_rejected`, force só admin |
| Publica `model:reload` | ✅ sim | ⛔ **não** |
| Escopo | por `user_id` | por `tenant_id` |

Redirecionar cru teria consertado a governança e **quebrado o deploy do modelo** — o inference-service
seguiria servindo o modelo antigo, em silêncio. Uma falha silenciosa trocada por outra.

**Consertado:** `_publish_model_reload` adicionado ao handler com gate, **depois** o redirecionamento.
A mensagem do 409 foi reescrita para o usuário final (antes dizia "reenvie com `force=true`", jargão de
API que vazava na tela via toast automático do `api.ts`).

**Sobre o endpoint sem gate — recomendação, não executada:** ⏸️ **manter por ora, com aviso no docstring.**
Motivo: o módulo Qualidade tem rota homônima porém distinta (`/api/v1/quality/training/models/<id>/activate`,
por câmera) e nenhum consumidor foi auditado fora do frontend. **Condição para remover:** quando um `grep`
por chamadas a `/training/models/*/activate` em todos os apps do monorepo e nos scripts de ops voltar
vazio por duas rodadas seguidas.

---

### D-133 · Arquivar câmera: a autorização comparava tenant com usuário, e o `DELETE` é destrutivo

**Status:** ✅ vigente

**O erro relatado tinha causa exata:** `camera_service.delete_camera` fazia
`if str(camera["tenant_id"]) != str(user_id)` — dois identificadores de entidades diferentes.
Para qualquer não-admin isso é sempre verdadeiro, então **sempre negava**.

**Consertado:** compara tenant com tenant; cross-tenant responde **404, nunca 403** (C-01);
override por `is_admin` preservado como estava.

**O `DELETE` é destrutivo de verdade** — `cameras` é referenciada com `ON DELETE CASCADE` por
`alerts`, `camera_events`, `counting_sessions`, `demo_videos` e `operations`; e por `NO ACTION` em
`training_frames`, `model_deployments`, `model_drift_metrics`. Numa câmera com histórico ele trava por FK;
numa câmera sem frames ele passa e **leva os alertas e as operações junto, em silêncio.**

**Novo caminho:** `POST /api/cameras/<id>/archive` e `/restore` — `is_active=false`, reversível.
⛔ Zero `DELETE` executado nesta rodada.

🔴 **E o que importa de verdade:** fila de anotação **e** export do dataset passam a ignorar câmera
arquivada. Sem isso arquivar seria cosmético e o modelo continuaria aprendendo de câmera descartada.
Frame de upload/vídeo (sem `camera_id`) não é afetado.

**⏸️ Tirar o `DELETE` do ar fica adiado**, por decisão do Vitor — alcance próprio.
**Condição de reabertura:** quando existir tela de arquivamento em uso e nenhum consumidor do
`DELETE /api/cameras/<id>` for encontrado no monorepo.

---

### D-134 · A lista de câmeras a arquivar não bate com o banco — 2 aplicadas, 2 BLOQUEADAS

**Status:** 🔄 em execução · **exige decisão do Vitor**

A numeração é de canal e **casa** com `public.cameras.channel` (1–29). O **estado** é que não bate:

| Canais | Descrito como | Banco diz | Ação |
|---|---|---|---|
| 13, 14, 17, 18 | fora do EPI | **já arquivadas** (`is_active=f`) | nada a fazer |
| 22, 25 | fora do EPI | ativas, 0 frames anotados | ✅ **arquivadas** |
| **3** | módulo Qualidade | 🔴 `module_code='epi'`, **1.000 frames**, 1 anotado | ⛔ **BLOQUEADA** |
| **27** | módulo Qualidade | 🔴 `module_code='epi'`, 50 frames | ⛔ **BLOQUEADA** |

**Por que 3 e 27 não foram tocadas:** as duas estão marcadas como **EPI**, não Qualidade. E o canal 3 tem
**1.000 frames** — o mesmo volume dos canais 1–8, que são os coletores de produção. Arquivar tiraria esse
material do treino (é exatamente o que D-133 passou a fazer). Um canal de produção rotulado como
"Qualidade" por engano custaria 1.000 frames.

**Também fora da lista, já arquivados:** canais 9, 15, 16.

**Pergunta para o Vitor:** os canais 3 e 27 são mesmo Qualidade? Se forem, o `module_code` no banco está
errado e o conserto é reclassificar, não arquivar.

---

### D-135 · Numeração `D-` colidiu de novo — inclusive comigo

**Status:** ✅ vigente

O PR #390 mergeou D-118..D-128 enquanto o PR #391 (auditoria da aba de Treinamento) estava aberto com
D-120..D-129. **O #391 ficou `CONFLICTING` e suas decisões colidem com as da develop.**

É a segunda colisão em duas rodadas — a primeira foi entre a develop e as PRs #385/#386/#388 (8 números).

**Ação pendente do Vitor:** o #391 precisa ser renumerado a partir de **D-136** antes de mergear, ou
fechado com o conteúdo portado. As decisões desta rodada (D-129..D-135) já nascem depois do D-128 vigente.

**Regra que sai daqui:** conferir o último `D-` **em `origin/develop` no momento do commit**, não no
momento em que a rodada começou. Rodada longa + PR de docs paralelo = colisão garantida.

---

### D-136 · Sobre as PRs #385/#386/#388: nada de substância se perdeu no #390

**Status:** ✅ vigente · **recomendação — ⛔ nenhuma PR foi fechada por mim**

Verificado branch a branch: os D-110/D-111/D-112 **não sumiram, foram renumerados** para D-121/D-122/D-123,
com títulos idênticos. `docs/decisions/licoes-repo-aws-ppe-dois-estagios.md` **está** em develop.

Ficaram de fora **três decisões-meta sobre estado de PR** (branch D-116/D-117/D-118), e uma delas
("#384 não mergeado") **já era falsa** quando o #390 foi escrito.

**Recomendação: pode fechar #385 e #386** — o #388 já não consta como aberto. Antes de fechar, vale
preservar num comentário o que a branch D-118 recomendava: **fechar também #375, #293 e #259**, cujo
valor já teria sido extraído. Não verifiquei essa última afirmação nesta rodada.
### D-137 · O gargalo do flywheel não é modelo nem dado — são dois passos que só existem como API

**Rodada:** auditoria da aba de Treinamento (2026-08-17) · **Status:** ✅ vigente
**Evidência:** clone fresco de `origin/develop` em `/Users/vitoremanuel/Logikos-mutirao/audit-training`,
HEAD `98056cf7`, 111 migrations (máx. `122`). Banco DEV, tenant `rvb`.

O ciclo de treino está **inteiro construído** — captura no edge, extração de NVR, curadoria, estúdio de
anotação, classificação por recorte, propagação SAM+DINOv2, busca OWLv2, export COCO com split por
câmera+dia, dispatch para GPU, verificação de artefato, avaliação campeão×desafiante, hot-reload.

**E produziu 0 modelos ativos.**

Dois passos obrigatórios existem no backend e **não têm nenhuma tela**:

| Passo | Endpoint | Chamador no frontend |
|---|---|---|
| Extração de frames do NVR — origem de **100%** do acervo RVB | `POST /api/v1/recorders/<id>/extract-frames` (`recorders/routes.py:162`) | ⛔ zero — "recorder" não aparece **nenhuma vez** em `apps/frontend/src` |
| Export do dataset COCO — **pré-requisito de todo treino** | `POST /api/v1/datasets/<id>/versions` (`datasets/routes.py:104`) | ⛔ zero — as 14 ocorrências de "dataset" são tooltip, tipo e texto de admin |

**Consequência medida:** 12 training jobs, **9 `failed`** (o dispatch levanta erro correto quando não há
`coco_r2_key`), 2 `completed`, 1 `stopped`. E o beat diário de auto-treino **pula em silêncio** —
`auto_train_skip` é log INFO (`auto_training.py:161-163`), nada chega à tela.

**A decisão:** parar de tratar isto como problema de modelo ou de volume de dados. **É problema de correia.**
Dos 8 itens do TO-BE, **4 são ligar frontend a backend que já existe e já está testado.**

⚠️ **Isto NÃO é "o endpoint não existe".** É o inverso — e a distinção é a que uma rodada anterior errou.

---

### D-138 · O acervo é MISTO  ↩ SUBSTITUÍDA por D-129 (medição posterior: 615 frames inteiros, não 1.254)

> ⚠️ Mantida por ser append-only. **O número desta entrada está errado** — ver D-129, que mediu
> 0,7% de contaminação e dano ZERO. Registrada aqui só para o erro ficar rastreável.

#### Texto original — nem "frames inteiros", nem "recortes de pessoa"

**Status:** ✅ vigente · **↩ corrige** a afirmação da rodada anterior (frames inteiros) **e** a correção do
briefing desta rodada (recortes desde sempre). **As duas estavam erradas.**

| Tipo | Frames RVB | Anotados | Dimensões |
|---|---|---|---|
| **Recorte de pessoa** (`width` < 640) | **8.413 (87%)** | 350 | 33×36 a 639×907 |
| **Frame inteiro** (`width` ≥ 640) | **1.254 (13%)** | 60 | 640×154 a 1437×934 |

Estão na **mesma tabela `public.training_frames`, sem nenhuma coluna que os distinga.**

**Causa:** o coletor do edge só recorta se o detector de pessoa estiver configurado E pronto; em 3 pontos
`_payload_para_upload` cai para o frame inteiro (`collector_loop.py:171-213`, `person_detector.py:340`).

**Consequência viva:** a aba Classificar (mergeada hoje pela #384) carrega a fila com
`GET /training/images?is_annotated=false&curation_status=active` — **sem filtro de tipo**
(`CropClassifier.tsx:243-256`). Cerca de **13% das perguntas "esta pessoa está de máscara?" são feitas
sobre uma cena inteira com várias pessoas** — pergunta que não tem resposta.

**A decisão:** marcar o tipo na ingestão (migration forward-only, coluna nova + backfill por `width`/`height`)
e filtrar a fila da aba Classificar. Sem isso, todo veredito por recorte carrega 13% de ruído estrutural.

---

### D-139 · O botão "Ativar" chama o endpoint SEM gate — e o gate já existe, testado

**Status:** ✅ vigente

Existem **dois** caminhos de ativação de modelo:

| Caminho | Gate de avaliação |
|---|---|
| `POST /training/models/{id}/activate` — `training/job_handlers.py:265-280` | ⛔ **nenhum** |
| `POST /api/v1/models/{id}/activate` — `models/registry_handlers.py:244-284` | ✅ 409 `eval_rejected` se `verdict='reject'`; `force=true` só admin/superadmin; 404 cross-tenant |

O botão "Ativar" da aba Modelo (`TrainingPage.tsx:244`) chama **o primeiro**.
`trainingService.ts:49` e `useTraining.ts:88` idem. **Nada no frontend chama o segundo.**

E a avaliação campeão×desafiante **roda sozinha a cada treino bem-sucedido**
(`training.py:311-316` dispara `evaluate_challenger_model`), grava `verdict` em `model_evaluations`,
e o resultado **não aparece em lugar nenhum da tela**.

**Resultado:** um modelo que o próprio sistema já reprovou é ativado com um clique, em silêncio.

**A decisão:** redirecionar a chamada do frontend para o endpoint com gate e tratar o 409.
É o item de **maior retorno sobre esforço da rodada** — esforço P, e fecha um furo de governança de modelo.

---

### D-140 · O export COCO parte conceitos ao meio  ↩ SUBSTITUÍDA por D-131 (não havia duplicata)

> ⚠️ Mantida por ser append-only. **A premissa desta entrada está errada** — ver D-131: os `class_id`
> pequenos são classes do CATÁLOGO, não duplicatas. O defeito real era o JOIN do export.

#### Texto original — `class_id` duplicado por nome

**Status:** ✅ vigente · **adendo a D-109** (que resolveu o "export devolvia ZERO classes custom" e, ao
resolver, deixou este resíduo)

O namespacing de classe custom **funciona** (`class_namespace.py`, `TENANT_CLASS_ID_OFFSET = 100_000`).
⚠️ **Correção de erro cometido dentro desta auditoria:** um subagente concluiu que as anotações apontavam
para classes inexistentes, porque juntou só contra `module_classes`. **Errado** — 12 das 13 resolvem.

O defeito real é outro: **o mesmo conceito tem dois `class_id`.**

| Conceito | `class_id` | Boxes |
|---|---|---|
| Protetor auditivo | 100004 **e** 4 | 197 + 5 |
| mascara | 100006 **e** 6 | 114 + 79 |
| Sem protetor de ouvido | 100007 **e** 7 | 45 + 26 |

E o export monta as categorias COCO **chaveando por `class_id`, não por nome**
(`versioning_v2.py:393-398`: `seen.setdefault(ann["class_id"], ...)`).
**O dataset sai com duas categorias homônimas por conceito, e os exemplos ficam partidos entre duas
classes que o modelo trata como diferentes.**

**466 dos 599 boxes (78%) estão afetados.**
Mais: `class_id=0` não resolve para nada (1 box), e `hardhat` (1) contraria D-103.

A duplicata está **viva, não é resíduo de migração**: os dois espaços foram gravados **nos mesmos dias**
(ambos até 13/08). Nasce em `ModuleClassesPage.tsx`, que oferece "Suas classes" e "Catálogo do módulo"
lado a lado, com nomes equivalentes.

**A decisão:** consolidar por nome no export **e** parar de oferecer as duas listas na anotação.
Duas frentes — corrigir o passado (export) e fechar a torneira (interface).

---

### D-141 · ⛔ NÃO construir orquestração assíncrona para o Estágio 2 — e ⏸️ o Estágio 2 em si fica adiado

**Status:** ⏸ adiada (o Estágio 2) + ⛔ não construir (a orquestração)

**O que NÃO vamos construir, e por quê:** fila, tabela nova ou state-machine dedicada para o
loop recorta→classifica. Motivo: **não há dor de orquestração para resolver — o Estágio 2 nem está servido**
(`detectors.py:169-216` é single-stage; grep por `stage_2`/`masked_bce` volta vazio). O risco real é de
inércia: os padrões assíncronos do repo (`propagation_jobs`, `search_jobs` — Celery + tabela + polling)
serão reaproveitados por hábito. Quando o Estágio 2 for construído, **loop síncrono**.
*(Guardrail equivalente já registrado como D-109 na PR #385, ainda não mergeada — ver D-142.)*

**O Estágio 2 em si — ⏸️ adiado com CONDIÇÃO OBJETIVA, não data:**
> **quando houver ≥500 recortes com veredito humano completo (present/absent/N-A por classe)
> E o FPS do Estágio 2 medido no Orin mantiver as 28 câmeras com folga.**

Hoje não é possível decidir: o veredito por recorte acabou de ganhar tela (aba Classificar, #384) e não há
lote classificado que permita dimensionar o ganho. **Adiar sem gatilho é como o briefing do Frigate sumiu.**

---

### D-142 · A cadeia de PRs de documentação colidiu em 8 números `D-` e já nasceu desatualizada

**Status:** ✅ vigente · **exige ação humana do Vitor**

`develop` e a cadeia aberta #385 → #386 → #388 usam os **mesmos números para decisões diferentes**:
**D-107, D-108, D-109, D-113, D-114, D-115, D-116, D-117** — oito colisões.

Pior: **o D-117 da PR #388 afirma "#384 não mergeado"** — e #384 foi mergeada em `98056cf7`,
durante esta auditoria. A cadeia de docs descreve um estado que já não existe.

**Decisões desta auditoria numeradas a partir de D-137** para não agravar.

**Ação pendente (Vitor, gate humano):** decidir se as PRs #385/#386/#388 são renumeradas antes do merge
ou se o conteúdo é portado. **Merge como está reescreve 8 decisões vigentes da `develop`.**

---

### D-143 · A propagação tem 100% de rejeição — e o motivo não é gravado, então NÃO se pode concluir nada sobre ela

**Status:** ✅ vigente (a decisão é sobre instrumentar, não sobre julgar a propagação)

| Propagação semeada (SAM + DINOv2), tenant RVB | |
|---|---|
| Frames com proposta gerada | **974** |
| Aprovadas | **0** |
| **Rejeitadas** | **974 (100%)** |
| Jobs | 8 completados, 5 falhados |

**E o motivo da rejeição não é gravado em lugar nenhum.**

Isto admite **três causas com tratamentos opostos**:
1. as propostas são ruins → melhorar ou desligar o motor
2. foi limpeza de fila em lote → o dado não diz nada sobre qualidade
3. rodou sobre o acervo misto (D-138) e produziu caixas sem sentido nos frames inteiros → o defeito é o
   acervo, não a propagação

**A decisão é explicitamente NÃO concluir qual é.** Instrumentar primeiro: ao rejeitar, três botões
(`caixa errada` / `classe errada` / `imagem imprestável`) + campo livre opcional.
**⛔ Não construir taxonomia de motivos agora** — refinar depois de 100 rejeições classificadas.

⚠️ Registrado como **dúvida reportada**, não como veredito sobre a propagação.

---

### D-144 · "Em dúvida" não pausa o frame — e 1 em cada 5 frames do RVB já está excluído

**Status:** ✅ vigente

`curation_status='duvida'` **não remove o frame do export** — só `'excluida'` remove.
`versioning_v2.py:80-83` admite em comentário: *"duvida CONTINUA entrando — ainda não há decisão humana"*.
São **36 frames** entrando no treino sem decisão, e a tela mostra só um chip, sem avisar disso.

**Segundo achado, do mesmo lugar:** o acervo se moveu **durante a auditoria**.
Início da rodada: `active 9.225 / excluida 406`. Fim: `active 7.605 / excluida 2.026` —
**~1.620 frames excluídos em 2026-08-17 22:16.**
**21% do acervo RVB está fora da curadoria** — e nada na tela mostra essa proporção.

**A decisão:** (a) tornar o texto de "em dúvida" honesto sobre o que ele faz e não faz;
(b) mostrar a proporção excluído/ativo na aba Imagens, porque 21% de descarte é um sinal
sobre a qualidade da coleta que hoje ninguém vê.

---

### D-145 · Onde já fazemos MELHOR que os benchmarks — 7 pontos, para não reconstruir o que já é bom

**Status:** ✅ vigente

O confronto com o AWS PPE (e o que restou do Frigate) confirmou os dois pontos esperados e revelou mais cinco:

| Fazemos melhor | Onde | O benchmark faz |
|---|---|---|
| Split por vídeo ou câmera+dia | `versioning_v2.py:175-199` `_group_key` | random 20% por imagem → vaza |
| Avaliação campeão×desafiante automática | `model_evaluation.py:181`, disparada por `training.py:311` | 100% manual |
| Meta de dados por classe computada em código | `coverage_service.py:11-38` (100 img, ≥5 câm, ≤50%) | "mínimo 10", sem base |
| Fila humana aprovar/rejeitar/corrigir | `VerificationQueuePage.tsx` + V/X no Estúdio | não tem loop de revisão |
| Artefato verificado antes de "completed" | `training.py:33-37` + `verify_model_artifact` | não trata |
| Limiar de confiança configurável | `ZoneTuningForm.tsx` + `inference/config.py:17` | caixa-preta gerenciada |
| Treino que exporta ONNX real (não preso a SaaS) | `training/vast/remote_train.py` | Custom Labels não exporta |

**A decisão:** estes 7 pontos **não entram em nenhuma proposta de reforma.** Já estão certos.
A reforma da aba mira exclusivamente o que está medido como quebrado (D-137 a D-140, D-143, D-144).

---

### D-146 · ⛔ O briefing do Frigate nunca existiu como arquivo — e é por isso que ele "sumiu"

**Status:** ✅ vigente

O briefing desta rodada afirma que `docs/decisions/BRIEFING_PADROES_FRIGATE_AWS.md` está no repositório.
**Não está — em nenhuma das 172 branches remotas, em nenhum ponto do histórico, em nenhum disco local.**

Verificado por `git grep -il "frigate"` sobre todas as branches remotas (só acha
`docs/research/PESQUISA_CV_30_CAMERAS.md` e `Roccatextil/arquitetura-plataforma-multitenant.md`),
por `git log --all --diff-filter=AD -- '*FRIGATE*'` (vazio) e por `find` no disco.

O briefing diz que o documento do Frigate *"virou documento e sumiu do conjunto de trabalho"*.
**Ele não chegou a virar documento.** Nunca foi commitado.

**A decisão:** avaliação que não vira arquivo commitado **não existe** na rodada seguinte.
Toda rodada de avaliação/benchmark termina com **arquivo commitado + entrada neste registro** —
inclusive quando a conclusão é "não vamos fazer". Foi exatamente esse o buraco que custou o Frigate.

---

### D-147 · `develop` já tem referência cruzada QUEBRADA — a colisão de `D-` deixou de ser hipotética

**Status:** ✅ vigente · **corrige referências, não decisões**

D-129 diz *"↩ corrige D-121"* e D-131 diz *"↩ corrige D-123"*. Ambas foram escritas apontando para as
entradas do PR #391, que **nunca mergeou**. Em `develop`, D-121 é *"⛔ NÃO adotar AWS servida"* e D-123 é
*"a campanha real de mineração é passo humano no box"* — **nada a ver**.

**Referências corretas:** D-129 corrige a entrada agora portada como **D-138**; D-131 corrige a **D-140**.

Não é um erro de conteúdo — as duas decisões estão certas no que afirmam. É o **índice** que apodreceu,
e apodreceu porque dois PRs escreveram no mesmo arquivo append-only em janelas sobrepostas.

---

### D-148 · Proposta: um arquivo por decisão — o `REGISTRO` virou mutex global

**Status:** ⏸ proposta — ⛔ NÃO implementada nesta rodada

**Três colisões em três rodadas**, agora com dano medido (D-147). A causa não é descuido: é que
`docs/REGISTRO_DE_DECISOES.md` é **um arquivo append-only tocado por todo PR**, então dois PRs
paralelos colidem por construção. Os ADRs (`docs/decisions/adr/`) nunca colidiram assim — **porque são
um arquivo por decisão.**

**Proposta:** `docs/decisions/d/D-NNN-slug.md`, um arquivo por decisão, e o `REGISTRO_DE_DECISOES.md`
vira índice gerado.

| Peça | Esforço |
|---|---|
| Script de split do arquivo atual (147 entradas) em arquivos | **P** — parsing por `^### D-` |
| Gerador do índice + check de CI (índice bate com os arquivos) | **P** |
| Guard de numeração no CI (recusa `D-` duplicado entre PRs abertos) | **P** — já existe precedente: `Migrations collision guard` |
| Reescrever links `[[D-NNN]]` existentes | **M** — há referências cruzadas em docs e ADRs |
| **Total** | **M** (1 rodada dedicada) |

**Ganho:** dois PRs só colidem se tocarem a MESMA decisão. Hoje colidem sempre.
**Condição para fazer:** próxima rodada que não tenha experimento em curso — ⛔ não misturar com dado.

---

### D-149 · Teste desativado é dívida silenciosa — proposta de regra

**Status:** ✅ vigente

Os três testes de `delete_camera` foram desativados via `--deselect` em junho
(`tools/agent-driver/config.yaml`), com o bug documentado em
`docs/quality/AUDITORIA_2026-06-21.md:50-52`. **Ficaram dois meses apagados**, e o bug que eles pegavam
era exatamente o que impedia o Vitor de arquivar câmera.

Reativados nesta rodada — os três passam.

**Regra proposta:** todo `--deselect` novo exige entrada `D-` com **condição objetiva de reativação**
(ex.: *"reativar quando X for corrigido"*). Sem isso, `--deselect` é indistinguível de "apagamos o alarme".
Um check de CI que recuse `--deselect` sem `D-` referenciado no mesmo commit custa **P**.

---

### D-150 · Sondagem × coleta: 1.000 dos 9.667 frames do RVB são amostra rala, e nenhum foi anotado

**Status:** ✅ vigente · ⛔ nada mutado

| | Canais | Frames | Anotados | Janela de captura |
|---|---|---|---|---|
| **Coleta real** | 1–8 | **8.667** (89,7%) | 410 | 3,6 a 10,9 dias |
| **Sondagem** | 10–29 (20 canais) | **1.000** (10,3%) | **0** | 45 min a 4,8 dias |

**Não são quadros do mesmo instante** — as janelas vão de 45 min (canal 28) a 4,8 dias (canal 19).
São amostra rala no tempo, não duplicata. **Não contaminaram nenhum treino** (zero anotados).

**Canal 27 NÃO arquivado** (decisão do Vitor): 50 frames em ~7.600 é ruído, arquivar não ganha nada e
perde opção. **Canal 3 NÃO arquivado** — é Qualidade mas serve para anotar EPI, e o `module_code='epi'`
está coerente com o uso; ⛔ não "corrigir" para Qualidade.

---

### D-151 · O botão "Excluir" câmera deve ARQUIVAR — a recomendação inverteu

**Status:** ⏸ proposta — ⛔ NÃO implementada

Achado: `DELETE /api/cameras/<id>` **não está esquecido** — está exposto ao usuário final em
`CamerasPage.tsx:108` (botão "Excluir" + `ConfirmDialog`) via `cameraService.ts:188`. E apaga em
**CASCADE** `alerts`, `camera_events`, `counting_sessions`, `demo_videos` e `operations`.

**Isso piora o quadro, não melhora:** o endpoint destrutivo é de uso corrente.

**Recomendação: o botão passa a chamar `POST /cameras/<id>/archive`** (já existe, veio no #392).

| Peça | Esforço |
|---|---|
| Trocar `cameraService.delete` por `archive` + copy do diálogo | **P** |
| Mostrar câmera arquivada na lista com selo + ação "Restaurar" | **P/M** |
| Manter `DELETE` só para admin, ou tirar do ar | **decisão do Vitor** |

⚠️ **A tela de triagem (`CameraTriagePage`) NÃO faz isso hoje** — ela triaga descoberta de câmera, não
ciclo de vida. Não há o que reaproveitar; é tela de câmeras mesmo.

---

### D-152 · Consumidores dos dois endpoints — determinado

**Status:** ✅ vigente

| Endpoint | Consumidor | Veredito |
|---|---|---|
| `POST /api/training/models/<id>/activate` (sem gate) | Só `trainingService.ts:50`, e **nenhuma tela o chama** (o `useTraining` não é montado em lugar nenhum; `CameraModelAssignment` só usa `listModels`). O `qualityService` chama rota **diferente** (`/v1/quality/training/models/...`, por câmera) | **Pode sair** — esforço **P**. Remover o método morto de `trainingService.ts` e a rota |
| `DELETE /api/cameras/<id>` | **TEM consumidor vivo** — botão "Excluir" | ⛔ **Não tirar do ar** sem antes fazer o botão arquivar (D-151) |

---

### D-153 · Risco registrado: advisory novo do `sharp`/libvips quebra o CI do landing

**Status:** ⚠️ risco aberto — ⛔ NÃO consertado nesta rodada

`SCA (npm audit) (landing)` falha com `sharp <0.35.0` herdando CVE-2026-33327/33328/35590/35591 do
libvips (`GHSA-f88m-g3jw-g9cj`), via `astro`. **Não é pré-existente** — a `Security Scan` da `develop`
passou às 22:29 de 17/08; o advisory saiu depois. **A `develop` vai ficar vermelha no próximo push.**

**Correção conhecida:** `npm audit fix --force` instala `astro@7.2.2` — **breaking change**.

⛔ Não feito aqui de propósito: bump de astro no meio de uma rodada de dados trocaria duas variáveis.
**Condição:** rodada própria, sem experimento em curso.

---

### D-154 · Comparativo dos dois exports: 556 → 574 boxes, 7 → 12 categorias

**Status:** ✅ vigente · **previsão registrada ANTES do TREINO 2**

Mesmo dado, única variável alterada = o export.

| Categoria | Antigo | Novo |
|---|---|---|
| Protetor auditivo | 198 | 193 |
| **mascara** | **188** | **111** |
| Sem protetor de ouvido | 66 | 41 |
| Botas · Sem mascara · Uso incorreto | 48 · 33 · 22 | iguais |
| `hardhat` (tenant e2e) | 1 | **0** — vazamento cross-tenant fechado |
| Óculos · Sem Óculos · Luvas · Sem Luvas · Capacete · Sem Capacete | — | 77 · 25 · 5 · 17 · 1 · 1 |
| **Total** | **556 · 7 cat.** | **574 · 12 cat.** |

O total antigo (556) bate exatamente com `provenance.humana: 556` gravado no `metrics` do TREINO 1 —
**a query antiga reproduz o export real daquele treino.**

**PREVISÃO, escrita antes de treinar:** *"mascara" cai de 188 para 111 boxes (−41%). **Se a precisão de
"mascara" SUBIR mesmo com 41% menos dado, é prova de rótulo.** Se cair, foi volume. Se ficar igual, os
dois se anularam.* Baseline TREINO 1: precisão **0,4375**, recall 0,1321, F1 0,2029 (tp 14, fp 18, fn 92),
avaliado no split **test** de **179 imagens** — ⛔ não no val de 6.

⚠️ ⛔ Não haverá comparação classe a classe: 12 categorias contra 7 não são comparáveis. **O sinal é a
precisão de "mascara".**

---

### D-155 · `gpu_cost.actual_usd` ficou NULL no TREINO 1 — por quê

**Status:** ✅ vigente

O `metrics` do job `10feb67b` traz `gpu_cost: {price_usd_h: 0.22, estimated_usd: 0.22, actual_usd: null}`.
O **estimado** é gravado no dispatch; o **real** dependeria de consultar o custo do pod **depois** de
morto, e esse passo não existe — o runner mata o pod e encerra.

É a **mesma lacuna** que produziu o órfão de US$ 21,54: o sistema sabe estimar e sabe matar, mas não
fecha a conta. `gpu_instance_ref` **É** gravado (`63armpimqkz3km` no TREINO 1), então a consulta pós-morte
é possível — só não é feita.

**No TREINO 2 o custo real será gravado**, consultando o pod pelo `gpu_instance_ref` após a morte.

---

### D-156 · Deploy por git ganha do `railway up` quando o commit está na branch — regra corrigida

**Status:** ✅ vigente · **↩ corrige orientação dada na própria rodada anterior**

A orientação era: `git archive` → diretório limpo → `railway up`. **Naquele contexto isso piorou.**
O que aconteceu no DEV em 18/08:

| Deploy | Proveniência |
|---|---|
| 00:03 — auto-deploy do merge do #392 | ✅ `commitHash b769ede5` |
| 00:12 — `railway up` de outra sessão | ⛔ sem `commitHash` — sobrescreveu o bom |
| 00:22 — `railway up` meu, seguindo a orientação | ⛔ sem `commitHash` |

**Um deploy com proveniência foi trocado por dois sem.**

**Regra:** se o auto-deploy por git está ligado e o commit já está na branch, **⛔ não use `railway up`** —
deixe o git deployar. `railway up` é para o que **não** é commit (árvore local, teste de algo não
comitado); aí sim vale a trava do `git archive` para não subir lixo do worktree.

---

### D-157 · `/livez` passa a dizer qual commit está servindo

**Status:** ✅ vigente

Não havia como perguntar à API que código ela roda. Isso mordeu **duas vezes numa semana**: um
`railway up` sobrescreveu um deploy por git e ninguém conseguiu provar o que estava no ar.

`GET /livez` agora devolve `commit`, lido de `RAILWAY_GIT_COMMIT_SHA` no import
(`services/api/app/api/v1/health/routes.py`). Sem autenticação de propósito — **SHA de commit não é
segredo**, e a pergunta "o que está no ar?" precisa ser respondível **mesmo com o banco fora** (por isso
`/livez`, que nunca toca dependência, e não `/health`).

🔴 **`"unknown"` não é degradação silenciosa — é o sinal.** Deploy por git sempre traz o SHA; upload
local (`railway up`) nunca. Ver `commit: "unknown"` é a denúncia automática de um deploy sem
proveniência, exatamente o caso de D-156.

---

### D-158 · "Achei o bug num método" ≠ "achei o PADRÃO"

**Status:** ✅ vigente · **lição de processo**

O #392 consertou `delete_camera` (`camera["tenant_id"]` comparado com `user_id`) e **declarou o bug
resolvido**. Tinha **três irmãos vivos** com a linha idêntica:

| Método | Efeito |
|---|---|
| `update_camera` | 🔴 **editar câmera falhava sempre para não-admin** — user-facing, nunca reportado |
| `build_rtsp_url` | idem |
| `build_stream_url` | idem |

O Vitor relatou *"não consigo remover câmeras"*. **Editar provavelmente também falhava**, e foi
atribuído a outra coisa.

**Regra:** quando o bug nasce de **nome de parâmetro que mente** (aqui, `user_id` recebendo `tenant_id`),
o defeito é copiável por leitura — grepe o **padrão inteiro** antes de declarar consertado, não só o
método que apareceu no relato. Os quatro agora respondem **404** em cross-tenant (C-01).

---

### D-159 · Desenho da amostra: dois turnos medidos, vale de troca preservado

**Status:** ✅ desenho aprovado — ⛔ mineração NÃO executada

Densidade normalizada por dias cobertos (canais 1–8, `source='nvr'`):

| Faixa | frames/dia-hora | Amostragem |
|---|---|---|
| **05h–16h** | 102–252 | ✅ **cheia** — turno principal |
| **20h–23h** | 84–98 | ✅ **cheia** — segundo turno, não sabido antes da medição |
| **17h–19h** | 22–34 | ⚠️ **leve, jamais zero** — é a troca de turno, quando se coloca e tira EPI: pouca gente, muita **transição de estado**, que é o que o classificador precisa distinguir |
| **01h–03h** | **0** | ⛔ fora — planta vazia |

⚠️ **Ressalva metodológica que fica no registro:** os frames são todos `source='nvr'`, extraídos em
janelas escolhidas manualmente. O eixo bruto media **"quando foi minerado"**, não "quando tem gente";
a normalização por dias cobertos aproxima densidade, mas segue **proxy, não censo**.

⛔ **Taxa de anotação NÃO é sinal de presença** — as 18h têm 24,2% de anotação com a menor densidade,
e isso reflete o que o Vitor **escolheu** anotar.

**Meta ~250/canal é ALVO, não cota:** canal que não chega com gente presente tem o **teto reportado**;
⛔ nunca completar com corredor vazio (frame sem pessoa não vira recorte e só engorda a fila).

**Consequência que sobe de prioridade:** havendo segundo turno das 20h às 23h, **há gente para detectar
no escuro**. Se a câmera não entrega recorte aproveitável em IR, isso é **buraco operacional do produto**,
não do dataset. Medir rejeição por faixa de hora; ⛔ **não baixar o limiar de nitidez de 150** para
forçar rendimento.

---

### D-160 · Padrão de requisição ao DVR: clipe por segmento, não frame a frame

**Status:** ✅ vigente — medido no código antes de qualquer lote

`replay_miner.py:336-395`: puxa **um clipe** (MP4 fragmentado, `ffmpeg -c copy`) e decodifica para JPEG
**em memória**, num segundo estágio. **Não é uma requisição por frame** — 5.000 requisições contra o DVR
seria risco de lockout; extração local não é.

O disjuntor anti-lockout **já existe**: falha de autenticação detectada no stderr do ffmpeg abre
`circuit_open` e **encerra a run inteira, sem retry** (`replay_miner.py:25`). ⛔ Nada a construir aqui.

---

### D-161 · O 401 do DEV não é senha: a conta de `ADMIN_EMAIL` está INATIVA e no tenant errado

**Status:** ✅ vigente · **exige ação do Vitor** · ⛔ nenhuma credencial lida, gerada ou adivinhada

Determinado **sem credencial**, só consultando o banco do DEV:

| Campo da conta de `ADMIN_EMAIL` | Valor |
|---|---|
| Existe | ✅ sim |
| `is_active` | ⛔ **false** |
| `role` | `admin` |
| `tenant` | 🔴 **`default`** — não `rvb` |
| Tem hash de senha | sim |

🔴 **Redefinir a senha não resolveria.** A conta está inativa; e mesmo ativada, está no tenant `default`
e não enxergaria os dados do RVB sem impersonação.

**Mapa das contas (sem e-mails), para escolher a certa:**

| tenant | role | ativa | qtd | é e2e |
|---|---|---|---|---|
| **`rvb`** | **admin** | ✅ **sim** | **1** | ⛔ **não** |
| `rvb` | admin | não | 1 | sim |
| `dev` | superadmin | sim | 3 | 1 é e2e |
| `admin` | superadmin | sim | 2 | não |
| `default` | admin | **não** | 1 | não |

✅ **Existe exatamente um admin ATIVO no tenant `rvb` que não é a conta e2e.** É essa que a variável
deveria apontar.

⛔ **A conta e2e NÃO foi usada** — nem para destravar. Ela está na fila para ser rebaixada de superadmin,
e usá-la agora entrincheiraria o problema que se quer remover. A do `rvb` está inativa de todo modo.

**Ação do Vitor:** apontar `ADMIN_EMAIL`/`ADMIN_PASSWORD` do serviço para o admin ativo do `rvb`
(ou ativar a conta de `default` **e** movê-la de tenant — pior caminho, porque cria um admin em
`default` que não deveria existir).

---

### D-162 · Adendo ao D-156: foram DUAS falhas independentes, não uma

**Status:** ✅ vigente · **adendo, não substituição**

O D-156 registra que a orientação `git archive` → `railway up` estava errada. **Registrar só isso
previne metade da repetição.** As duas falhas:

| Falha | De quem | Como não repetir |
|---|---|---|
| Orientar `railway up` quando o auto-deploy por git já cobria o commit | do briefing | **D-156** — commit na branch → deixa o git deployar |
| **Executar sem checar o metadado que já estava na mão** | **minha** | O deploy de 00:03 trazia `commitHash b769ede5` e eu **li esse metadado** antes de subir por cima. Instrução recebida ⛔ não dispensa conferir o estado que ela pressupõe |

⚠️ **Registro que joga a culpa toda num lado não previne a repetição do outro.** A instrução era
corrigível por leitura — e a leitura estava feita.

---

### D-163 · TREINO 2: a comparação NÃO é simétrica — registrado ANTES do resultado

**Status:** ✅ vigente · **escrito com o pod `qthetvneczh6qa` ainda rodando, resultado desconhecido**

No split de teste (as mesmas 179 imagens dos dois treinos), `mascara` foi de **106 para 54 instâncias**.
Não é só o modelo que muda: **o gabarito ficou mais severo.**

| Situação | TREINO 1 | TREINO 2 |
|---|---|---|
| Modelo prevê "máscara" sobre foto de óculos | ✅ contava **ACERTO** (gabarito dizia `mascara`) | 🔴 conta **ERRO** (gabarito diz `Óculos`) |

**O TREINO 2 é avaliado contra um alvo mais difícil.** Leitura fixada de antemão:

| Se a precisão de `mascara` | Veredito |
|---|---|
| **subir** | ✅ evidência **forte** — subiu apesar de o gabarito ter endurecido |
| **cair** | ⚠️ **ambíguo** — ⛔ não concluir "era volume"; pode ser só o gabarito mais severo |

### Limiar de significância, também fixado antes

TREINO 1: `tp 14 + fp 18` = **n=32 predições**, precisão 0,4375 → IC95% ≈ **[0,27 – 0,61]**.

| Precisão do TREINO 2 | Veredito |
|---|---|
| **> 0,61** | ✅ fora do intervalo — **sinal real** |
| **0,50 – 0,61** | ⚠️ sugestivo, **dentro do ruído** — ⛔ não declarar vitória |
| **< 0,50** | ⛔ sem suporte para a hipótese do rótulo |

⚠️ **O `n` de predições do TREINO 2 também será reportado** — se cair muito, o intervalo alarga e o
limiar sobe. **"Ficou dentro do ruído" é resposta válida e esperada.**

---

### D-164 · `base_model` virando NULL é regressão de LINHAGEM, não metadado cosmético

**Status:** ✅ vigente

`POST /api/training/jobs` não aceita `base_model`: mandei `"base"`, o job `4c782cdf` gravou `null`.
No TREINO 1 (`10feb67b`) ficava `base`.

🔴 **O gate de licença depende de saber qual variante rodou.** RF-DETR **base** é Apache 2.0; **XL** e
**2XL** são PML (ADR-0044, `license_gate.assert_rfdetr_variant_allowed`). Linhagem `null` **não prova
nada numa auditoria** — e o gate deixa passar justamente porque variante ausente cai no default
`RFDETRBase()`, que é permitido. Funciona; não é auditável.

**Consertado:** o handler passa a aceitar e persistir `base_model`, com default explícito `"base"`.
O job `4c782cdf` foi preenchido retroativamente, porque se sabe qual variante rodou.

---

### D-165 · Split por grupo com poucos grupos não respeita proporção — e ninguém era avisado

**Status:** ✅ vigente

**17 grupos câmera+dia para 413 frames**, o maior com 91. O mesmo `{train:0.7, val:0.2, test:0.1}`
produziu **210/6/179** (53/1,5/45) no `v3-treino1` e **354/51/8** (86/12/2) no `v4`. **Nas duas vezes
seguiu calado.**

⛔ **O split por grupo NÃO muda** — é ele que impede vazamento de câmera+dia e é uma das coisas em que
batemos o benchmark (D-128). O que faltava era **o aviso**.

**PROPOSTO — ⛔ SEM CÓDIGO NESTA RODADA:** `_split_by_group` deve registrar aviso alto quando qualquer
split fica abaixo de um mínimo utilizável ou muito fora da proporção pedida. É "nunca degradar em
silêncio" aplicado ao split. ⚠️ **A redação anterior dizia "Consertado" e estava ERRADA** — a decisão
foi escrita, o código não. Corrigido aqui para não mentir no próprio registro.

**Causa que se resolve sozinha:** poucos grupos ⇒ proporção instável. Entra mais câmera e mais dia —
exatamente o que a mineração estratificada vai fazer — e o problema encolhe.

---

### D-166 · O bootstrap de admin e a migration 046 se desfazem a cada deploy

**Status:** ✅ vigente

`railway_start.py:90-106` cria um admin **a cada boot**, com `INSERT INTO users` **sem `tenant_id`**.
A migration `046_deactivate_default_tenant.sql` (ADR-0017) **desativa** os usuários do tenant `default`,
chamando-os de *"artefato de bootstrap sem dono ativo"*. **Os dois rodam a cada deploy, um desfazendo o
outro** — foi isso que deixou `ADMIN_EMAIL` apontando para conta inativa em tenant errado (D-161).

**PROPOSTO — ⛔ SEM CÓDIGO NESTA RODADA:** o bootstrap deve rodar só se **não existir nenhum tenant** —
isto é, só na instalação virgem, que é o caso para o qual foi escrito. ⚠️ **A redação anterior dizia
"Consertado" e estava ERRADA.** Corrigido aqui.

**Verificado:** tenant `default` tem 0 câmeras, 0 frames, 0 anotações e 2 usuários inativos.
⛔ Nenhum dado do RVB vazou para lá. ⛔ Nada removido.

---

### D-167 · TREINO 2 · Camada 1 — o teste pré-registrado NÃO decide

**Status:** ✅ vigente · **Data:** 2026-08-18

O D-163 fixou a régua **antes** do disparo: baseline `mascara` = **0,4375** (tp 14 / fp 18 / fn 92,
n=32, IC95% [0,28–0,61]); **>0,61 = era RÓTULO** · **0,50–0,61 = dentro do ruído** · **<0,50 = sem
suporte**.

Medido: **0,5000** (tp 13 / fp 13 / fn 41, n=26, IC95% [0,32–0,68]).

> **0,5000 cai na faixa "dentro do ruído". O teste pré-registrado NÃO DECIDE.**

⚠️ **A régua não se rebatiza depois do resultado.** Este registro existe para que a Camada 2 —
exploratória e favorável — nunca seja lida como se tivesse passado por este teste.

---

### D-168 · TREINO 2 · Camada 2 — era RÓTULO, com mecanismo medido (exploratória)

**Status:** ✅ vigente · **Data:** 2026-08-18 · ⚠️ **PÓS-HOC — não pré-registrada**

A varredura de limiar foi decidida **depois** de ver o resultado. Registrada como exploratória. O que
a distingue de análise pós-hoc comum: o **mecanismo está medido de ponta a ponta**, não inferido.

**1. As caixas migraram, e dá para contar:** o `test` do export v3 tinha **106 `mascara`**; o do v6
tem **54 `mascara` + 52 `Óculos`**. **Exatamente 52.** Mesmas 179 imagens nos dois (conferido:
conjunto de nomes idêntico).

**2. A confusão aparece e some:** matriz do TREINO 1 tem `Óculos → mascara`; a do TREINO 2, não.
O TREINO 1 aprendeu *"mascara = máscara OU óculos"*.

**3. Vence em 8 de 9 limiares** (mesmo gabarito, mesmo instrumento):

| thr | T1 | T2 | Δ |
|---|---|---|---|
| 0,70 | 0,4167 | 0,6250 | **+0,21** |
| 0,60 | 0,4762 | 0,6000 | **+0,12** |
| 0,55 | 0,4815 | 0,5000 | +0,02 |
| 0,50 | 0,4545 | 0,4483 | −0,01 |
| 0,40 | 0,2903 | 0,4211 | **+0,13** |
| 0,30 | 0,1939 | 0,3800 | **+0,19** |

Em **thr 0,30 os IC quase não se tocam** (T1 [0,13–0,28] × T2 [0,26–0,52]) com **`tp` idêntico (19)**.

**4. A assimetria do gabarito foi DISSOLVIDA por medição, não declarada.** O D-163 previa que o
gabarito endurecido tornaria a comparação ambígua e mandava não concluir "era volume" se caísse.
Rodar **os dois modelos no mesmo instrumento contra o mesmo gabarito** elimina o problema em vez de
o contornar: 0,4815 × 0,5000.

> 🔴 **O efeito do rótulo limpo NÃO é acertar mais — é errar 2,5–3,1× menos.**
> thr 0,30: fp 79 → 31 com `tp` idêntico · thr 0,10: fp 445 → 142.

---

### D-169 · TREINO 2 · Camada 3 — VOLUME é o teto, e isso reordena a prioridade

**Status:** ✅ vigente · **Data:** 2026-08-18

Nas 6 classes que os dois modelos conhecem, `test` de 179 imagens, thr 0,55:

| | tp | fn | recall |
|---|---|---|---|
| TREINO 1 | 17 | 204 | **7,7%** |
| TREINO 2 | 17 | 204 | **7,7%** |

`Botas` (34 instâncias) e `Uso incorreto de mascara` (16): **zero predições dos dois modelos**.

> 🔴 **A pergunta "rótulo ou volume" tem resposta COMPOSTA, com as duas metades provadas no MESMO
> experimento: o rótulo CORROMPIA (D-168) — e o volume LIMITA (aqui).**
> **12 épocas sobre ~400 imagens não produz detector.** A paridade em 12 foi correta para o controle,
> e é exatamente por isso que o controle não pode responder "volume".

**Decisão de prioridade:** o conserto do rótulo **já está entregue** — toda anotação nova nasce
certa. **A prioridade do projeto passa a ser DADO:** mineração estratificada + anotação sobre export
limpo. Treinar de novo antes de multiplicar o volume repete o mesmo teto. Ver issue #423 e o gate
proposto em #427 (D-166).

---

### D-170 · Instrumento novo se calibra contra valor conhecido ANTES da medida que decide

**Status:** ✅ vigente · **Data:** 2026-08-18

O baseline 0,4375 veio de um harness offline **nunca commitado** — `per_class_eval_split` não existia
em lugar nenhum do repositório. Para comparar o TREINO 2 foi preciso **reconstruir o instrumento**.

Um instrumento reconstruído não vale nada até reproduzir um valor conhecido. Este reproduziu
`tp=14` e `fn=92` **exatos** do baseline em `thr=0.55`, com casamento guloso **cego à classe** — e
foi assim que a regra de casamento original ficou conhecida: nenhum limiar sobre casamento *dentro*
da classe podia dar `fp` maior **e** `tp` menor ao mesmo tempo, o que denunciou a regra cega.

⚠️ **A divergência que sobra está registrada, não escondida:** `fp` 13 contra 18. Um harness que
omite o que não fecha não é instrumento.

Versionado em `training/eval/per_class_eval.py` com 7 testes (PR #430, fecha #418).

---

### D-171 · Cheiro não é prova — nem o meu, nem o seu (2ª aplicação)

**Status:** ✅ vigente · **Data:** 2026-08-18

Ficou registrado por dias que *"a API de billing do RunPod responde HTTP 400 — custo indeterminado"*.
Respondia **401**. A causa era minha: o arquivo de credencial guarda `RUNPOD_API_KEY=rpa_...` inteiro
e o consumo mandava a linha toda no bearer — **o nome da variável viajava colado no token**.

Com o token correto o GraphQL responde na hora: `clientBalance = 28,73`, `currentSpendPerHr = 0`.

**A conclusão de fundo sobrevive** — `/v1/billing/summary` realmente não existe na especificação REST,
não há custo por job. **Mas a evidência que eu dei para ela estava errada**, e por dias o sensor de
custo que existia foi tratado como inexistente. Issue #422.
### D-172 · Retenção do DVR da RVB = 4 dias (medida) · a gravação de 31/07 está PERDIDA

**Status:** ✅ vigente · **Data:** 2026-08-18 · **Impacto:** P1-ALTO (operacional, irreversível)

Medido no gravador (Intelbras `iNVD 3032`, série `DQN0009707690`) via CGI `mediaFileFind` — leitura
pura, poucas requisições, credencial que o agente já usa. **O DVR trava por força bruta; medir não
pode virar ataque.**

| medida | resultado |
|---|---|
| mais antigo, janela de 120 dias, canal 1 | **2026-08-14 06:55** |
| canais 4, 6, 8, 12, 20, 27 | **14/08 — todos dentro de 23 min** |
| janela 25/07 → 05/08 | `Error / Bad Request` — **vazia** |
| controle 10/08 → 16/08 | `OK`, primeiro 14/08 06:56 |
| disco, 4 partições | `UsedBytes == TotalBytes` — **100% cheias, ~3,9 TB** |

**O alinhamento entre canais levantou suspeita de wipe; a leitura do disco a descartou.** Disco 100%
cheio é FIFO sobre pool compartilhado: a frente de sobrescrita anda em **ordem de tempo**, não por
canal, e por isso todos os canais perdem o mesmo instante. ~1 TB/dia para ~28 câmeras.

> 🔴 **A gravação de 31/07 está perdida. Irrecuperável. Não há o que minerar dela.**

**Consequências:**
- todo plano de mineração cabe em **4 dias**, não 8 — o default `days=8` era otimista por 2×
- o modo de falha era o pior: metade do plano caía num vazio **sem erro**, só rendimento menor
- mineração tem de ser **contínua**, não campanha mensal: a janela se renova inteira a cada 4 dias
- ⛔ não se conserta com flag — é capacidade de disco

⚠️ **Re-medir quando mudar número de câmeras, bitrate ou disco.** Retenção é consequência das três.

---

### D-173 · Limiar de nitidez 150 fica — MEDIDO por faixa de hora, não ajustado

**Status:** ✅ vigente · **Data:** 2026-08-18

O limiar foi calibrado (D-anterior) sobre n=224 recortes **sem estratificar por hora**. O risco não
medido: um limiar que rejeita quase tudo à noite faz o plano noturno render zero **em silêncio**.

Medido com a **função de produção** (`replay_miner.blur_variance`, Laplaciano 3×3 em PIL puro) sobre
**834 recortes** do acervo, amostrados até 40 por hora, limiar **intocado**:

| faixa do plano | n | mediana | rejeitados @150 |
|---|---|---|---|
| 05–16 (cheia) | 480 | 683 | **3,8%** |
| 17–19 (leve) | 120 | 477 | **9,2%** |
| 20–23 (cheia) | 160 | 708 | **6,9%** |
| 00–04 (fora) | 74 | 627 | 4,1% |
| **total** | **834** | — | **5,2%** |

> ✅ **Nenhuma faixa colapsa. O medo de "à noite rejeita tudo" está DESCARTADO** — 20–23h rejeita 6,9%,
> praticamente o mesmo que o dia.

Pior hora: **17h e 21h, 15%** (6 de 40 — amostra pequena, não é sinal forte). O **crepúsculo (17–19h)
é a faixa mais difícil**: menor mediana (477) e maior rejeição — coerente com luz de transição, e
mais uma razão para ela ser "leve mas nunca zero" no plano.

**Decisão: `_DEFAULT_BLUR_VARIANCE_MIN = 150.0` fica como está.** A medição confirmou a calibração
anterior (mediana 683 aqui × 693 lá) com amostra 3,7× maior e agora estratificada.

⚠️ **Limite honesto da medida:** foi feita sobre o acervo do **coletor ao vivo**, não sobre recorte
de **replay** do DVR, que passa por substream e pode ter qualidade diferente. Re-medir na primeira
mineração real.

---

### D-174 · Item com prazo não vive em lista de pendências humanas · RSK materializado

**Status:** ✅ vigente · **Data:** 2026-08-18

> 🔴 **RISCO MATERIALIZADO:** a gravação de **31/07** foi perdida. Retenção do DVR = 4 dias (D-172);
> o mais antigo no gravador é 14/08; a janela 25/07–05/08 volta vazia.

**O que sobrevive e o que morreu:**

| | |
|---|---|
| ✅ sobrevive | os frames e recortes **já minerados** de 31/07 — estão no R2 e no banco, anotados ou anotáveis. **O dia não sumiu do dataset.** |
| ⛔ morreu | o **direito de voltar ao vídeo bruto** — minerar mais frames, outros instantes, outros ângulos daquele dia |

**A lição não é culpa, é mecanismo.** O item viveu em "pendências do Vitor" por dez prompts. Lista de
pendências humanas recorrente não tem relógio: cada prompt a rola para frente sem custo aparente,
até o prazo vencer em silêncio.

> 🔴 **REGRA: item com PRAZO REAL não pode viver em lista de pendências. Prazo exige ação agendada
> com dono executor — ou vira este parágrafo.**

A aplicação imediata da própria regra: a mineração deixou de ser "campanha a rodar" e virou **timer
no Orin** (D-175). Ninguém precisa lembrar.

---

### D-175 · Mineração é SERVIÇO com cadência, não campanha

**Status:** ✅ vigente · **Data:** 2026-08-18

A janela do DVR **se renova inteira a cada 4 dias** (D-172). Campanha mensal mineraria 4 dias e
encontraria vazio nos outros 26. O desenho:

| | |
|---|---|
| **Cadência** | **2 dias** — metade da janela. Margem para uma falha e um retry **sem perder nada**. |
| **Onde roda** | **Orin, systemd --user timer** (`edge-replay-miner.timer`). ⛔ Não pelo beat da nuvem: mineração fala com o DVR na LAN, e o beat nunca foi provisionado. |
| **Horário** | 03:30 — madrugada, faixa que o plano **não** minera, então não disputa o DVR com turno nenhum. |
| **Janela** | 3 dias por ciclo (margem dentro da retenção de 4). Pedir além da retenção **avisa** em vez de voltar vazio calado. |

**Estratificação** (`SHIFTS_RVB`, ladrilha 05:00→24:00 sem buraco):

| faixa | intervalo | janelas/dia/canal |
|---|---|---|
| **dia** 05–17h | 20 min (cheio) | 36 |
| **crepúsculo** 17–20h | 60 min (**leve, nunca zero**) | 3 |
| **noite** 20–24h | 20 min (cheio) | 12 |
| **madrugada** 00–05h | — | **fora** |

**O crepúsculo é leve, não ausente — e isso é medição, não gosto.** É a faixa com a menor mediana de
nitidez (477 contra ~700) e a maior rejeição por blur (9,2% contra 3,8%), D-173. Luz de transição é
difícil, e é **por isso** que o modelo precisa vê-la. ⚠️ **"Leve" e "ausente" são coisas diferentes**
— há teste fixando a distinção, porque a faixa difícil é sempre a mais tentadora de cortar.

**Regras mantidas:** 250 é **alvo**, não cota · dedup contra o pool inteiro · `excluida` reversível ·
retomável (estado em disco) · anti-lockout (sequencial, pacing, circuito abre em 401/403, zero
varredura de porta) · reserva de disco intocável.

⚠️ **Cada ciclo LOGA início e fim.** Coleta silenciosa que falha é o `days=8` de novo — só que sem
ninguém perceber. O log é a diferença entre serviço e superstição.
