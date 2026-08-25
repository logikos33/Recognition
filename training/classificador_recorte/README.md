# Classificador de recorte — v1

Caminho 2 da [ADR-0067](../../docs/decisions/adr/0067-violacao-nasce-de-julgamento-positivo-de-ausencia.md):
pessoa (âncora) → recorte → veredito `{com | sem | não visível}`.

## O que isto é, e o que deliberadamente NÃO é

**É:** uma cabeça linear multiclasse sobre embeddings **congelados** do DINOv2
ViT-S/14. Treina em CPU, em segundos, sobre 420 recortes.

**Não é:** fine-tuning de rede convolucional. Com 27 a 95 exemplos na classe
minoritária, treinar um backbone é o caminho mais curto para decorar o conjunto
de treino e produzir uma régua que mente.

O backbone congelado é a escolha honesta para este tamanho de acervo, e é
reversível: quando o acervo crescer, o mesmo dataset alimenta um fine-tune sem
mudar nada a montante.

## Licença — zero AGPL no caminho servido

| peça | licença | origem |
|---|---|---|
| DINOv2 ViT-S/14 | **Apache 2.0** | `docs/WEIGHTS_LICENSES.md`, sha256 pinado e verificado |
| cabeça linear | nossa | treinada aqui |
| torch / numpy / pillow | BSD / MIT | já pinados em `requirements/` |

Nada novo entra no `requirements`. O gate de licença do CI continua valendo.

## O acervo (medido em 2026-08-25, banco do DEV)

**420 frames** com veredito, **1.095 anotações** — 2,6 rótulos por frame, porque
um recorte carrega o veredito de várias famílias ao mesmo tempo.

| família | com | sem | uso incorreto | minoria | treina? |
|---|---:|---:|---:|---:|---|
| máscara | 74 | 158 | 31 | 31 | ✅ |
| luvas | 48 | 183 | — | 48 | ✅ |
| óculos | 120 | 95 | — | 95 | ✅ |
| auditiva | 247 | 27 | — | 27 | ⚠️ minoria pequena demais |
| botas | 112 | **0** | — | **0** | ⛔ zero negativos |

`botas` não tem um único exemplo de ausência: um classificador aqui aprenderia
"sempre com" e teria 100% de acurácia sendo inútil. Fica de fora até a mineração
dirigida trazer negativos.

`auditiva` tem 27 exemplos na minoria. Treina, mas a régua manda — e a régua vai
provavelmente reprovar.

## Rótulo faltante ≠ rótulo negativo

A aba Classificar **não grava nada** para "não visível". Por família, a ausência
de rótulo significa "não visível **ou** ainda não julgado" — as duas coisas, sem
distinção no dado.

Consequência de desenho: cada família treina **só nos frames que têm rótulo
daquela família**. Não se inventa negativo a partir de silêncio — é o mesmo
princípio da ADR-0067 aplicado ao dataset.

Consequência prática: **a abstenção do v1 vem da confiança, não de uma classe
aprendida.** O modelo não sabe reconhecer "não visível" porque nunca viu um
exemplo rotulado assim. Está registrado como dívida: gravar o veredito
"não visível" explicitamente é o que destrava aprender abstenção de verdade.

## Partição

Aleatória por frame, estratificada por rótulo, semente fixa.

Não é por câmera, e isso é uma escolha: **58% dos frames vêm de 3 câmeras**
(Entrada Expedição 90, Entrada Usinagem Madeira 01 89, Entrada WC 64). Segurar
uma câmera inteira fora responderia "funciona numa câmera nova?", que não é a
pergunta do go-live — as 28 câmeras do RVB são conhecidas.

A régua reporta **por câmera** de qualquer forma, para a concentração ficar
visível em vez de escondida na média.

## Uso

```bash
python training/classificador_recorte/exportar.py --saida /tmp/recortes
python training/classificador_recorte/treinar.py  --dataset /tmp/recortes
python training/classificador_recorte/regua.py    --dataset /tmp/recortes
```

`exportar.py` precisa de `DATABASE_URL` e das credenciais do R2.
