# ESTADO — LOOP DO PROPOSITOR (reentrante)

> 1º ato de toda sessão: `git fetch` + ler este arquivo do `origin/develop`. Ele MANDA sobre o prompt.

## Marcos

| marco | estado |
|---|---|
| **M0** · #502 no ar (âncora `id:0`) | 🔄 em andamento — pytest quebrou em 2 testes que fixavam o formato antigo; ambos ajustados |
| **M1** · re-congelar (`v8-propositor`) | ⏳ |
| **M2** · pré-voo | ⏳ |
| **M3** · treino 50 ép | ⏳ |
| **M4** · runner → propostas na tela | ⏳ |

## 🔴 Custo acumulado da missão: **US$ 0,00** (teto US$ 12 · por pod US$ 5)
Nenhum pod disparado. O pré-voo reprovou o v7 antes de qualquer GPU.

## Fatos herdados
- `v7-propositor` **INVÁLIDO** (sem âncora) — descartar por etiqueta, ⛔ nunca DELETE
- 2.157 caixas humanas (3,76× a base do TREINO 2)
- propostas `ai` no banco: **zero** — régua da fase C nasce limpa
- flag DINO+SAM **OFF** (é o modelo errado para este runner)
- pós-processamento corrigido (#470, identifica tensor por FORMA)
- split degenerado conhecido (D-165): test com 26 imgs — números do harness são **ruído declarado**

## M1-A · Congelamento é FOTOGRAFIA, ⛔ não cadeado
A `dataset_version` é snapshot imutável **deste** treino. **A anotação ao vivo NÃO para em momento
nenhum** — o Vitor pode estar anotando durante o freeze, zero impacto.

Todo veredito dado durante/depois da foto **entra normalmente no banco** e estreia na **próxima**
versão (o candidato de quinta). ⛔ Nada é perdido ou ignorado.

O runner respeita isso **por desenho**: ⛔ não propõe sobre recorte com veredito humano — e o cheque
é feito **na escrita**, não na foto.

⚠️ **Implementação futura que pause a anotação para exportar é BUG.**

## Fila depois da missão
D-165 vira código até quinta (gate do candidato) · PR refill+retry da tela de boxes · quinta:
candidato com gate (régua D-163) · sexta: shadow + pacote main.
