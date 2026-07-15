# `requirements/pre-annotation.txt` — conflito de dependência real (não travado)

**Data:** 2026-07-14
**Descoberto por:** tentativa de gerar lock com hashes (`fix/pin-python-deps`) e,
independentemente, pelo job `pip-audit` do PR #165 (`fix/ci-supplychain-sast`), que já
tinha falhado ao tentar resolver este mesmo arquivo.

## O problema

```
pip-compile --generate-hashes -r requirements/pre-annotation.in
```

falha com:

```
ERROR: Cannot install -r requirements/pre-annotation.in (line 9) and supervision>=0.19.0
because these package versions have conflicting dependencies.

RequirementInformation(requirement=SpecifierRequirement('supervision>=0.19.0'), parent=None)
RequirementInformation(requirement=SpecifierRequirement('supervision==0.6.0'),
  parent=LinkCandidate('.../groundingdino-py-0.4.0.tar.gz'))
```

`groundingdino-py==0.4.0` fixa `supervision==0.6.0` como dependência direta, mas
`requirements/pre-annotation.txt` pede `supervision>=0.19.0` — as duas versões nunca
podem coexistir num único ambiente resolvido com o resolvedor estrito do pip
(`resolvelib`).

## Por que isso não quebrou em produção (confirmado)

`requirements/pre-annotation.txt` (a versão neste diretório `requirements/`) **não é o
arquivo usado para instalar o pre-annotation-service em produção**. `railway_start.py`
(`SERVICE_TYPE=pre-annotation`) instala a partir de `pre-annotation-service/requirements.txt`
— arquivo próprio do serviço, que **tem** `groundingdino-py>=0.4.0` e `segment-anything>=1.0`,
mas **não tem `supervision` nem `transformers` como constraint direta**. Sem o
`supervision>=0.19.0` extra, o pip resolve livremente para o que `groundingdino-py` pede
(`0.6.0`) e não há conflito.

`requirements/pre-annotation.txt` divergiu do arquivo real e ganhou dois pacotes a mais
(`supervision>=0.19.0`, `transformers>=4.36.0`) que criam o conflito. Ele parece ser um
duplicado órfão — nada no `nixpacks.toml` raiz ou no `railway_start.py` o referencia.

## Por que não corrigi sozinho

Corrigir exigiria escolher uma de duas direções que mudam comportamento:
1. Rebaixar `supervision` para `==0.6.0` (compatível com `groundingdino-py==0.4.0`,
   mas uma API de 2023, bem atrás da `0.19+` pedida) — risco de quebrar código que
   espera a API nova.
2. Trocar/atualizar `groundingdino-py` para uma versão que aceite `supervision` mais
   novo, ou remover o pin de `supervision>=0.19.0` do arquivo.

Ambas são decisões de produto/ML, não uma tarefa de infraestrutura de CI. Por isso este
PR (`fix/pin-python-deps`) **não gera lock para este arquivo** — `requirements/pre-annotation.txt`
continua com ranges soltas (`>=`), exatamente como estava antes.

## Estado atual

- `requirements/pre-annotation.txt` — **sem lock**, sem hashes, inalterado por este PR.
- `.github/workflows/security-scan.yml` (job `pip-audit`, PR #165) já reporta a falha de
  resolução deste arquivo como achado não-bloqueante — ver
  `docs/runbooks/sast-sca-baseline-phase0.md`.
- O job `lockfile-check` (CI, `fix/pin-python-deps`) pula este arquivo explicitamente.

## Resolvido (2026-07-15)

Confirmado que nada referencia `requirements/pre-annotation.txt` (busca completa no repo por
`nixpacks.toml`, `railway_start.py`, scripts, workflows) além dos próprios artefatos de CI
listados acima. Arquivo removido; entrada correspondente também removida da matriz do job
`pip-audit` (`security-scan.yml`) e do `_EXCLUDED` de `scripts/check_license_gate.py`. O
serviço real de pre-annotation continua instalando normalmente a partir de
`pre-annotation-service/requirements.txt`, que nunca teve esse conflito.

## Próximo passo (fora deste PR)

Como o arquivo parece órfão (não referenciado por `nixpacks.toml` nem `railway_start.py`),
o caminho mais provável é remover `requirements/pre-annotation.txt` num PR dedicado —
mas confirmar antes que nenhum fluxo de dev local ou script esquecido ainda o usa.
Se alguém precisar dele para algo real, aí sim vale escolher a direção de correção
(rebaixar `supervision` ou trocar `groundingdino-py`) e gerar o lock normalmente.
