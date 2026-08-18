# D-127 · Modelo `8e8fedf7`: avaliação bloqueada; ordenador (não rotulador) desenhado + descope do bloco 3

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

> ⚠️ Renumerado **D-119→D-127** na consolidação dos PRs #385/#386/#388 (D-119 já em uso na develop).

**17/08 · Claude · 📄 análise**

**Bloqueado.** Avaliar o modelo contra os 377 frames de verdade exige R2 (ONNX 108 MB + frames) e DEV DB
(anotações) — sem credencial de nenhum. Nada baixado; a linha `trained_models 8e8fedf7` nem foi confirmada (sem DB).
#387 é o verificador R2 que destrava. **Desenho registrado** (doc §3): batch inference → `model_order_score`
nullable → fila existente `order_by=model_score`; ⛔ jamais rótulo/proposta (lição SAM+DINO 1005/100%-rejeitadas);
medir ganho (rolagem p/ achar 50 anotáveis, aleatório vs modelo) e **desligar se < ~1,5×**. Bloco 3 (laço de revisão)
**descopado** (prioridade era DEV testável) — quando vier, estender `curation_status`, ⛔ sem tela nova.
**DEV está no ar** (API+DB+Redis+frontend 200), menos a aba Classificar (D-117).

**Veredito: ⏸️ avaliar quando R2+DB provisionados (condição, não data).**
