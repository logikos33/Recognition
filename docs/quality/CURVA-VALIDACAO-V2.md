# Curvas de validação — rodada v2 (três taxonomias)

Prova de que cada treino parou por **convergência**, e não por corte de relógio,
de orçamento ou de qualquer outra coisa. A curva é a prova; curva que desmente
também entra.

Fonte: `jobs/{job_id}/pod.log` no R2 — a linha
`Early stopping: Current mAP (EMA): X, Best: Y` que o RF-DETR imprime uma vez
por época. É o MESMO número que elege o `checkpoint_best_total.pth`, que é o
arquivo que vira o ONNX servido. Métrica: AP@[IoU=0.50:0.95], EMA, no split
`val` da própria variante.

---

## Variante A — v17a-presenca (5 classes de presença)

Job `04508616-7197-4d65-ab9b-44c927a4d64c` · pod `tep7xhdt469zoy` · RTX 4090
SECURE · batch 4 × grad_accum 4 · imgsz 560 · teto 100 épocas · paciência 15.

| ép | mAP EMA | | ép | mAP EMA | | ép | mAP EMA |
|---:|--------:|---|---:|--------:|---|---:|--------:|
| 1 | 0,2912 | | 9 | 0,4333 | | 17 | 0,4063 |
| 2 | 0,3699 | | 10 | 0,4308 | | 18 | 0,4068 |
| 3 | 0,4195 | | 11 | 0,4223 | | 19 | 0,4011 |
| 4 | 0,4345 | | 12 | 0,4227 | | 20 | 0,4004 |
| 5 | 0,4347 | | 13 | 0,4071 | | 21 | 0,4001 |
| 6 | 0,4274 | | 14 | 0,4153 | | 22 | 0,3996 |
| 7 | 0,4352 | | 15 | 0,4102 | | 23 | 0,4011 |
| **8** | **0,4386 ← PICO** | | 16 | 0,4079 | | | |

**Veredito: convergiu, e com folga.** Três coisas sustentam isso:

1. **Subida limpa até a ép.8** (0,2912 → 0,4386) e nenhuma superação depois.
2. **A curva não estagnou — ela CAIU.** Não é o caso ambíguo de "ainda subia
   devagar, dentro do limiar de 0,001": das 15 épocas após o pico, 14 ficaram
   ABAIXO dele, e as últimas cinco (0,4011 · 0,4004 · 0,4001 · 0,3996 · 0,4011)
   estão ~0,038 abaixo. Isso é começo de sobreajuste, não platô.
3. **A parada bate exatamente com a regra:** pico na ép.8 + paciência 15 = ép.23,
   que é onde parou. Não foi timeout (o pod tinha 43.416 s de teto e usou 8.303),
   não foi saldo, não foi o teto de 100 épocas.

### O que a curva revela de quebra (não estava sendo procurado)

**O `lr_drop=15` não entregou o segundo salto que justificava a paciência 15.**
O comentário em `remote_train.train_rfdetr` prevê que a validação dá um segundo
pico logo após a queda de 10× do LR na época 15, e a paciência foi subida de 8
para 15 justamente para não perder esse salto. Nesta corrida ele não veio: ép.15
= 0,4102 e ép.16-23 continuaram descendo.

Consequência em dinheiro, medida: o pico foi na ép.8 e o run foi até a 23. As 15
épocas de prova custaram ~70 min = **US$ 0,87 dos US$ 1,71** do treino — metade
do custo para provar uma ausência. Com paciência 8 teria parado na ép.16, com o
MESMO artefato (o best é o da ép.8 nos dois casos).

**Não é recomendação de mudar a paciência com base numa corrida.** É o primeiro
dado real sobre ela; se B e C repetirem o padrão, aí há três corridas dizendo a
mesma coisa e a decisão fica do dono.

---

## Variante B — v17b-ausencia (presença + ausência como classe)

Job `9cc62fd6` · pod `fyca473ls44yh6` · RTX 4090 SECURE (VRAM 24,0 GiB lida no
pod) · batch 4 × grad_accum 4 · **23 épocas**.

`0,1564 · 0,2281 · 0,2472 · 0,2701 · 0,2765 · 0,2779 · 0,2821 · **0,2861 ←
PICO (ép.8)** · 0,2832 · 0,2783 · 0,2771 · 0,2720 · 0,2702 · 0,2717 · 0,2666 ·
0,2652 · 0,2617 · 0,2621 · 0,2601 · 0,2585 · 0,2559 · 0,2572 · 0,2568`

Convergiu. Pico ép.8, parada ép.23, distância exatamente 15. Das 15 épocas após
o pico, **15 ficaram abaixo dele** — queda ainda mais limpa que a do A.

## Variante C — v17c-partes (parte do corpo + EPI)

Job `11f1303c` · pod `6lqnmefcjbeqet` · RTX 4090 SECURE (24,0 GiB) · batch 4 ×
grad_accum 4 · **20 épocas**.

`0,2187 · 0,3172 · 0,3589 · 0,3835 · **0,3905 ← PICO (ép.5)** · 0,3803 · 0,3803 ·
0,3780 · 0,3735 · 0,3852 · 0,3762 · 0,3776 · 0,3739 · 0,3704 · 0,3704 · 0,3535 ·
0,3542 · 0,3563 · 0,3575 · 0,3615`

Convergiu. Pico ép.5, parada ép.20, distância 15. A ép.10 (0,3852) chegou perto
mas não superou o limiar de 0,001 sobre o pico.

## 🔴 TRÊS CORRIDAS, UMA CONCLUSÃO: a paciência 15 não se pagou

O critério combinado era "se B e C repetirem o padrão do A, são três corridas
dizendo o mesmo, e a decisão é do dono". **Repetiram.**

| variante | pico | parada | épocas após o pico | superações após o pico |
|---|---|---|---|---|
| A | ép. 8 | ép. 23 | 15 | 0 |
| B | ép. 8 | ép. 23 | 15 | 0 |
| C | ép. 5 | ép. 20 | 15 | 0 |

**Nas três, o pico veio entre a época 5 e a 8, e nenhuma das 45 épocas seguintes
superou o próprio pico.** O `lr_drop=15` — a queda de 10× no LR que justificava
subir a paciência de 8 para 15 — não produziu o segundo salto em nenhuma delas.

O preço, medido: as épocas gastas após o pico custaram **~US$ 3,3 dos US$ 4,9**
da rodada, e entregaram exatamente os mesmos três artefatos (o `best` é anterior
ao pico em todas). Com paciência 8, as três teriam parado nas épocas 16, 16 e 13
— mesmos modelos, ~40% menos GPU.

**Decisão é do dono.** Três corridas do MESMO acervo não provam que a paciência
15 é errada para todo dataset; provam que para ESTE acervo ela vem cobrando um
terço da conta sem ter entregue nada em 3 de 3 oportunidades.

---

## ⚠️ A RÉGUA — leia antes de comparar qualquer número daqui com qualquer outro

Os números desta página são **AP no split `val` da própria variante**. Eles
servem para responder "este treino convergiu?" e para NADA MAIS.

**Não compare o 0,439 / map50 0,764 da variante A com o 0,550 do censo dos 11
modelos.** São réguas diferentes em três eixos ao mesmo tempo:

- **Conjunto diferente:** cada modelo foi medido no `val` do SEU dataset. Foi
  exatamente esse o erro metodológico que o censo desmontou — um ranking em que
  cada competidor corre numa pista própria não ordena nada.
- **Número de classes diferente:** A tem 5 classes, o baseline tem 11. mAP é a
  média por classe; menos classes, e classes mais fáceis, inflam o número
  sozinho, sem o modelo ser melhor em nada.
- **Distribuição diferente:** o `val` de cada variante herda a densidade de
  rótulos daquela taxonomia.

**A única comparação que vale é o holdout congelado**, idêntico nas três
variantes (`dataset-v2/split_membership.json`, mesma membresia por construção),
rodado também no baseline v10-ft. Qualquer conclusão sobre "qual taxonomia é
melhor" tem de sair de lá, não desta página.
