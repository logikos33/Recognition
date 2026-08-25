# ADR-0066 — A caixa diz quem a desenhou

**Status:** Aceita · **Data:** 2026-08-25 · **Contexto:** rodada de correções da RVB (#536, #538)

## O problema

O treino de localização aprende com caixas. O gate de procedência (D-39, migration 095) decide o que
entra olhando `frame_annotations.source`. Duas coisas quebravam essa decisão em silêncio, e as duas
foram medidas no dado real do RVB.

### 1. Caixa que não é caixa

A aba Classificar responde *"este frame mostra a classe X?"* — pergunta de **classificação**. Ela
gravava o veredito com `[0,0,1,1]` (`CropClassifier.tsx: FULL_FRAME_BBOX`), um placeholder assumido
no próprio código enquanto não havia detector de pessoa para recortar. Mas o destino era a mesma
tabela e o mesmo `source='manual'` de uma caixa desenhada à mão.

| | anotações | com área ≥95% do frame | % |
|---|---:|---:|---:|
| `source='manual'` | 4.629 | **1.095** | **23,7%** |
| `source='pre_annotation'` | 2.853 | 3 | 0,11% |

Exatamente `cx=0,5 cy=0,5 w=1 h=1`, 1.095 vezes, em 420 frames sem nenhuma outra caixa. **Um quarto
do dado humano ensinava que "Protetor auditivo" é a imagem inteira.**

E o dano se concentrava onde mais dói: as três classes de ausência que não sustentam precisão são
exatamente as três com ~50% de rótulo de frame (46%, 50%, 54%), contra 5% e 12% nas duas que
sustentam.

### 2. Proveniência apagada pelo próprio save

`AnnotationRepository.save_batch` faz `DELETE` de todas as linhas do frame e reinsere com
`source='manual'` **cravado**. Abrir o estúdio num frame de proposta aceita e salvar — sem tocar em
nada — convertia geometria do MODELO em "desenhada por humano".

Medido: **403 caixas** `source='manual'` com coordenadas idênticas às de uma proposta do mesmo frame
(v10_base_vencedor 195, v9_best 187, propositor_best 17, propositor 4), em 365 frames. As colunas de
proveniência da migration 124 (`proposal_batch_id`, `proposal_model_id`, `proposal_confidence`)
existiam e nasciam sempre vazias.

## A decisão

**1. Caixa que cobre o frame não é alvo de localização.** Corte na fonte
(`versioning_v2._e_rotulo_de_frame`, limiar de área 0,95), no único lugar por onde todo dado de
treino passa. A linha **não é apagada** — o rótulo continua valendo como classificação; ele só não
entra no treino de localização.

**2. Nenhum frame vai ao treino com zero caixas por causa de filtro.** Frame que perdeu todas as
caixas por qualquer filtro sai do dataset: mantê-lo com zero caixas ensina o detector a **não ver** o
que está ali, o que é pior que descartá-lo. Frame que nunca teve caixa alguma no banco é negativo
legítimo e fica (3 no RVB).

**3. A proveniência sobrevive ao save.** Antes do `DELETE`, o save fotografa as linhas do frame e
devolve `source`/`reviewed_by`/`proposal_*` a toda caixa cuja geometria voltou **idêntica** — que é
a definição operacional de "o humano não tocou nesta". Caixa movida, redimensionada, de classe
trocada ou nova entra como `manual`, que é o certo: aí a mão de gente passou por ela.

## Por que assim, e não de outro jeito

- **Por que não apagar os rótulos de frame?** Eles são dado válido de classificação. A regra da casa
  é nunca `DELETE`, e aqui ela também é a decisão certa: o problema é o destino, não o rótulo.
- **Por que igualdade exata de coordenada, e não uma tolerância?** Caixa não tocada volta do frontend
  com a MESMA coordenada. Uma tolerância larga passaria a tratar ajuste fino humano como "não
  mexeu" — que é justamente o que se quer distinguir. O arredondamento em 6 casas absorve o ruído de
  ida e volta entre float do Postgres, JSON e float do Python, e nada além disso.
- **Por que `area ≥ 0,95` e não `== 1,0`?** Para não depender de a UI gravar exatamente 1,0 para
  sempre. Nenhuma caixa legítima do RVB chega perto: a maior anotação real de ausência tem área
  média de 2,3% do frame.

## Consequências

- O braço "só-humano" do experimento do #536 **estava 11,4% contaminado** por geometria de modelo.
  O viés apontava CONTRA a hipótese, então uma vitória dele é conservadora; empate ou derrota fica
  ambíguo e pede repetição sobre o dado corrigido.
- A aba Classificar produz hoje **classificação, não detecção**. Enquanto ela não receber o recorte
  de pessoa real (#538), o dado dela não treina localização — e as classes de ausência, que são
  julgamento de pessoa inteira, continuam dependendo de mão humana caixa a caixa.
- A aceitação real do propositor subiu de 59,8% para **66,8%** quando a proveniência foi restaurada:
  o defeito também fazia o produto parecer pior do que é.

## Aberto

- Alimentar o `CropClassifier` com o recorte de pessoa real (#538) — o detector de pessoa já existe
  (`person_detector.py` + `yolox_nano.onnx`, rodando no box e no shadow).
- Migrar o gate de procedência de `source` para `proposal_model_id IS NULL`, que é o campo que **não
  pode** ser reescrito por um save. Enquanto o gate depender de `source`, ele depende de um campo
  que o caminho de escrita já provou saber destruir.
