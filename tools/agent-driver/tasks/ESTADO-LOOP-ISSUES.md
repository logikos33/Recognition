# ESTADO — LOOP de ISSUES (3ª pista)

**Sessão 3:** 2026-08-29 (sábado) · **Worktree:** `~/Logikos-mutirao/wt-issues` (clone rápido —
⛔ **não** o checkout em `Documents`, que sofre eviction do iCloud) · **Branches:** `fix/*` de
`origin/develop`.

## Convivência — TRÊS pistas no mesmo repo

| pista | dona de | como marco |
|---|---|---|
| **MIGRAÇÃO** | `apps/frontend` novo (`/novo/*`), `design/`, telas F2–F6 | `faixa:migracao` |
| **MODELO / SEMANA-CLIENTE** | inference · treino · export · box/edge · shadow · calibração | `faixa:modelo` |
| **ESTA (ISSUES)** | backend geral fora das duas · CI/infra · proveniência · docs · dívidas | — |

🔴 **Antes de todo merge que redeploya:** `running_jobs == 0` **e** fila do worker vazia.
A pista modelo pode ter treino/export em voo — **matar trabalho alheio é o pecado capital.**

```bash
curl -s https://api-v3-desenvolvimento.up.railway.app/livez | jq .running_jobs   # 0 → pode
```

⚠️ `null` = "não sei" e **bloqueia** (D-182). ⛔ Não consulte banco à mão para isso — já deu "zero
pods" porque a tabela estava vazia, não porque não havia pod.

🔴 **CONGELAMENTO DE DEMO: terça 18h → quarta pós-onboarding = ZERO merge na develop.**
Hoje é **sábado**, fora da janela. Na janela: acumular PRs verdes, ⛔ não mergear.

## TRIAGEM TOTAL — 61 issues abertas em 2026-08-29

### Minha faixa (17)

| # | tema | prioridade |
|---|---|---|
| **421** | 🔴 astro 4.16.19 — vulnerável AINDA (ver achado abaixo) | security |
| **545** | 🔴 cross-tenant em `GET /cameras/<id>/alerts` + migration 022 planta alerta falso | security |
| **530** | 403→404 nas 10 rotas irmãs de `/videos` (C-01: não vazar existência) | security |
| **540** | job terminal sem `completed_at` acumula tempo para sempre | bug-que-mente |
| **532** | SocketIO: `alert` e `quality_gate_result` sem emissor — front escuta no vazio | bug-que-mente |
| **534** | `railway up` sobe árvore incompleta — API do DEV não sobe | infra |
| **475** | `workflow_run` executa a definição de `main` | infra |
| **558 559 560 561** | proveniência: produção sem vigia · workflow que se desliga aos 60 dias · build do worker × develop · Frontend sem o dado | proveniência |
| **507 508** | sonda contra endpoint público · buckets de IP atrás da borda | dívida |
| **207 209** | cleanup: claim-code sem consumidor · `versioning.py` v1 superseded | dívida |
| **429** | contradição de 14/08 no TREINO 1 | docs |
| **472** | 🔴 GATE: não existe entrega de alerta a usuário (sem Teams, sem envio) | feature grande |

### `faixa:modelo` (27) — ⛔ não são minhas

`442 445 497 510 511 513 514 515 517 519 520 531 536 537 538 539 541 542 543 544` ·
`131 142 220 423 427 480 481`

### Humano-gated (9) — dono nomeado

| # | espera |
|---|---|
| 495 | **Vitor** — conectar repo no `celery-worker` de production (dashboard) |
| 433 | **Vitor** — decidir `enforce_admins` (ver achado: os checks JÁ existem) |
| 222 | **Vitor** — rotação da senha admin RVB |
| 219 | **Vitor** — promoção develop→staging (gate humano) |
| 223 | **Vitor** — provisionamento no site da RVB |
| 535 | **Paulo** — matriz de exigência por câmera |
| 483 | **Paulo** — condição da regra de luva |
| 224 225 482 | **cliente** — contrato, peça, câmeras a instalar |

### Demo-evento (3) — minha faixa, infra própria

`548` (browsers) · `549` (fonte sem remoto) · `550` (backup dos leads sem credencial)

## 🔴 Achados da própria triagem

**#433 está QUASE resolvida, e o título não vale mais.** A `develop` **tem** proteção hoje:

```
checks obrigatórios: License gate · Migrations harness (D1) · Tests (pytest)
enforce_admins: false     pr_required: false     strict: false
```

O corpo diz *"nenhum check é obrigatório"* — ⛔ falso agora. Resta só a decisão de `enforce_admins`,
que o Vitor já declarou como **saída de emergência explícita**. Vira issue de decisão, ⛔ não de bug.

**#421 NÃO está resolvida, apesar de o `security-scan` estar VERDE.** É o achado que mais importa
desta triagem:

- `apps/landing/package-lock.json` ainda tem **astro 4.16.19** — a versão vulnerável
- o commit `6f895b06` fez o **`npm audit` auditar só o app que o PR toca**; PR que não mexe em
  `apps/landing` ⛔ **não audita a landing**
- e **todos** os jobs de SCA/SAST têm `continue-on-error: true` — bandit, pip-audit, npm audit
  ⛔ nenhum reprova o workflow

⚠️ **O verde não é prova de segurança: é a ausência da pergunta.** Fechar #421 por "CI está verde"
seria exatamente a conclusão falsa que este repositório vem catalogando a semana inteira.

## Registro de convivência (avisos antes/depois)

| quando | o quê | pista afetada |
|---|---|---|
| 29/08 18:44 | triagem publicada; ⛔ nenhum arquivo de outra faixa tocado | — |
