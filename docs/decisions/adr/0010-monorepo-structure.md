# ADR 0010 — Monorepo como Estrutura do Repositório

## Status

Aceito

## Data

2026-05-28

## Contexto

O projeto Recognition cresceu de um monolito Flask para múltiplos serviços independentes (API, worker, frontend, landing, pre-annotation, edge-sync-agent, inference). Duas abordagens de organização de repositório foram avaliadas:

- **Polyrepo**: cada serviço em repositório Git independente. Máxima independência de deploy, mas overhead de sincronização entre repos, duplicação de código compartilhado, dificuldade de visualizar mudanças cross-serviço, múltiplos PRs para uma única feature.
- **Monorepo**: todos os serviços em um único repositório. Visibilidade completa, mudanças cross-serviço em um único commit, código compartilhado sem publicação de pacote, histórico unificado.

O Railway suporta monorepo nativamente via `rootDirectory` por serviço, permitindo builds independentes a partir do mesmo repositório.

## Decisão

Manter e formalizar a estrutura de **monorepo único "Recognition"** com a seguinte organização de diretórios:

```
services/
  api/               # Flask API + SocketIO
  inference/         # Engine de inferência (DeepStream/Ultralytics)
  edge-sync-agent/   # Sincronização edge→cloud
apps/
  frontend/          # React 18 + TypeScript + Vite
  landing/           # Astro 4 + demo ONNX
shared/
  python/            # Libs Python compartilhadas (auth, responses, validators)
  proto/             # Definições de schema de mensagens Redis
  ts-types/          # Tipos TypeScript compartilhados
infra/
  migrations/        # Migrations SQL globais e por tenant
  railway/           # Configurações Railway por serviço
deployments/         # Configs de deployment (edge box, cloud)
deepstream/          # Pipelines e configs GStreamer/DeepStream
models/              # Modelos YOLO base e versionados
docs/                # ADRs, runbooks, API docs, decisões
tests/               # Testes de integração e E2E cross-serviço
```

Histórico Git preservado via `git mv` na reorganização. CI/CD usa path filtering para buildar apenas serviços afetados por cada push.

## Consequências

- Visibilidade total de mudanças cross-serviço em um único PR e commit.
- `shared/` elimina duplicação de código entre serviços Python e TypeScript sem necessidade de publicar pacotes privados.
- Path filtering no CI obrigatório para evitar rebuilds desnecessários de todos os serviços a cada push.
- Railway configurado com `rootDirectory` por serviço apontando para o subdiretório correto dentro do monorepo.
- Histórico Git unificado: `git log` mostra evolução de todos os serviços no mesmo grafo de commits.
- Merges de branches de feature requerem atenção a conflitos em `shared/` quando múltiplos serviços evoluem em paralelo.
- Tamanho do repositório cresce com modelos e assets em `models/` — considerar Git LFS para arquivos `.pt` e `.onnx` acima de 50 MB.
