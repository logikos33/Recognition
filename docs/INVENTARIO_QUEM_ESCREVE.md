# Inventário — quem escreve o quê

**Levantado em:** 2026-08-18 · **Método:** leitura de código e de configuração, ⛔ sem acesso ao banco
· **Issue:** #460

## Por que este documento existe

Quatro incidentes desta missão têm **a mesma forma**: dois escritores no mesmo recurso, sem dono
declarado, e o último apaga o outro **sem erro nenhum**.

| recurso | escritores | como apareceu |
|---|---|---|
| `REGISTRO_DE_DECISOES.md` | duas sessões em paralelo | 3 colisões de `D-` em 3 rodadas |
| conta admin | `create_admin()` × migration 046 | `ADMIN_EMAIL` em conta inativa, tenant errado |
| deploy do DEV | CI por git × `railway up` manual | cascata de supersessão |
| `training_jobs.metrics` | repository (funde) × dispatch (sobrescreve) | achado ao escrever este documento |

Foram tratados como quatro incidentes. **São um defeito de desenho:** recurso compartilhado sem dono.

Este inventário é o checklist para a próxima vez que alguém for acrescentar um escritor.

---

## 1. `training_jobs.metrics` — 🔴 sem dono, semânticas divergentes

| escritor | onde | SQL | semântica |
|---|---|---|---|
| callback do pod | `TrainingRepository.update_job_status` | `metrics = COALESCE(metrics,'{}') \|\| %s::jsonb` | **funde** |
| dispatch | `tasks/training.py::update_job` (~182) | `metrics = %s` | **sobrescreve** |
| procedência | `tasks/training.py` (~739, ~750) | `\|\| %s::jsonb` | funde |

O comentário do próprio repository chama `metrics = %s` de *"o 5º 'dois escritores'"* — o padrão foi
reconhecido e corrigido **num** dos sites. O outro ficou. → **#459**

**Dono proposto:** o repository. Todo caminho passa por ele, e a fusão é do BANCO, atômica dentro do
mesmo UPDATE — fazer `SELECT` → merge em Python → `UPDATE` reabriria a corrida, só que maior.

## 2. `training_jobs.started_at` / `current_epoch` — ✅ com dono desde #458

| campo | escritores | regra |
|---|---|---|
| `started_at` | dispatch **e** callback | **primeira escrita vence** (`COALESCE`) — o dono é o dispatch |
| `current_epoch` | só o callback | valor maior que `total_epochs` não é época: ⛔ não grava, ⛔ não trunca |

Antes de #458 o callback sobrescrevia `started_at` e a duração saía errada por **8×**.

## 3. Registro de decisões — ✅ com dono desde #450

Era um arquivo append-only único: toda sessão escrevia na mesma região. **Dono: nenhum, por
construção.** Virou um arquivo por decisão + índice gerado + gate no CI.

⚠️ O gate ⛔ **não** impede duas sessões de escolherem o mesmo número — troca o custo da colisão
(`git mv` em vez de conflito de merge). Está dito assim no `docs/decisions/README.md`.

## 4. Conta admin (`public.users`) — ✅ com dono desde #456

| escritor | quando | o que fazia |
|---|---|---|
| `railway_start.create_admin()` | **todo boot** | `INSERT INTO users` sem `tenant_id` |
| migration `046_deactivate_default_tenant.sql` | todo boot | desativa usuários do tenant `default` |

Rodavam juntos, um desfazendo o outro. **Dono agora:** a migration. O bootstrap só roda em instalação
virgem (nenhum tenant).

## 5. Deploy do DEV — 🟡 dono declarado, sem trava

| escritor | gatilho |
|---|---|
| `.github/workflows/railway-deploy-dev.yml` | push em `develop` (com `concurrency: railway-deploy-dev`) |
| `railway up` de sessão humana/agente | manual |

O `concurrency` do workflow serializa **os deploys do CI entre si**. ⛔ Ele ⛔ não vê um `railway up`
disparado de fora — que é exatamente o que causou a cascata de supersessão. → **#425**

**Dono declarado:** o git. ⛔ `railway up` manual é a exceção que quebra a regra, e não há trava
técnica impedindo — só combinado.

⚠️ **Consequência que esta faixa respeita como lei:** deploy do worker mata o vigia de pod em voo.
Por isso a checagem de pod antes de todo merge.

## 6. Artefatos no R2 — 🟢 particionado por prefixo

Escrevem em R2 (`upload_bytes` / `copy_object`): `versioning_v2`, `training`, `propagation`, `search`,
`inference`, `nvr_extraction`, `quality_recording`, `quality_clips`, `quality_annotation`, e as rotas
`branding`, `storage`, `videos`, `training/images`, `edge`.

São muitos escritores, mas **cada um num prefixo próprio** (`{tenant}/{módulo}/{tipo}/…`), então não
disputam a mesma chave. ⚠️ **Não verificado contra o bucket real** — a afirmação é sobre como as
chaves são montadas no código, não sobre o que está lá.

O caso perigoso é `versioning_v2` copiando frames para `{base_key}/{split}/`: se duas versões de
dataset recebessem o mesmo `base_key`, uma sobrescreveria a outra. O `base_key` carrega a `version`,
que é única por dataset — **por construção**, não por trava.

## 7. Estado do coletor no edge — ⚪ fora desta faixa

`services/edge-sync-agent/app/collector/collector_state.py` mantém estado em disco no Orin. ⛔ Não
inspecionado nesta rodada: a faixa da Missão DADO cobre o minerador/edge. Fica anotado como recurso
que **precisa** de uma linha neste inventário, escrita por quem tem a faixa.

---

## Como usar

Antes de acrescentar um escritor a um recurso desta lista:

1. **O recurso tem dono?** Se não, o problema é esse — não o seu escritor.
2. **Qual é a regra de precedência?** Última escrita vence · primeira vence · funde. Escreva-a no
   código, não no combinado.
3. **A regra é do banco ou da aplicação?** `SELECT` → merge em Python → `UPDATE` reabre a corrida.
4. **Existe trava, ou só combinado?** Combinado já falhou nos quatro casos acima.

## O que este documento ⛔ não afirma

- ⛔ Nada foi verificado contra o banco ou o bucket reais — não havia credencial de DEV na sessão.
  Tudo aqui é leitura de código e configuração.
- ⛔ A lista de escritores de R2 é a dos que chamam as APIs de escrita do storage; ⛔ não cobre
  processos fora deste repositório.
- ⛔ O estado do coletor no edge não foi inspecionado (§7).
