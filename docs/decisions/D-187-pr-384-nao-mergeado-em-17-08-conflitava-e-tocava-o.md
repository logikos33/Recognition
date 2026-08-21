# D-187 · #384 (aba Classificar + minerador) não mergeado em 17/08 — conflitava e tocava o supercategory

**Data:** 2026-08-17 · **Status:** ↩ substituída — o #384 foi mergeado (ver "Depois")

> **Nota de port.** Corpo verbatim da entrada que os PRs #385/#386 acrescentavam a
> `../REGISTRO_DE_DECISOES.md` — arquivo **congelado**. Lá nascia como `D-117`, número já ocupado na
> `develop`. Portada com número livre; os PRs de origem foram fechados sem merge.

**17/08 · Claude · 📄 análise**

**Medido.** #384 é `CONFLICTING`/`DIRTY` e toca `versioning_v2.py` + `test_coco_supercategory.py` — o arquivo que
o prompt avisa que reverte o #378. Resolver esse conflito autonomamente viola "PARE em conflito" e arrisca a raiz
do CUDA assert. **Bloqueia a aba Classificar no DEV** (ela vive só neste PR). **Passo do Vitor:** rebase do #384
sobre develop preservando `"supercategory": module_code`, resolver `versioning_v2.py`, então merge.

**Veredito: ⛔ não mergear — recomendar rebase.**

## Depois (2026-08-21, no port)

O rebase recomendado aconteceu e **o #384 foi mergeado** — o próprio cabeçalho de
`../REGISTRO_DE_DECISOES.md` cita "renumeradas à força no merge #384" ao explicar por que o registro
monolítico foi congelado. A aba Classificar está na `develop` e recebeu, depois disso, uma série de
correções próprias (fila que reapresentava recorte, paginação por cursor, 410 de cursor órfão).

⚠️ Fica o método, que ⛔ não envelheceu: **"PARE em conflito"** continua sendo a regra, e foi ela que impediu
uma resolução autônoma sobre `versioning_v2.py` num momento em que ela teria reintroduzido o defeito do
supercategory.
