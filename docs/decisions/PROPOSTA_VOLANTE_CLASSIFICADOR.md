# Proposta — o volante do classificador de recorte

**Escrito em 2026-08-25. Nada aqui está ligado.** É desenho para o Vitor
aprovar, e cada peça tem o número que a sustenta ou a marca explícita de que
não tem número.

Estado do que JÁ existe (não é proposta, está no ar):

- **Pré-seleção** — a aba Classificar já traz o veredito da proposta
  pré-marcado, Enter confirma, tecla corrige. `CropClassifier.tsx:1133`.
- **Fila por incerteza** — `ordenar=incerteza`, provada contra o banco.
- **Classificador v1** — 4 classes passando a régua no campo virgem.

---

## 1 · Auto-confirmação em lote (≥ 0,95) — PROPOSTA, NÃO LIGADA

### O que seria

Recorte cuja proposta tem confiança ≥ 0,95 é confirmado sem clique, e **1 em
cada 20** vai para uma fila de auditoria amostral onde uma pessoa confere.

### O número que ainda NÃO existe

⚠️ **Não sei a precisão do classificador acima de 0,95.** A régua atual mede no
melhor limiar por família (0,90 nas três treinadas), e o campo virgem tem
`n = 10..27` por classe. Numa faixa mais estreita (≥ 0,95) o `n` cai para uns
poucos, e um número sobre punhado é sorte — foi exatamente a razão de
`Sem Óculos` (66,7% sobre n=3) não virar aprovação no A/B do #536.

**Pré-condição para ligar:** medir precisão na faixa ≥ 0,95 com `n ≥ 30` **por
classe**, no campo virgem. Antes disso a auto-confirmação está confirmando o
quê, exatamente?

### Por que a auditoria amostral é 1 em 20, e o que ela detecta

Com 5% de amostragem, uma taxa de erro real de 2% aparece em ~1 de cada 10
lotes de 20 auditados. Não é vigilância contínua — é **alarme de deriva**: se a
câmera mudar de ângulo ou a luz do turno mudar, a taxa de erro sobe e a
amostra começa a acusar antes de o acervo estar contaminado.

**O que a amostra NÃO faz:** garantir que os 19 não-auditados estão certos. Com
19 confirmados às cegas por 1 conferido, o acervo aceita erro. A pergunta que o
Vitor tem de responder é: **quanto erro no acervo é aceitável para ganhar
velocidade?** Sem essa resposta, o desenho não tem alvo.

### Como seria reversível

Toda confirmação automática nasce com `source='auto_aprovada'` e
`proposal_model_id` preenchido — a proveniência da ADR-0066 já cobre isso. Um
lote ruim é identificável e **removível do treino por filtro**, sem `DELETE`:
basta o export parar de aceitar aquele `proposal_batch_id`.

Isso é o que torna a proposta segura de experimentar: o erro é reversível
porque a caixa diz quem a desenhou.

### ⛔ Não executei

Ativação é decisão do Vitor. Não escrevi código de auto-confirmação.

---

## 2 · Retreino por ciclo

### O gatilho

A cada **N vereditos humanos novos** (proposta: N = 150, ~metade do acervo
atual de uma família), dispara: exporta → treina → régua no campo virgem →
**A/B contra a versão em produção**.

### A regra de promoção

**Promove só se vencer.** E "vencer" tem definição, não é impressão:

- precisão ≥ a da versão em produção, **por classe**, no MESMO campo virgem;
- `n ≥ 10` na classe, senão "não afirma nada" e a classe não muda de versão;
- ganho sobre a linha de base mantido — modelo que empata com o chute cego
  reprova, mesmo tendo "melhorado".

### O campo virgem tem de continuar virgem

Este é o ponto que quebra retreino automático em quase todo lugar: se o campo
de teste crescer junto com o treino, cada ciclo mede num campo diferente e os
números não são comparáveis.

Por isso o `exportar.py` usa **partição por hash** (`_split_estavel`), não
ordenar-e-fatiar: o frame X cai sempre no mesmo lado, hoje e daqui a mil
anotações. Frame novo entra em `test` na mesma proporção, mas nenhum frame
**muda de lado**.

E o filtro de quase-duplicata continua valendo a cada ciclo — senão o acervo
crescente vai naturalmente aproximando treino e teste.

### Custo

Treino de uma família: **18 segundos em CPU**, medido. A cada 150 vereditos,
isso é ruído. ⛔ Não precisa de GPU, não precisa de RunPod, não conta no teto
de custo de missão.

---

## 3 · O círculo completo — veredito de alerta vira dado

### O que já existe

- O veredito humano é gravado em 5 colunas de `alerts`
  (`verification_status`, `verification_verdict`, `verification_reason`,
  `verified_at`, `verified_by`), pelo `human_review`.
- A prova de humanidade é o prefixo `user:` em `verified_by` — a IA grava as
  MESMAS colunas com `verified_by='claude-haiku'`, então a coluna do veredito
  sozinha não distingue máquina de gente.
- Três telas: detalhe (`/epi/alerts/:id`), fila (`/epi/verification`) e
  histórico (`/epi/alerts`).
- O alerta guarda o frame (`evidence_key`) e as caixas (`violations` jsonb com
  bbox em pixels + `bbox_unidade`).

### O elo que falta, medido

🔴 **`grep -n 'alert_id' infra/migrations/*.sql` devolve ZERO linhas nas 128.**
Não existe coluna, nem tabela de junção, que ligue um exemplo de treino ao
alerta de origem. Também falta `width`/`height` no alerta — sem eles não dá
para normalizar o bbox de pixels para YOLO no servidor.

E não há representação de **negativo**: um `reject` diz "isto não era violação",
que é informação valiosa e hoje morre na coluna.

### O que eu proponho, e o que NÃO proponho

**Proponho:** uma migration forward-only que acrescente `alert_id UUID NULL` em
`training_frames` (e `width`/`height` em `alerts`), mais o caminho que
transforma veredito em exemplo carregando essa proveniência.

**NÃO proponho** ligar isso nesta rodada, por uma razão concreta: o veredito de
alerta é sobre a **detecção** (a caixa estava certa?), e o classificador de
recorte aprende sobre o **recorte** (a pessoa está de máscara?). São perguntas
diferentes sobre a mesma imagem. Misturar sem pensar contamina o acervo do
classificador com rótulos que respondem outra coisa.

O mapeamento correto é:

| veredito do alerta | o que ensina ao classificador |
|---|---|
| `approve` em `Sem mascara` | recorte daquela pessoa = `mascara/sem` ✅ |
| `reject` em `Sem mascara` | ⚠️ **ambíguo** — a pessoa estava de máscara, OU a caixa pegou a pessoa errada, OU não dava para ver |

**A coluna `verification_reason` é o que desambigua**, e é por isso que ela
importa mais do que parece.

### 🔴 E aqui há um defeito pequeno com efeito grande

`AlertDetailPage.darVeredito` faz `POST /verification/:id/review` e **não envia
`reason`** — a rota aceita, o service grava, o frontend não coleta.
(`AlertDetailPage.tsx:110-121`.)

Ou seja: o campo que desambigua o `reject` — e que alimentaria tanto a
recalibração de limiar quanto o classificador — **nunca é preenchido pela
tela**. Corrigir isso é barato e é pré-condição do círculo.

---

## 4 · O que precisa de você

| # | decisão | por que trava |
|---|---|---|
| 1 | **Quanto erro no acervo é aceitável** para ganhar velocidade com auto-confirmação | sem alvo, 1-em-20 é número inventado |
| 2 | Ligar a auto-confirmação **depois** de medir ≥0,95 com n≥30/classe | hoje não há esse número |
| 3 | `alert_id` em `training_frames` — aprovar a migration | escrita de schema, gate humano |
| 4 | Coletar `reason` na tela de alerta | barato; só não fiz para não misturar com o PR do volante |

---

## 5 · Ordem que eu sugiro

1. **Coletar `reason` na tela** — barato, destrava tudo a jusante.
2. **Retreino por ciclo** — custo medido (18 s), regra de promoção definida,
   campo virgem já é estável por construção.
3. **Medir ≥0,95** — sai de graça do ciclo acima, quando o `n` crescer.
4. **Auto-confirmação** — só depois de (3), e com o alvo de erro da decisão #1.
5. **`alert_id`** — quando o mapeamento veredito→rótulo estiver decidido.

O que **não** deve vir antes: ligar auto-confirmação sem o número. Seria trocar
a régua por otimismo, que é exatamente o que esta rodada inteira passou
consertando.
