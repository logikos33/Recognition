# D-181 · O dispatch não escreve por cima do que o pod reportou

**Data:** 2026-08-18 · **Status:** ✅ vigente

**O defeito (issue #459).** `tasks/training.py::update_job` gravava três campos com os **defaults da
própria assinatura** (`progress=0`, `epoch=0`, `metrics=None`) — e ele roda **depois** de o pod
existir: `update_fn("running", progress=5)` dispara logo após a criação do pod, e
`update_job("failed", metrics=metrics_falha or None)` roda no fim.

| campo | antes | efeito |
|---|---|---|
| `metrics` | `metrics = %s` | **apaga** tudo que o pod reportou (o repository já fundia com `\|\|`) |
| `progress` | `progress = %s` | um `failed` sem progress **zera** 90% de treino feito |
| `current_epoch` | `current_epoch = %s` | o `0` default **apaga** a época real |

⚠️ O comentário do próprio repository chama `metrics = %s` de *"o 5º 'dois escritores'"*. O padrão foi
reconhecido e corrigido **num** dos sites; o outro ficou. É o [[D-176]] de novo, em outro recurso:
**recurso compartilhado sem dono declarado**.

**Decisão.** O escritor que chega com valor default ⛔ não sobrepõe o escritor que chega com medida:

| campo | agora |
|---|---|
| `metrics` | `COALESCE(metrics,'{}'::jsonb) \|\| %s::jsonb` — funde, igual ao repository |
| `progress` | `GREATEST(COALESCE(progress,0), %s)` — progresso ⛔ não anda para trás |
| `current_epoch` | `COALESCE(NULLIF(%s, 0), current_epoch)` — o `0` default nunca apaga |

**A fusão é do BANCO**, atômica no mesmo `UPDATE`. `SELECT` → merge em Python → `UPDATE` reabriria a
corrida, só que maior — é o que o repository já tinha aprendido.

**Efeito colateral necessário:** o `UPDATE` saiu da closure para `_gravar_progresso_do_job()`, no
módulo. Enquanto viveu dentro do dispatch, o defeito ⛔ **não tinha como ser fixado por teste nenhum**.
Extração sem mudança de comportamento além da correção.

Ver [[D-180]] e o inventário `docs/INVENTARIO_QUEM_ESCREVE.md` — é a mesma forma de defeito.
