# D-024 · 🛑 O rate limit inviabiliza 8 câmeras — corrigir antes de subir

**Seção:** Câmeras e edge · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude (achado em log) · 🔄**

Medido no DEV em 04/08, 15:06–15:08: `ratelimit 300 per 1 minute (ip:…) exceeded`, com **429 em `.m3u8`,
`.ts` e até no `OPTIONS` de preflight**.

Três causas independentes:

1. **3 sessões simultâneas por câmera** (tokens nascidos com 39 min e 65 s de intervalo, todos vivos),
   baixando o **mesmo** segmento — o PR #285 (teardown) resolve e está aberto sem merge.
2. **A conta não fecha nem limpa:** ~1,5 req/s por câmera ⇒ **8 câmeras ≈ 720 req/min**, contra um teto
   de 300. Não é ajuste fino, é aritmética.
3. **A chave é o IP.** Numa fábrica todos saem pelo mesmo IP público — o limite é dividido pela operação
   inteira e um usuário derruba os outros.

Decidido: isentar `OPTIONS` · bucket separado para o caminho de vídeo · chave por usuário/tenant (com
teto de IP alto) · mergear o #285 primeiro.

⚠️ **Sem isso, o aceite "8 câmeras ao vivo" falha por motivo alheio às câmeras.**
