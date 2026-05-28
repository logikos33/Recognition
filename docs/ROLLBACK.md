# ROLLBACK — Pre Rescue Protocol (2026-04-10)

Se o staging explodir após o merge do `rescue/governance-infra`, use um dos comandos abaixo.

---

## Ponto de Segurança

| Campo | Valor |
|-------|-------|
| **Tag** | `backup/pre-rescue-2026-04-10` |
| **Commit hash** | `645fc89df5887518840e0c0b87cf69052655d9bc` |
| **Mensagem** | `feat(gateway): local runner script + fix default port 8001→8080` |
| **Data** | 2026-04-10 |

---

## Opção 1 — Railway Rollback (mais rápido, sem tocar no git)

1. Abrir Railway dashboard
2. Serviço `api-v3` → aba **Deployments**
3. Clicar no deployment anterior → **"Redeploy"**

Pronto. Nenhum comando necessário.

---

## Opção 2 — Reverter via commit (limpo, histórico preservado)

```bash
git checkout staging
git revert HEAD --no-edit
git push origin staging
```

Railway rebuilda com estado anterior. Histórico intacto.

---

## Opção 3 — Reset forçado para o ponto de segurança (nuclear)

```bash
git checkout staging
git reset --hard backup/pre-rescue-2026-04-10
git push origin staging --force
```

⚠️ Reescreve histórico do staging. Usar só se as opções 1 e 2 falharem.

---

## O que foi adicionado no rescue/governance-infra

Se quiser entender o que pode ter quebrado:

- `flask-limiter` — rate limiting em `/api/auth/login` e `/register`
- `X-Request-ID` — header propagado em todas as respostas
- Remoção de `annotations/` e `datasets/` (eram vazios, sem risco)
- Remoção de `services/` (ghost dir, sem risco)
- Docstrings nos arquivos de `core/` e `domain/services/`

**Causa mais provável de falha**: `flask-limiter` não instalado no Railway.
**Fix rápido**: checar se `flask-limiter[redis]>=3.5` está em `requirements/base.txt`.
