# Mutirão de dívida técnica — ÍNDICE da fila (não é prompt de execução)

> Este arquivo é o mapa. **Os prompts de execução são os três `CHAT-*.md`** — um por chat do Claude Code.

## Como rodar

**Três chats sequenciais, um por bloco.** Não paralelize entre si: `railway_start.py` aparece nos **três** blocos
(A3 nos argumentos do gunicorn, B2 no `except ImportError`, C2 no loop de migration) e `stream_handlers.py` em A1 e
A4. Duas sessões nesses arquivos ao mesmo tempo é a colisão de 31/jul de novo.

| # | Arquivo | Escopo | Portão |
|---|---|---|---|
| 1 | `CHAT-1-BLOCO-A-DESTRAVAR-PROMPT.md` | Passo zero + deadlock do live view + introspecção + gargalo (7 itens) | live view sai do cold start **sozinho** |
| 2 | `CHAT-2-BLOCO-B-FALHAS-SILENCIOSAS-PROMPT.md` | Onda 1 — fail-fast, health honesto, sinal de degradação (8 itens) | cada fail-fast provado com antes/depois |
| 3 | `CHAT-3-BLOCO-C-MIGRATIONS-PROMPT.md` | Onda 2 — runner único, ledger, advisory lock, backfill (5 itens) | harness 2× + backfill provado |

**Mecânica:** em cada chat novo, mande apenas
> *"Leia e execute `tools/agent-driver/tasks/CHAT-N-....md`."*

e **cole o relatório do portão anterior**. O relatório é o handoff — o bloco seguinte precisa dos *resultados* do
anterior, não do raciocínio.

**Paralelização que É segura:** o mutirão (`services/api/**`) × a sessão do edge
(`services/edge-sync-agent/**`). Diretórios disjuntos.

## O que amarra a fila

- **A2 antes de A3.** Não mexer no `--max-requests` sem antes ter `ru_maxrss` — ele existe para conter vazamento, e
  é exatamente isso que ainda não sabemos se existe.
- **Z.2 do CHAT 1 define o B0 do CHAT 2.** Se os testes de integração estiverem skipados no CI, plugar isso vem
  antes de qualquer correção — senão o resto é afirmação, não prova.
- **C5 é o passo que pode quebrar produção.** O backfill precisa vir antes do cutover, e é coordenado com o Vitor,
  nunca autônomo.

## Fora desta fila (por decisão, não esquecimento)

| Onda | O quê | Por que fora agora |
|---|---|---|
| 0 | Credenciais, rotação, senha que se auto-restaura | Decisão do Vitor: não gateia a RVB; entra na varredura do dia do embarque final |
| 3 | Convite de tenant, recuperação de senha, `token_version` | Depende da Onda 0 |
| 4 | Arquitetura de vídeo (MediaMTX × R2+CDN × manter) | Depende da medição que o A2 destrava. Números em `CADERNO_SOLUCOES_MUTIRAO.md` § D-09 |
| 5 | Cursores/`base.py`, qualificar `public.` nos 14 repos, docs | `base.py` tem 208 chamadores; não misturar com o resto |
| — | CDRB de migrations (baseline + renumeração) | Exige congelamento e reconciliação entre 3 ambientes: operação humana coordenada |

## Documentos de apoio

- `docs/REGISTRO_DIVIDA_TECNICA.md` — o levantamento (26 itens, o que é real e o que os docs alegam falsamente)
- `docs/CADERNO_SOLUCOES_MUTIRAO.md` — a solução de cada item, com fonte e armadilha
- `docs/OBSERVABILIDADE_CONSUMO_API.md` (PR #259) — o levantamento que originou o Bloco A
