# Runbook — arquivos de credencial em scripts de operação

**Criado em:** 2026-08-19 · **Motivo:** #422 · **Escopo:** scripts e sessões de operação que falam com
API de terceiro (RunPod, Vast.ai, Cloudflare, Railway) a partir de credencial guardada em arquivo
local.

⚠️ Este runbook existe porque o defeito que ele previne **já custou dias de conclusão errada**, e o
erro é do tipo que ⛔ não se anuncia.

---

## O incidente, para não repetir

Durante a missão do TREINO 2 ficou registrado que *"a API de billing do RunPod responde HTTP 400 —
custo indeterminado"*. Ela ⛔ não respondia 400. Respondia **401**, porque o cabeçalho ia assim:

```
Authorization: Bearer RUNPOD_API_KEY=rpa_xxxxx
```

O arquivo guardava a linha inteira `NOME=valor` e o consumo fazia `cat` direto para dentro do bearer.
**O nome da variável viajava colado no token.**

🔴 O que torna isto grave ⛔ não é o erro — é o disfarce: 401 e 400 viram *"a API não coopera"*, e a
conclusão errada (*"a conta não expõe custo por API"*) ficou registrada como **fato** por dias. Com o
token correto o GraphQL responde na hora (`clientBalance`, `currentSpendPerHr`) — o sensor de custo
que se dizia inexistente estava lá o tempo todo.

---

## A convenção — uma só, e é esta

🔴 **Arquivo de credencial guarda `NOME=valor`, e o consumo SEMPRE passa por parser.**

Não é a única convenção possível — "só o valor, sem o nome" também funcionaria. É a que fica porque:

- é o formato que os arquivos já existentes usam, então ⛔ não exige migrar nada;
- é o formato que `source` entende de graça;
- um arquivo com só o valor ⛔ não diz **de que** é o valor, e é assim que se autentica na conta errada.

### Como consumir

```bash
# ✅ CERTO — source: o shell faz o parsing, e a variável fica com o nome certo
set -a; . ~/.rp; set +a
curl -H "Authorization: Bearer $RUNPOD_API_KEY" ...

# ✅ CERTO — quando não se quer poluir o ambiente
RUNPOD_API_KEY=$(cut -d= -f2- < ~/.rp)

# ⛔ ERRADO — foi exatamente isto
curl -H "Authorization: Bearer $(cat ~/.rp)" ...
```

⚠️ `cut -d= -f2-` com `-f2-` (e ⛔ não `-f2`): token com `=` no meio — base64 costuma ter — seria
truncado silenciosamente por `-f2`. Mesma família de defeito, outro disfarce.

---

## 🔴 O teste de fumaça — obrigatório ANTES de qualquer conclusão sobre a API remota

**Nunca escreva "a API remota não expõe X" sem antes provar que você está autenticado.** Uma chamada
que só diz *quem sou eu* separa "credencial errada" de "recurso inexistente", e são as duas conclusões
que o incidente confundiu.

```bash
# 1. a credencial chegou inteira? (imprime o TAMANHO, ⛔ nunca o valor)
echo "len=${#RUNPOD_API_KEY} prefixo=${RUNPOD_API_KEY:0:4}"

# 2. autentica? Um endpoint de IDENTIDADE, ⛔ não o endpoint que você quer investigar
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Bearer $RUNPOD_API_KEY" "$URL_DE_IDENTIDADE"
```

Leitura do resultado:

| resposta do passo 2 | o que você pode concluir |
|---|---|
| **200** | autenticado. A partir daqui, 404 no endpoint que interessa é sobre o **recurso** |
| **401 / 403** | ⛔ **PARE.** É a credencial. ⛔ Nenhuma conclusão sobre o que a API expõe é válida |
| **400** | quase sempre a credencial malformada — o caso deste runbook |

⚠️ ⛔ **Nunca** imprima o valor da credencial para depurar. Comprimento e prefixo respondem
"chegou inteira?" sem colocar segredo em log — foi segredo em log que gerou o #471 e a rotação
inteira do [ROTACAO_CREDENCIAIS_DEV.md](./ROTACAO_CREDENCIAIS_DEV.md).

---

## Onde isto vale

⛔ **Nenhum script versionado neste repositório lê credencial de arquivo** — verificado em 19/08 com
busca por `cat`/`$(cat` em `scripts/`, `tools/`, `training/` e `deployments/`. Os arquivos de
credencial vivem **fora do repo**, na máquina de quem opera.

Ou seja: esta convenção governa **como se opera**, ⛔ não código que exista aqui hoje. Se um dia um
script versionado precisar de credencial de arquivo, ele nasce com o parser acima — e com o teste de
fumaça antes de qualquer afirmação sobre a API remota.
