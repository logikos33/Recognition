# ESTADO — LOOP DO PROPOSITOR (reentrante)

> 1º ato de toda sessão: `git fetch` + ler este arquivo do `origin/develop`. Ele MANDA sobre o prompt.

## Marcos

| marco | estado |
|---|---|
| **M0** · #502 âncora `id:0` no ar | ✅ `bea3a5c2` |
| **M1** · `v8-propositor` congelado | ✅ `57670afd` — train=1293 val=303 **test=154** (o v7 tinha 26) |
| **M2** · pré-voo | ✅ **PASSOU** — âncora OK, filhas OK, ids contíguos, remap idêntico nos 3 splits, fonte batendo exato |
| **M3** · treino 50 ép | 🔄 **bloqueado por deploy do worker** |
| **M4** · runner → propostas | ⏳ |

## 🔴 Custo acumulado: **US$ 0,00** (teto US$ 12 · por pod US$ 5) — nenhum pod disparado

## M3 — onde está travado

Três disparos, três `pending` eternos. Causa achada e consertada (#503, `45b1acdf`):
**`%s` dentro de COMENTÁRIO SQL também é placeholder** — o psycopg2 interpola na string crua, antes
de qualquer parser. Um comentário meu explicando o conserto do #416 continha `` `metrics = %s` `` e
virou o 11º placeholder para 10 parâmetros → `IndexError` no dispatch, **antes do pod** (US$ 0).

⚠️ **O worker ainda não serve o conserto.** O deploy dele começou **3 segundos** depois do merge do
#503 e pegou o commit anterior. `railway redeploy` **não resolve** — ele REUSA a imagem. É preciso um
**build novo por git** (este commit serve de gatilho).

**Ao retomar:** confirmar que o worker roda o commit com o conserto ANTES de re-disparar. O sintoma
de que não roda: `dispatch_training` estoura `IndexError: tuple index out of range` em
`training.py:378`.

## Jobs criados (todos `pending`, sem pod, US$ 0)
`9194b36b` · `41361259` · `35f7e8e5` — nenhum provisionou GPU.

## M1-A · Congelamento é FOTOGRAFIA, ⛔ não cadeado
A `dataset_version` é snapshot imutável **deste** treino. **A anotação ao vivo NÃO para** — o Vitor
pode estar anotando durante o freeze, zero impacto. Todo veredito dado durante/depois **entra no
banco** e estreia na **próxima** versão (candidato de quinta). ⛔ Nada é perdido.

O runner respeita por desenho: ⛔ não propõe sobre veredito humano, com cheque **na escrita**.

⚠️ Implementação futura que pause a anotação para exportar é **BUG**.

**Baseline M1-A.3:** anotações `humana` antes do freeze = **2.656** (eram 2.157 há poucas horas —
o Vitor anotou ~500 durante a sessão, sem qualquer interferência).

## Fatos herdados
`v7-SEM-ANCORA` etiquetado como inválido (⛔ sem DELETE) · propostas `ai` no banco: **zero** ·
flag DINO+SAM **OFF** · pós-proc corrigido (#470, por FORMA) · split do v8 muito melhor que o v7,
mas ainda com suporte fraco em 3 classes no test → números do harness seguem **ruído declarado**.

## Fila depois da missão
D-165 vira código até quinta (gate do candidato) · PR refill+retry da tela de boxes · quinta:
candidato com gate (régua D-163) · sexta: shadow + pacote main.


---

## 🔴 2026-08-20 15:10Z · TREINO EM VOO — job `5894a860` · pod `4xeyw2j8q1grrn`

**⚠️ HÁ POD VIVO. Primeiro ato da próxima sessão: verificar o job pelo POSTGRES (#507), nunca pela API.**

```sql
select status, current_epoch, gpu_instance_ref, metrics
  from public.training_jobs where id='5894a860-3037-4976-abbc-239bfa3fd882';
```

### Checklist anti-órfão — tudo cumprido
| item | prova |
|---|---|
| payload estrito | `total_epochs=50` · `base_model=base` conferidos ANTES do pod |
| `running_jobs==0` | verificado no gate de merge e no disparo |
| **proveniência** | `worker_commit = f0a889bf…` = **SHA exato do merge do #509**. O deploy saiu 3s depois do merge — o relógio não provaria, a proveniência provou |
| `gpu_instance_ref` | `4xeyw2j8q1grrn`, gravado NO dispatch |
| régua independente | zip que foi ao pod: **train=1293 · valid=303 · test=154**, batendo a fonte contada por paginação PRÓPRIA (⛔ não a função consertada se auto-aprovando) — 89,3 MB |
| **projeção (época 7)** | **115 s/época → 1,59 h** para 50 · **US$ 0,80** · timeout 5 h, teto US$ 5 → **SEGUE** |

### Ritmo — baseline para o candidato de quinta
**115 s/época** com train=1293, val=303, RTX 3090, batch 4, resolução 616.

### Se a próxima sessão encontrar o pod ainda vivo
Deixe terminar (previsão ~16:25Z). ⛔ **NENHUM merge que toque o worker enquanto voa** — deploy mata
o vigia.

### Ao fechar
`actual_usd` gravado (sucesso OU falha) · **morte provada por NOVA consulta** ao RunPod ·
harness carimbado "split degenerado — ruído, ⛔ não citar" · então **M4 (runner)**.

### Custo
~US$ 0,10 (pod anterior) + em curso. Teto da missão US$ 12.
