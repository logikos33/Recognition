# D-162 · Adendo ao D-156: foram DUAS falhas independentes, não uma

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **adendo, não substituição**

O D-156 registra que a orientação `git archive` → `railway up` estava errada. **Registrar só isso
previne metade da repetição.** As duas falhas:

| Falha | De quem | Como não repetir |
|---|---|---|
| Orientar `railway up` quando o auto-deploy por git já cobria o commit | do briefing | **D-156** — commit na branch → deixa o git deployar |
| **Executar sem checar o metadado que já estava na mão** | **minha** | O deploy de 00:03 trazia `commitHash b769ede5` e eu **li esse metadado** antes de subir por cima. Instrução recebida ⛔ não dispensa conferir o estado que ela pressupõe |

⚠️ **Registro que joga a culpa toda num lado não previne a repetição do outro.** A instrução era
corrigível por leitura — e a leitura estava feita.
