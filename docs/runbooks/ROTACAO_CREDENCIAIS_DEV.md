# Runbook — rotação de credenciais do DEV (Redis + Postgres)

**Criado em:** 2026-08-18 · **Executor:** Vitor (dashboard do Railway) · **Motivo:** #471 (senha do
Redis saiu em log a cada boot) + rotação do Postgres do DEV já pendente.

⚠️ **A rotação do Redis é necessária independentemente do "fantasma" do #425.** O segredo esteve em
log — isso não depende de quem deployou o quê. Conserto de código (#474) impede vazamento **novo**;
⛔ não desfaz o que já foi impresso.

---

## Antes de tocar em qualquer coisa — a pergunta que decide o resto

🔴 **As variáveis são REFERÊNCIA ou VALOR LITERAL?**

No dashboard, `Desenvolvimento → API-V3 → Variables`, olhe `REDIS_URL`:

| o que você vê | o que significa | o que a rotação exige |
|---|---|---|
| `${{Redis.REDIS_URL}}` (ou similar) | **referência** ao serviço Redis | Railway propaga sozinho; só reinicia |
| `redis://default:…@…` colado | **literal** | ⛔ **você tem de reeditar em CADA serviço**, senão fica metade rodando com a senha velha |

**Não pule esta checagem.** É a diferença entre uma rotação de 5 minutos e um DEV meio quebrado com
erro de autenticação em serviço aleatório.

---

## Quem consome o quê (levantado via API do Railway, ⛔ sem ler valores)

| serviço | `REDIS_URL` | `SEGMENTS_REDIS_URL` | `DATABASE_URL` |
|---|---|---|---|
| **API-V3** | ✅ | ✅ | ✅ |
| **celery-worker** | ✅ | — | ✅ |
| **Frontend** | ✅ | — | ✅ |

⚠️ **`Frontend` tem `REDIS_URL` e `DATABASE_URL`.** É um Vite estático — ⛔ não deveria precisar de
nenhuma das duas. Provavelmente resíduo. **Não remova durante a rotação** (uma coisa de cada vez), mas
anote: variável a mais é superfície a mais, e ela também precisa ser rotacionada enquanto existir.

---

## Redis — passo a passo

1. **Checar referência × literal** (acima). Decide os passos 3–4.
2. **Dashboard → serviço `Redis` → Variables → `REDISPASSWORD`** (ou *Data → rotate*, conforme o
   plugin oferecer). Gerar nova senha.
3. **Se as variáveis forem referência:** nada a editar. Vá ao passo 5.
4. **Se forem literais:** atualizar `REDIS_URL` em **API-V3, celery-worker, Frontend** e
   `SEGMENTS_REDIS_URL` em **API-V3**. ⚠️ `SEGMENTS_REDIS_URL` é fácil de esquecer — é o Redis dos
   segmentos HLS, isolado do blocklist de JWT ([[D-043]]). Esquecê-lo derruba o live view **sem**
   derrubar a API, e o sintoma não parece de credencial.
5. **Reiniciar, nesta ordem:** `celery-worker` → `API-V3` → `Frontend`.
   *Worker primeiro:* ele é quem reconecta mais devagar e quem estava imprimindo a senha.
6. **Verificar:**
   ```bash
   curl -s https://api-v3-desenvolvimento.up.railway.app/livez    # status alive, running_jobs presente
   curl -s -o /dev/null -w "%{http_code}\n" \
        https://api-v3-desenvolvimento.up.railway.app/readyz      # 200 = Redis e DB de pé
   ```
   ⚠️ `/readyz` é o que prova o Redis: `/livez` responde 200 mesmo com Redis fora.
7. **Confirmar que o log parou de vazar** (⛔ só depois do #474 mergeado): a linha
   `celery_configured: broker=` deve mostrar `***` no lugar da senha.

## O que reinicia, e o que NÃO

| | |
|---|---|
| **Reinicia** | API-V3, celery-worker, Frontend |
| **⛔ Não é afetado** | o **box/Orin** — o Redis dele é local, e o edge fala com a nuvem por HTTPS, ⛔ não por Redis |
| **⛔ Não é afetado** | deploy por git (a integração nativa não usa Redis) |

⚠️ **A afirmação sobre o box é por leitura de arquitetura, ⛔ não medida nesta sessão.** Se houver
qualquer `REDIS_URL` apontando para a nuvem no box, é faixa da Missão DADO confirmar — pergunte antes
de rotacionar, ⛔ não depois.

## Janela

⛔ Não rotacione com job de treino em voo:

```bash
curl -s https://api-v3-desenvolvimento.up.railway.app/livez | jq .running_jobs   # tem de ser 0
```

`null` ⛔ não serve como autorização — `null` é "não sei" ([[D-182]]).

---

## Postgres do DEV — a rotação já pendente

Mesma estrutura, com duas diferenças que importam:

- **Consumidores:** `DATABASE_URL` em API-V3, celery-worker, Frontend. Mais qualquer `.env` local de
  desenvolvedor ou de sessão de agente — ⛔ **esses não se atualizam sozinhos** e vão falhar depois,
  longe da rotação, parecendo outra coisa.
- **Migrations rodam no boot da API.** Depois de reiniciar, confira o log de startup: se a API não
  conseguir conectar, ela ⛔ não sobe, e o `/readyz` reprova. É falha barulhenta — o que é bom.

**Ordem:** rotacionar → atualizar variáveis (se literais) → reiniciar worker → API → Frontend →
`/readyz` 200 → avisar as sessões ativas para refazerem seus `.env`.

---

## Depois: registrar

Uma decisão nova em `docs/decisions/` com a data da rotação e **o que foi encontrado no passo 1**
(referência ou literal). Esse detalhe é o que a próxima rotação vai querer saber primeiro, e é
exatamente o que ninguém anota.
