# D-081 · Inventário R2: acervo RVB 100% íntegro · pesos SAM/DINO NÃO estão no R2

**Seção:** Rodada 10/08 — anotação destravada de ponta a ponta (D-80..D-84) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**10/08 · Claude · ✅ (PR #333, relatório `docs/quality/r2-inventory-2026-08-10.md`)**

7.241 frames no DB no momento da varredura: **7.151 com objeto que baixa (98,8%)**; os 90
faltantes são TODOS do tenant `e2e-fase-a-validation` (upload de 12/07) — **nenhum frame da RVB
está perdido**. GET de prova 30/30. 17 órfãos no R2 (janela upload↔linha da coleta ativa).
O "frame não encontrado" que abriu esta frente era a soma #313 (posse por tenant de casa) +
#322 (erro de R2 mascarado como 404) — ambos já corrigidos e agora provados por inventário.
Bucket inteiro varrido (7.168 objetos): **nenhum peso de modelo** (`.pth`/`.onnx`/sam/dino).
A lembrança de pesos "numa aba do epi-monitor" não corresponde ao bucket; o serviço
`pre-annotation` espera baixá-los por env (`PREANNOT_*_CHECKPOINT`) sob demanda (D-38).
