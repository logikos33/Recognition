# D-104 · Matriz classe × câmera + metas de equilíbrio da base (Volta 1)

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**14/08 · Claude · ✅ construído no DEV (sem disparar treino)**

*(Segue a D-103 — taxonomia de 6 classes, PR #376. D-102 segue não localizado; numeração para o Vitor.)*

**O quê.** Aba **Cobertura** na tela de treinamento + endpoint `GET /api/training/coverage-matrix`
(`coverage_service.py`): matriz **classe × câmera** com **células zeradas visíveis** (a classe que
aquela câmera nunca viu é a informação mais valiosa). Conta **idêntico ao export de treino** —
mesmo universo de `versioning_v2._fetch_annotations` (só `humana`/`auto_aprovada`, sem arquivada, sem
excluída, offset de classe decodificado). **Provado com número:** `scripts/ops/verify_coverage_matches_export.py`
extrai os DOIS SQLs do código-fonte e roda contra o DEV → **556 caixas / 377 imagens dos dois lados**.
Estende `DEV-FILTRO-CLASSES-PROMPT.md` (não duplica: aquela rodada entregou facetas câmera/status; a
matriz 2D + metas + ranking + aviso de órfã é nova).

**Metas (pintadas na matriz).** **≥100 imagens/classe, em ≥5 câmeras, nenhuma câmera com >50% da
classe.** Derivação: 100 img × 20% de validação = **20 positivos de val/classe → resolução de recall
≤5%** (contra passos de 17% a k=6, onde F1 0,07 é indistinguível de 0 — os números da Volta 0). ≥5
câmeras permite **validação com câmera retida** (mede generalização, não decorar ângulo). Teto de 50%
ataca a concentração. **Piso de interpretabilidade** (abaixo = ruído): ≥40 img em ≥4 câmeras.

**Estado medido (DEV, 14/08).** 556 caixas / 377 imagens / **100% humanas**. **7 de 28 câmeras** têm
anotação; **só *Protetor auditivo* bate a meta** (189 img, 6 câm, 48%). *máscara* e *Sem protetor* têm
câmeras suficientes mas passam de 50% numa só (concentração). *Uso incorreto* (22), *Sem máscara* (28) e
*Botas* (30) estão **abaixo do piso**. *hardhat* (1 caixa) é straggler fora do D-103 — **arquivar** (não
some da contagem: aparece marcado, para a soma bater com o export).

**Respostas da Volta 1 (sem disparar).** (1) A validação para de ser arredondamento quando cada classe
atinge **≥100 img em ≥5 câmeras** (X medido acima). (2) *Uso incorreto* e *hardhat* estão abaixo do piso;
*hardhat* deve ser arquivado (D-103). (3) Para quebrar a concentração da **Canal 8**, anotar as classes
concentradas nas câmeras-reservatório com backlog (**RVB Camera 1: 1398 · Canal 7: 1000 · Canal 3: 999**)
— ranking na tela. **Coleta parada:** as 20 câmeras com ~50 frames (Canais 10–29) esgotam antes da meta e
precisam de coleta nova (listadas em "Câmeras para voltar a coletar").

**Avisos que a tela dá (não degrada em silêncio).** 1 **caixa órfã** `class_id=0 "Capacete"` na Canal 8
(o fantasma do capacete removido no D-103) — o export descarta calado, a tela **avisa**. Arquivadas
confirmadas fora: *Protetor auricular* (17), *incluir blur* (1).

**Como aplicar.** Endpoint é read-only, por tenant do JWT (`get_tenant_id`, sem fallback). Célula/lacuna
clicada leva direto à galeria filtrada naquela câmera, não anotadas.
