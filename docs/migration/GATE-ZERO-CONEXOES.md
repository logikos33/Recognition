# Gate Zero — as conexões, medidas
> A régua da missão: quantas conexões front↔backend estão PROVADAS no front novo.
> Levantado por 5 agentes, um por domínio, lendo os blueprints reais do backend e
> cruzando com quem chama no front antigo e no novo.

## Legenda
| estado | significa |
|---|---|
| **PROVADO** | o front novo chama **e** há teste que exercita a chamada |
| MIGRADO_NAO_PROVADO | o front novo chama, sem teste que cubra |
| PENDENTE | a tela que usaria ainda não foi migrada (F2/F4/F5/F6) |
| SO_ANTIGO | só o front antigo usa, e a substituta não cobre |
| ORFAO | nenhum dos dois usa |

## Por domínio

| domínio | conexões | provadas | pendentes |
|---|---:|---:|---:|
| dashboard | 13 | 3 | 4 |
| operacoes | 20 | 0 | 6 |
| alertas | 17 | 7 | 0 |
| cameras | 48 | 9 | 2 |
| plataforma | 112 | 0 | 41 |
| **total** | **210** | **19** | **53** |

## Total

| estado | n |
|---|---:|
| PROVADO | 19 |
| MIGRADO_NAO_PROVADO | 14 |
| PENDENTE | 53 |
| SO_ANTIGO | 49 |
| ORFAO | 75 |

**19 de 210** provadas.

## Como ler estes números com honestidade

A granularidade **não é uniforme entre domínios** — 'plataforma' levantou 112
conexões e 'dashboard' 13, porque o primeiro varreu auth + tenant-context +
branding + admin inteiros. Comparar domínios pelo tamanho não diz nada; o que
vale é o estado dentro de cada um.

Os 75 ÓRFÃOS não são novidade desta rodada: o mapa de contrato de 23/08 já
registrava 61 entradas órfãs em 421. São rotas que o backend serve e ninguém
chama — assunto de limpeza, não de migração.

Zero PROVADO em 'operações' e 'plataforma' é o esperado: são as fases F4/F5, que
nem começaram.

## Detalhe

O `journal.jsonl` do run `wf_0c83a71e-7ed` guarda cada conexão com
`arquivo:linha` do chamador novo, do antigo, e a rota do backend.
