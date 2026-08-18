# D-171 · Cheiro não é prova — nem o meu, nem o seu (2ª aplicação)

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **Data:** 2026-08-18

Ficou registrado por dias que *"a API de billing do RunPod responde HTTP 400 — custo indeterminado"*.
Respondia **401**. A causa era minha: o arquivo de credencial guarda `RUNPOD_API_KEY=rpa_...` inteiro
e o consumo mandava a linha toda no bearer — **o nome da variável viajava colado no token**.

Com o token correto o GraphQL responde na hora: `clientBalance = 28,73`, `currentSpendPerHr = 0`.

**A conclusão de fundo sobrevive** — `/v1/billing/summary` realmente não existe na especificação REST,
não há custo por job. **Mas a evidência que eu dei para ela estava errada**, e por dias o sensor de
custo que existia foi tratado como inexistente. Issue #422.
