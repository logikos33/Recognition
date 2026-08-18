# D-036 · O fluxo do dataset — anotação é semente, não o dataset inteiro

**Seção:** Adendos de 04/08 (pós-rodada #288–#292) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Vitor · 🔄 · a implementar depois das câmeras ao vivo**

```
1. Vitor acessa as imagens da RVB           → conta Logikos + impersonação (D-37)
2. Anota ~N frames à mão                     → SEMENTE
3. DINO+SAM propaga                          → acha semelhantes e propõe a caixa (D-38)
4. Humano aprova ou rejeita cada proposta    → o portão de qualidade
5. Aprovadas formam o dataset                → pacote exportado para o R2
6. RunPod treina                             → modelo (D-33)
```

**A anotação manual é semente, não o dataset.** Dezenas anotadas à mão viram centenas propostas pela
máquina e aprovadas pelo humano. É o que tira a anotação do caminho crítico — com 8 câmeras produzindo
~136 frames/dia, anotar tudo à mão não escala.

**Onde vive o quê:** caixas e rótulos no **Postgres** (dado estruturado pequeno) · imagens no **R2**
(já vão) · **pacote do dataset no R2**, que é de onde o RunPod baixa.

⚠️ **Confrontar a ADR-0031 antes de assumir que a propagação funciona.** O DINO+SAM foi removido em maio
por "custo × qualidade ruim" — mas provavelmente numa tarefa diferente. Detectar "pessoa sem capacete"
do zero é difícil; **propagar a partir de uma caixa que o humano já desenhou é muito mais fácil** — o SAM
é feito para "dado este ponto, me dê a máscara", e o DINO para "ache imagens parecidas com esta".
Leitura de 10 minutos que decide se o passo 3 é viável.
