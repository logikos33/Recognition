# D-118 · Estágio 2 = classificação multilabel por RECORTE (a AWS valida a direção do doc dois-estágios)

**Seção:** Rodada RunPod 10/08 (PR #343 — renumerada de D-85..D-88 → D-106..D-109) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

> ⚠️ Renumerado **D-107→D-118** na consolidação dos PRs #385/#386/#388 (D-107 já em uso na develop).

**16/08 · Claude · 📄 análise (sem código de produto)**

**Medido.** O caminho servido é **single-stage** (`services/inference/inference/detectors.py:169-216`;
`config.py:23` `VIOLATION_CLASSES="no_helmet,no_vest,no_gloves"`) — um forward por frame, sem cascata. O repo AWS é a
implementação de referência de **recorta-pessoa → classifica-o-recorte-inteiro**, confirmando independentemente a
recomendação de `avaliacao-dois-estagios-classificacao-por-recorte.md`.

**Veredito: 🟡 adotar adaptado.** Protótipo/export `{recorte, multilabel}` **pode começar já** (363 recortes já
anotados; masked BCE p/ rótulo parcial). **Servir no edge ⏸️ ADIADO até** — condição, não data — o FPS do Estágio 2
estar medido no Orin mantendo os 28 cams com folga.
