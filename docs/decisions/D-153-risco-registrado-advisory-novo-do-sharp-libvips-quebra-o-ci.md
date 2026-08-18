# D-153 · Risco registrado: advisory novo do `sharp`/libvips quebra o CI do landing

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ⚠️ risco aberto — ⛔ NÃO consertado nesta rodada

`SCA (npm audit) (landing)` falha com `sharp <0.35.0` herdando CVE-2026-33327/33328/35590/35591 do
libvips (`GHSA-f88m-g3jw-g9cj`), via `astro`. **Não é pré-existente** — a `Security Scan` da `develop`
passou às 22:29 de 17/08; o advisory saiu depois. **A `develop` vai ficar vermelha no próximo push.**

**Correção conhecida:** `npm audit fix --force` instala `astro@7.2.2` — **breaking change**.

⛔ Não feito aqui de propósito: bump de astro no meio de uma rodada de dados trocaria duas variáveis.
**Condição:** rodada própria, sem experimento em curso.
