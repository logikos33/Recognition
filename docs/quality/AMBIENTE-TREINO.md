# O ambiente de treino como artefato

Objetivo do dono: *"o treino X rodou no ambiente Y, e o ambiente Y existe para
sempre"*. Este documento diz como isso está resolvido hoje, o que ficou de fora,
e o que destrava o resto.

## O problema, medido — não hipotético

Em **02/09/2026**, com os **mesmos pacotes de topo** e a **mesma imagem**, o
`pip install` montou ambientes diferentes em horas diferentes do **mesmo dia**, e
matou dois pods pagos na época 0:

| hora | job | erro | causa |
|---|---|---|---|
| 15h25 | `04508616` | — treinou 23 épocas, entregue | — |
| 18h38 | `b4d69cde` | `ImportError: cannot import name '_center'` | numpy misto 1.x/2.x: os `.py` da 2.x sobre o `.so` 1.x da imagem |
| 19h09 | `40e61279`, `b5569408` | `ImportError: cannot import name 'Sentinel'` | imagem traz `typing_extensions` 4.9.0; `pydantic_core` novo precisa de 4.13+ e não declara |

Nada nosso mudou entre 15h25 e 18h38. Mudou o que o PyPI oferecia. **Quem quebra
não é o pacote de topo — é a transitiva**, e pin de topo não alcança.

## A solução em vigor: lock de constraints

`training/vast/remote_train.py::_CONSTRAINTS` — 34 versões exatas, aplicadas com
`pip install -c`. `-c` restringe versões **sem instalar nada por si**: o conjunto
pedido continua sendo o do runner; cada transitiva resolvida cai na versão
provada.

Origem dos números: a execução da sonda `scripts/ops/sondar_ambiente.py` que
subiu e importou `rfdetr` com sucesso. Não foram escolhidos a dedo — são o
conjunto que **de fato funcionou**, lido de dentro do pod.

**Validado antes de tocar em treino pago** (sonda `71b039a61daf`, pod
`ua87z44iqmrq23`): `pip_returncode 0`, `import_rfdetr OK`, e as versões
resolvidas iguais às do lock — prova de que as constraints seguraram.

`torch` está deliberadamente **fora** do lock: a imagem traz `2.4.1+cu124`, build
que não existe no PyPI; pinar faria o pip tentar buscar e falhar. Nada da lista
pede torch, então ele fica intocado.

## A sonda de ambiente — o que mudou o custo de descobrir

`scripts/ops/sondar_ambiente.py` roda o **mesmo** `pip_install` e o **mesmo**
lock (lidos do runner por regex, nunca recopiados) e só `import rfdetr`.

| caminho | tempo até saber | custo |
|---|---|---|
| disparo normal de treino | ~50 min (o `dataset.zip` — 4.983 downloads + 349 MB — é montado ANTES do pip) | US$ 0,03 + o pod |
| sonda | **~4 min** | **US$ 0,04** |

As duas correções de dependência de 02/09 queimaram o ciclo de 50 min para
descobrir, no minuto 50, que faltava mais um pin. A sonda inverte isso — e de
quebra foi ela que produziu o conjunto resolvido que virou o lock.

## O que o lock NÃO cobre (e a imagem cobriria)

- **Yank no PyPI.** Se alguma dessas versões for removida do índice, o lock
  quebra e não há cópia local de onde tirar. Risco real, pequeno, e explícito
  aqui porque escrito é melhor que implícito.
- **Tempo de boot.** O lock não evita o `pip install`: ~4 min por pod, toda vez.
  Uma imagem pronta zeraria isso.

## Imagem congelada — BLOQUEADA, e o que exatamente destrava

Não foi construída, por decisão consciente (o dono autorizou seguir com os pins
em vez de travar o fluxo):

1. **Registry — gate do dono.** Docker roda local (29.6.2), mas
   `~/.docker/config.json` está com `auths: []` (sem login no Hub). O `gh` está
   autenticado como `logikos33` com escopos `gist, read:org, repo` — **falta
   `write:packages`**, exigido para push no GHCR.
   **Destrava com:** login no Docker Hub, **ou** `write:packages` no token do gh.
   Nenhuma conta foi criada nem imagem foi subida em lugar nenhum.
2. **Custo de build aqui é proibitivo.** Manifesto medido sem baixar: a base
   `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` tem 28 camadas e
   **6,92 GB comprimidos** (~20 GB descompactados). Esta máquina é **arm64** e o
   pod é **amd64** → build sob emulação QEMU. Estimativa: 3-6 h de relógio,
   ~7 GB de download e ~10 GB de push, competindo por banda com os treinos.
3. **A RunPod aceita imagem customizada — confirmado no código**, não presumido:
   `RunPodClient.create_pod(image=...)` → `"imageName": image`
   (`runpod_client.py:180,192`) e `run_runpod_job(image=_DEFAULT_IMAGE)`
   (`runpod_runner.py:421`).
   ⚠️ **Dívida achada de brinde:** `_run_runpod_train_job` **não encaminha
   `image=`**, então o parâmetro é inerte no caminho de treino. A imagem, quando
   existir, exige esse fio ligado — melhor descoberto agora que no dia do build.

Quando houver registry, o lock não atrapalha a imagem: vira o `pip install -c`
de dentro dela, e a imagem passa a ser a defesa primária com o lock como segunda
linha para quem rodar fora dela.
