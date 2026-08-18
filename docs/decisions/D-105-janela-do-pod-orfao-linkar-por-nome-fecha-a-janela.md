# D-105 · Janela do pod órfão: linkar por NOME fecha a janela; varredura por nome ALERTA, não mata

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

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
