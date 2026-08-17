# Roteiro — anotar 50 frames numa sentada

> Escrito depois de percorrer o caminho inteiro no DEV (10/08/2026): login → contexto RVB →
> filtro por câmera → sequência de 10 → caixas com tecla e `C` → reload → tudo no lugar.
> Alvo: **menos de 10 segundos por frame** em sequência da mesma câmera. 50 frames ≈ 15–30 min.

## Entrar (1 minuto, uma vez)

1. Login normal. Como superadmin você cai no **Painel Admin**.
2. **Tenants → "Assumir contexto"** na linha da RVB. O banner vermelho no topo
   ("Você está vendo como RVB…") confirma — sem ele, nada do que você fizer vai para a RVB.
3. Menu **EPI → Treinamento**, aba **Imagens**.

## Preparar a sequência (30 segundos)

4. **Filtre pela câmera** nos chips do topo (cada um mostra a contagem). Anotar uma câmera
   por vez é mais rápido — o olho se acostuma com o enquadramento.
5. Selecione o lote: **⌘+clique** no primeiro card, **Shift+clique** no último (pega o
   intervalo). A barra no rodapé mostra "N selecionados".
6. **"Anotar em sequência (N)"**. O estúdio abre no primeiro; a fila lateral mostra
   "N de M" e as próximas.
   - A lista fica **congelada** na abertura — frames novos da coleta não empurram sua posição.

## Anotar (o ciclo de ~10 segundos)

7. **Arraste** na imagem para desenhar a caixa. A classe aplicada é a ativa na paleta;
   **tecla numérica** troca (da caixa selecionada, ou a ativa para a próxima).
8. Frame quase igual ao anterior (pessoa andou meio metro)? **`C` copia as caixas do
   anterior** — só ajustar pelas alças. É o atalho que paga o dia.
9. **`D`** avança. **Salva sozinho** — "✓ Salvo" no topo. ⛔ **Nunca avance com banner
   vermelho de erro na tela**: ele significa que a última mudança ainda não está no servidor
   (nada se perde localmente; use "tentar de novo").
10. **Não sabe o que marcar? `F`** — marca "em dúvida" e avança. Não trave numa imagem;
    dúvidas se filtram e resolvem depois.

## Quando a imagem atrapalha

- Escura (cena noturna de CFTV): **`B`** abre brilho/contraste — só muda a exibição, nunca o arquivo.
- Detalhe pequeno (capacete de 20 px): **`+`/roda do mouse** dá zoom; **Espaço+arrastar** move.
- Muitas caixas na frente: **`H`** esconde/mostra as caixas.
- Errou: **Ctrl+Z** desfaz (Ctrl+Shift+Z refaz). Caixa errada: clique nela + **Del**.

## Atalhos — a tabela inteira

| Tecla | Ação | Tecla | Ação |
|---|---|---|---|
| `D` / `→` | próxima imagem | `H` | esconder/mostrar caixas |
| `A` / `←` | anterior | `B` | brilho/contraste (só exibição) |
| `1`–`9` | escolher classe | `+` / `−` / roda | zoom (Espaço+arrastar = mover) |
| **`C`** | **copiar caixas do frame anterior** | `Esc` | cancelar desenho / desselecionar |
| `F` | "em dúvida" e avança | `Ctrl+Z` / `Ctrl+Shift+Z` | desfazer / refazer |
| `Del` | apagar caixa selecionada | `?` / `G` | ajuda / diretrizes |

## Teclas de classe hoje (RVB, ordem por frequência)

As **6 classes** vigentes da RVB (D-103 — `Capacete`/`Colete` e suas variantes `Sem …`
**saíram**: não são EPI exigido na RVB; ver `docs/REGISTRO_DE_DECISOES.md`):

<!-- RVB-EPI-CLASSES:start (D-103 — fonte: docs/REGISTRO_DE_DECISOES.md; gate: scripts/ci/check_docs_gate.py) -->
- Protetor auditivo
- Sem protetor de ouvido
- mascara
- Sem mascara
- Uso incorreto de mascara
- Botas
<!-- RVB-EPI-CLASSES:end -->

| Tecla | Classe | | Tecla | Classe |
|---|---|---|---|---|
| `1` | Protetor auditivo | | `4` | Sem mascara |
| `2` | Sem protetor de ouvido | | `5` | Uso incorreto de mascara |
| `3` | mascara | | `6` | Botas |

Reordenar (muda a tecla!), renomear, cor e arquivar: **tela de Classes**
(`/epi/training/classes`, botão na galeria). O alerta de desbalanceamento aí é sério:
classe rara = modelo que parece bom e falha em produção.

## Como saber que ficou

Volte à galeria: o card ganha **selo "✓ Humana"** e a contagem de caixas. Recarregar a
página não perde nada — verificado no percurso. Toda caixa nasce com procedência
`manual` + quem anotou, gravadas no banco.

## Frame ruim (borrado, vazio, sem pessoa)

Selecione → **"Excluir da coleta"**. É reversível: aparece "Desfazer" na hora, e o filtro
**Excluídas** restaura depois. Nada é apagado de verdade.
