# EVALS — Eval-Driven Development no Recognition

**Versão:** 1.0
**Data:** 2026-06-02

## O que é EDD aqui

> Define sucesso → encoda em eval → mede continuamente → falha dirige a mudança.

Um eval não é um teste qualquer. É uma **fonte de verdade automatizada** que decide se o sistema
está correto. Cada eval tem:

| Campo | Descrição |
|-------|-----------|
| `nome` | Identificador único (ex: `migrations-harness`) |
| `o que mede` | Invariante verificado |
| `fonte de verdade` | De onde vem o estado correto |
| `onde roda` | Local / CI / ambos |
| `critério pass/fail` | Exit code / assert / threshold |
| `princípio protegido` | Qual C-XX da constitution este eval defende |

---

## Tipo 1 — Evals de sistema/agente (implementados e planejados)

Validam que o sistema (banco, API, infra) está no estado correto.
Rodam no CI, bloqueiam merge se vermelhos.

### `migrations-harness` *(implementado — Fase D1)*

| Campo | Valor |
|-------|-------|
| Nome | `migrations-harness` |
| O que mede | Invariantes de schema Fase 1 + idempotência de todas as 54 migrations |
| Fonte de verdade | `infra/migrations/*.sql` aplicadas em Postgres 15 efêmero |
| Onde roda | Docker local (`run.sh`) + CI job `migrations-harness` |
| Pass | Runner 2× exit 0 + 8 asserts de schema verdes |
| Fail | Runner exit ≠ 0 na 2ª passada OU qualquer assert de schema falha |
| Princípios | C-02 (idempotência), C-04 (schema real), C-08 (eval antes de merge) |

Localização: `tests/harness/migrations/`.
Um comando: `bash tests/harness/migrations/run.sh`.

---

### Evals já existentes (retroativamente classificados)

| Eval | O que mede | Onde roda | Princípio |
|------|-----------|-----------|-----------|
| `ruff` | Zero violações de estilo/lint Python | CI job `ruff` | C-07 |
| `pytest` | Cobertura ≥ 30 % + testes unitários verdes | CI job `pytest` | C-07 |
| `tsc --noEmit` | TypeScript sem erros de tipo | CI job `tsc` | C-07 |
| `gitleaks` | Zero secrets expostos no histórico git | CI `security-scan.yml` | C-05 |

---

### `synthetic-rtsp` *(planejado — Fase D2)*

Cenário end-to-end sintético: MediaMTX servindo vídeo loop como câmera RTSP fake →
pipeline de inferência → alerta gravado no DB.
Cenários planejados: enrollment → evento no cloud (baseline), multi-tenant isolation (403 cross-tenant).

---

## Tipo 2 — Evals de modelo (planejado — Fase 5/treino)

Validam que o modelo YOLO está correto **antes de ir para produção**.

> **Status: PLANEJADO. Não implementar agora.**

### Esqueleto

| Campo | Valor |
|-------|-------|
| Nome | `model-eval-epi` |
| O que mede | Precisão e recall por classe de EPI: capacete, colete, luva, óculos |
| Fonte de verdade | Dataset de validação versionado (Roboflow, branch fixo) |
| Onde roda | Pipeline de treino (Google Colab / CI de treino) após cada epoch final |
| Pass | mAP50 ≥ threshold por classe (a definir por sprint de treino) |
| Fail | Qualquer classe abaixo do threshold → rollback do modelo |
| Princípios | C-07 (definição de concluído inclui eval verde antes de ship) |

Amarra com Fase O5/rollout: se o eval de modelo regredir após deploy em edge → rollback automático
do modelo no site afetado.

Classes a cobrir: `helmet`, `no_helmet`, `vest`, `no_vest`, `gloves`, `no_gloves`, `glasses`, `no_glasses`.

---

## Workflow EDD em prática

```
1. Antes de implementar: escrever o eval (o que é sucesso?)
2. Implementar até o eval ficar verde
3. Merge bloqueado se eval vermelho
4. Eval vermelho = sinal de melhoria, não de derrota
```

Nunca pular o eval porque "é só uma coluna" ou "é só uma função" (C-08).
