# D-163 · TREINO 2: a comparação NÃO é simétrica — registrado ANTES do resultado

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **escrito com o pod `qthetvneczh6qa` ainda rodando, resultado desconhecido**

No split de teste (as mesmas 179 imagens dos dois treinos), `mascara` foi de **106 para 54 instâncias**.
Não é só o modelo que muda: **o gabarito ficou mais severo.**

| Situação | TREINO 1 | TREINO 2 |
|---|---|---|
| Modelo prevê "máscara" sobre foto de óculos | ✅ contava **ACERTO** (gabarito dizia `mascara`) | 🔴 conta **ERRO** (gabarito diz `Óculos`) |

**O TREINO 2 é avaliado contra um alvo mais difícil.** Leitura fixada de antemão:

| Se a precisão de `mascara` | Veredito |
|---|---|
| **subir** | ✅ evidência **forte** — subiu apesar de o gabarito ter endurecido |
| **cair** | ⚠️ **ambíguo** — ⛔ não concluir "era volume"; pode ser só o gabarito mais severo |
