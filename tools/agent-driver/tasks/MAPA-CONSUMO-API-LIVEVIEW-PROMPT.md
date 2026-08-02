# Prompt (Claude CODE) — Mapa de consumo da API-V3 (live view / segmentos)

```
[SESSÕES PARALELAS — leia antes de tudo]
Pode haver OUTRA sessão do Code rodando em paralelo.
- ⛔ NUNCA rode `git clean` (nem -fd/-fdx) nesta árvore. Há documentos NÃO COMMITADOS aqui.
  Se precisar limpar, LISTE antes (`git clean -nd`) e peça confirmação.
```

> **Modelo: Sonnet 5.** Levantamento, não implementação.

## ⛔ Regra número 1 — ESTA TAREFA NÃO ESCREVE CÓDIGO

Nenhum PR. Nenhum commit em `services/**` ou `apps/**`. Nenhum restart de serviço. Nenhuma mudança de env var.
Nenhum deploy. **Read-only.** A entrega é um documento com números.

Se durante o levantamento você identificar a correção óbvia, **descreva com `file:line` no relatório** — não
implemente. A decisão de qual caminho seguir é do Vitor e depende justamente destes números.

## Contexto (por que estamos medindo)

Com **1 câmera** o consumo de RAM da `api-v3` subiu de forma perceptível. Em breve chegam **~25 câmeras** na RVB.
Antes de decidir entre três caminhos possíveis, precisamos saber **para onde a memória está indo**:

| Opção | O que é | Custo |
|---|---|---|
| **D — não bufferizar** | manter Redis; parar de ler o corpo do upload inteiro em memória | baixo (código) |
| **A — só correções pontuais** | guarda `edge_fed`, intervalo de poll, idempotência | baixo |
| **B — segmento direto no R2** | edge escreve no R2, browser lê do R2, API só assina URL | alto (arquitetura) |

**Hipótese principal a testar:** o pico de RAM é *high-water mark* do CPython por bufferizar corpos grandes de
upload — não vazamento e não volume. Se for isso, **D resolve** e B fica desnecessário agora.

> ⚠️ **Não confirme a hipótese — teste.** Nesta linha de trabalho, duas hipóteses minhas já se provaram erradas
> quando medidas (contenção de RTSP no NVR; watchdog apagando `/tmp/hls`). Traga o número, mesmo que contrarie.

## A. Curva de memória (Railway)

1. RAM da `api-v3` numa janela de **24–48h**. A curva é **platô** (sobe e estabiliza) ou **monotônica** (sobe e nunca
   volta)? Isso separa *high-water mark* de vazamento — é a pergunta mais importante do documento.
2. Houve **restart por OOM** ou restart automático no período? Quantos?
3. Correlacionar os degraus da curva com **janelas de live view ativo** (dá pra cruzar com os logs de
   `POST /segment` / `serve_hls`).
4. Registrar limite de memória do plano e o headroom atual.

> Só leitura de métricas/logs. **Não reinicie, não altere plano, não mexa em env.**

## B. Como o byte é recebido e devolvido (o código)

Este bloco é o que decide a opção D.

1. Handler de **`POST /edge/live-view/{camera}/segment`**: ele lê o corpo **inteiro** em memória
   (`request.data`, `request.get_data()`, `request.files[...].read()`) ou consome em **chunks/stream**?
   Citar `file:line`.
2. **`serve_hls`**: lê o segmento inteiro do Redis para memória antes de responder, ou usa generator/streaming?
   Citar `file:line`.
3. Config do **gunicorn**: worker class, número de workers, `worker_connections`, `max_requests` /
   `max_requests_jitter` (se ausente, registrar — é relevante para high-water mark).
4. Tamanho real do segmento: distribuição (mín/mediana/máx) dos últimos uploads, não o valor nominal.

## C. Redis

1. `INFO memory`: `used_memory_rss`, `maxmemory`, `maxmemory_policy`.
2. Quanto as chaves `epi:edge_hls:*` ocupam hoje. Há **TTL** configurado?
3. Existem **chaves órfãs** acumulando (câmera que parou de transmitir e deixou segmento)?
4. Se `maxmemory` não estiver definido, sinalizar — é risco real com 25 câmeras.

## D. Custo por câmera assistida (a medida que falta)

Com **1 câmera** em live view ativo, medir por ~10 min:

- MB/s entrando (`POST /segment`) e MB/s saindo (`serve_hls`)
- Delta de RSS do processo da API entre "live view desligado" e "live view ligado"
- CPU% atribuível

Depois **extrapolar para 25** e dizer explicitamente: cabe no plano atual ou não?

## E. Processos ffmpeg órfãos

1. Quantos processos `ffmpeg` vivos no container **agora**, e o RSS de cada um.
2. Confirmar (ou refutar) que `/stream/start` ainda dispara ffmpeg para câmera **alimentada pelo edge** — a guarda
   `edge_fed` do PR #250 foi aplicada em `serve_hls`; verificar se `start_stream` ficou de fora. Citar `file:line`.
3. Contar quantas chamadas de `/stream/start` o front dispara por abertura de tela (há indício de **5 em 13s**).

## F. Latência atual do live view (baseline)

Para saber se a discussão de latência é real ou ruído:

1. `#EXT-X-TARGETDURATION` e quantos segmentos o player bufferiza antes de tocar.
2. Latência ponta a ponta **medida**: relógio com segundos visível na frente da câmera × o que aparece na tela.
   Registrar o número em segundos.

Isso define o piso: qualquer alternativa precisa ser comparada **contra este número**, não contra a intuição.

## Entrega

Documento em **`docs/OBSERVABILIDADE_CONSUMO_API.md`** (commit só deste arquivo, em branch própria, sem tocar em
código). Estrutura:

1. **Veredito em 3 linhas** — platô ou vazamento; onde está a memória; qual opção (D / A / B) os números apontam.
2. Os números de cada bloco A–F, com fonte (print de métrica, saída de comando, `file:line`).
3. **O que NÃO foi possível medir** e por quê — lacuna declarada vale mais que estimativa.
4. Correções identificadas, descritas mas **não implementadas**, com `file:line` e esforço estimado.

Sem opinião sem número ao lado. Se um bloco não puder ser medido, diga — não preencha com estimativa.

## Segurança / escopo

- Ambiente: leitura de métricas e logs. **Produção (host `interchange`) — não alterar nada, só ler.**
- Não expor em log/commit: `DATABASE_URL`, JWT, tokens, senhas, chaves R2.
- Se algum log trouxer credencial exposta, **reportar o `file:line`, não colar o valor**.
