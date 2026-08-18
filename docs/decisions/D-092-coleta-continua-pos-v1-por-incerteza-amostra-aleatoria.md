# D-092 · Coleta contínua pós-v1: por incerteza + amostra aleatória (desenho, NÃO construído)

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**12/08 · desenho registrado · ⏸ depende do modelo v1 existir**

A intuição do Vitor ("diminuir a captura e deixar o modelo se retreinar com cenários novos")
está certa, com um ajuste: o ganho não vem de coletar menos, vem de coletar MELHOR.

- **Hoje (sem modelo):** coleta ampla por amostragem — não há como saber o que é útil.
- **Depois do v1:** toda detecção vira candidata; guardar e anotar as de **baixa confiança**
  (active learning) — mesmo esforço humano rendendo várias vezes mais. Ciclo:
  `coletar → anotar → treinar → detectar → coletar onde errou → …`
- ⚠️ **Ressalva:** só incerteza concentra o dataset em poucas situações parecidas. **Misturar
  com amostragem aleatória** — câmeras diferentes, horários diferentes.
- O schema já espera por isso: `training_frames.uncertainty_score` e `priority_rank` existem
  desde a migration de active learning (011). O gatilho de construção é o v1 treinado — nada
  a construir antes.
