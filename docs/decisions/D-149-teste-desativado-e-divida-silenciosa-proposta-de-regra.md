# D-149 · Teste desativado é dívida silenciosa — proposta de regra

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente

Os três testes de `delete_camera` foram desativados via `--deselect` em junho
(`tools/agent-driver/config.yaml`), com o bug documentado em
`docs/quality/AUDITORIA_2026-06-21.md:50-52`. **Ficaram dois meses apagados**, e o bug que eles pegavam
era exatamente o que impedia o Vitor de arquivar câmera.

Reativados nesta rodada — os três passam.

**Regra proposta:** todo `--deselect` novo exige entrada `D-` com **condição objetiva de reativação**
(ex.: *"reativar quando X for corrigido"*). Sem isso, `--deselect` é indistinguível de "apagamos o alarme".
Um check de CI que recuse `--deselect` sem `D-` referenciado no mesmo commit custa **P**.
