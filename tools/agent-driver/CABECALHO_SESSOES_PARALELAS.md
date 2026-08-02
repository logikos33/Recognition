# Cabeçalho de sessões paralelas — colar no topo de TODO prompt

> Motivo: em 2026-07-31 duas sessões do Code trabalharam o mesmo tema. Resultado: trabalho duplicado, dois merges
> descoordenados em `develop`, e uma sessão quase **sobrescreveu** a correção de auth da outra (só um teste
> pré-existente pegou). A regra abaixo existe pra isso não repetir.

---

## Bloco A — SESSÃO 1 (dona de `services/api/**`)

```
[SESSÕES PARALELAS — leia antes de tudo]
Há OUTRA sessão do Code rodando em paralelo. Regras:
- VOCÊ é dona de: services/api/** (API, stream, cameras, auth, handlers).
- NÃO TOQUE em: services/edge-sync-agent/** e infra/migrations/** (são da outra sessão).
- VOCÊ PODE mergear PRs (com CI verde).
- Antes de editar um arquivo, confirme que a develop não mudou nele desde sua cópia (git fetch + diff).
  Se um teste existente falhar de forma inesperada, PARE: provavelmente a outra sessão já entregou ali.
- Achado FORA do seu diretório = RELATÓRIO, não código. Descreva com file:line e siga.
- ⛔ NUNCA rode `git clean` (nem -fd/-fdx) nesta árvore. Há documentos NÃO COMMITADOS do Vitor/Claude aqui —
  um `git clean` já apagou ADR, runbooks, planos e um .pptx. Se precisar limpar, LISTE antes (`git clean -nd`)
  e peça confirmação.
```

## Bloco B — SESSÃO 2 (dona de `edge-sync-agent` + `migrations`)

```
[SESSÕES PARALELAS — leia antes de tudo]
Há OUTRA sessão do Code rodando em paralelo. Regras:
- VOCÊ é dona de: services/edge-sync-agent/** e infra/migrations/**.
- NÃO TOQUE em: services/api/** (é da outra sessão — inclusive stream_handlers.py e camera_service.py).
- VOCÊ NÃO MERGEIA. Abra o PR, deixe verde e avise o Vitor — o merge é da outra sessão/dele.
- Antes de editar um arquivo, confirme que a develop não mudou nele desde sua cópia (git fetch + diff).
  Se um teste existente falhar de forma inesperada, PARE: provavelmente a outra sessão já entregou ali.
- Achado FORA do seu diretório = RELATÓRIO, não código. Descreva com file:line e siga.
- ⛔ NUNCA rode `git clean` (nem -fd/-fdx) nesta árvore. Há documentos NÃO COMMITADOS do Vitor/Claude aqui —
  um `git clean` já apagou ADR, runbooks, planos e um .pptx. Se precisar limpar, LISTE antes (`git clean -nd`)
  e peça confirmação.
```

---

## Como usar
1. Escolha o bloco conforme a sessão e cole **no topo** do prompt, antes do conteúdo.
2. Se trocar quem é dona de quê, **atualize os dois** blocos na mesma leva — nunca só um.
3. Se as sessões forem trabalhar no MESMO diretório, **não paralelize**: rode em sequência.

## Regras que valem sempre
- **Um só merge.** Duas sessões mergeando em `develop` sem se ver foi o que virou risco real.
- **Achado fora do escopo vira relatório** — quem repassa é o Vitor. Evita a corrida por escrever no mesmo arquivo.
- **Teste inesperado falhando = sinal de colisão**, não de bug seu. Pare e reporte.
- Se a duplicação já aconteceu: **quem chegou depois reverte**, não "resolve o conflito" — o código já mergeado é a
  fonte de verdade.
