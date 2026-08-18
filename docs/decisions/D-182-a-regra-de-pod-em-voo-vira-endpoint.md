# D-182 · A regra "há pod em voo?" vira endpoint, não pergunta

**Data:** 2026-08-18 · **Status:** ✅ vigente

**O impasse (issue #467).** Merge na `develop` redeploya API e worker, e o deploy do worker **mata o
vigia de um pod em voo**. A regra de convivência mandava checar antes de todo merge — mas checar
significava **perguntar**. Em 18/08 a pergunta ficou **três vezes sem resposta** e 8 PRs verdes
ficaram paradas.

⚠️ **E a alternativa à mão era pior.** Consultar o banco do `.env` local devolveu *"zero pods"* —
porque a tabela estava vazia, não porque não havia pod. **Zero pelo motivo errado.** É o mesmo defeito
do #436 (falha de infra contada como janela vazia), em outro órgão.

**Decisão.** `/livez` passa a devolver `running_jobs`. A regra vira, para qualquer sessão, sem
credencial e sem perguntar a ninguém:

```bash
curl -s <api>/livez | jq .running_jobs      # 0 → pode mergear
```

## Duas restrições que o desenho respeita

🔴 **O `/livez` continua sem tocar o banco.** Ele é o probe que o Railway usa para reiniciar processo
travado — uma consulta ao banco ali vira **loop de restart** na primeira queda de banco, o oposto do
que liveness serve. A contagem vem do **cache do refresher de readiness**, que já roda de fundo; o
handler só faz `peek`. `peek_running_jobs()` existe separado de `get_state()` exatamente porque este
último computa inline quando ainda não houve ciclo.

🔴 **`null` nunca vira `0`.** Sem ciclo do refresher · snapshot mais velho que `STALE_AFTER_SECONDS`
(refresher morto ⇒ número congelado é mentira) · banco fora ⇒ `null`. A regra é `== 0`, então `null`
**bloqueia** — que é o comportamento certo. *"Não sei"* e *"não tem"* são respostas diferentes, e
confundi-las foi exatamente como a checagem falhou.

**Não é dado sensível:** um inteiro, ⛔ sem id, tenant ou nome. O endpoint já é público e já devolve
o commit ([[D-156]]).

**Achado do próprio teste:** `database.ok` só vira `False` depois de `FAILURE_THRESHOLD` falhas
consecutivas — tolerância deliberada a piscada de rede. Então nos primeiros ciclos com o banco fora a
contagem **é** tentada, e devolve `null` por conta própria. O guard é otimização, ⛔ não portão. O
teste foi corrigido para descrever isso em vez de fingir um portão que não existe.

Mesma família de [[D-176]] e [[D-181]]: quando a coordenação depende de combinado, ela falha; o que
resolve é a informação ficar disponível sozinha.
