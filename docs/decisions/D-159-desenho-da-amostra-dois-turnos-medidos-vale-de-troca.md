# D-159 · Desenho da amostra: dois turnos medidos, vale de troca preservado

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ desenho aprovado — ⛔ mineração NÃO executada

Densidade normalizada por dias cobertos (canais 1–8, `source='nvr'`):

| Faixa | frames/dia-hora | Amostragem |
|---|---|---|
| **05h–16h** | 102–252 | ✅ **cheia** — turno principal |
| **20h–23h** | 84–98 | ✅ **cheia** — segundo turno, não sabido antes da medição |
| **17h–19h** | 22–34 | ⚠️ **leve, jamais zero** — é a troca de turno, quando se coloca e tira EPI: pouca gente, muita **transição de estado**, que é o que o classificador precisa distinguir |
| **01h–03h** | **0** | ⛔ fora — planta vazia |

⚠️ **Ressalva metodológica que fica no registro:** os frames são todos `source='nvr'`, extraídos em
janelas escolhidas manualmente. O eixo bruto media **"quando foi minerado"**, não "quando tem gente";
a normalização por dias cobertos aproxima densidade, mas segue **proxy, não censo**.

⛔ **Taxa de anotação NÃO é sinal de presença** — as 18h têm 24,2% de anotação com a menor densidade,
e isso reflete o que o Vitor **escolheu** anotar.

**Meta ~250/canal é ALVO, não cota:** canal que não chega com gente presente tem o **teto reportado**;
⛔ nunca completar com corredor vazio (frame sem pessoa não vira recorte e só engorda a fila).

**Consequência que sobe de prioridade:** havendo segundo turno das 20h às 23h, **há gente para detectar
no escuro**. Se a câmera não entrega recorte aproveitável em IR, isso é **buraco operacional do produto**,
não do dataset. Medir rejeição por faixa de hora; ⛔ **não baixar o limiar de nitidez de 150** para
forçar rendimento.
