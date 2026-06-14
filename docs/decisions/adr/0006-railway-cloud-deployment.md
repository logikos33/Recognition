# ADR 0006 — Railway como Plataforma de Deploy Cloud

## Status

Aceito

## Data

2026-05-27

## Contexto

A plataforma Recognition precisa de uma infraestrutura cloud para hospedar os serviços de API, worker, frontend e landing page, além de PostgreSQL e Redis gerenciados. As opções avaliadas foram:

- **Heroku**: plataforma PaaS madura, mas com fim do tier gratuito e custo elevado para múltiplos serviços.
- **AWS ECS**: máxima flexibilidade e escala, mas overhead operacional alto (VPC, IAM, ALB, ECR, task definitions). Inadequado para equipe pequena sem DevOps dedicado.
- **VPS bare metal** (DigitalOcean, Hetzner): custo baixo por recurso, mas requer gerenciamento manual de OS, SSL, reverse proxy, deploys. Sem auto-scaling.
- **Railway**: PaaS moderno com suporte nativo a monorepo, auto-deploy via git push, plugins gerenciados (PostgreSQL, Redis), nixpacks para build sem Dockerfile, custo baseado em uso.

## Decisão

Usar **Railway** como plataforma de deploy cloud para todos os serviços. PostgreSQL e Redis são provisionados como plugins Railway (instâncias gerenciadas). Nixpacks detecta e builda automaticamente os serviços Python e Node.js a partir do repositório.

Serviços ativos no Railway:
- `api-v3` — Flask API + SocketIO (`SERVICE_TYPE=api`)
- `worker` — Celery Worker + Beat (`SERVICE_TYPE=worker`)
- `frontend` — React + Vite
- `landing-page` — Astro + demo ONNX (`SERVICE_TYPE=landing-page`)
- `pre-annotation-service` — DINO + SAM (`SERVICE_TYPE=pre-annotation`)
- `PostgreSQL` — plugin Railway
- `Redis` — plugin Railway

Branch `staging` dispara deploy automático. Branch `main` é protegida.

## Consequências

- Baixo overhead operacional: sem gerenciamento de OS, SSL automático, scaling por serviço.
- Auto-deploy em push para `staging`: ciclo de iteração rápido sem pipeline CI/CD adicional.
- Custo baseado em uso: cresce linearmente com recursos consumidos; monitorar para evitar surpresas de faturamento.
- Limites de CPU/memória por tier Railway: worker com torch/ultralytics pode atingir limites de memória (monitorar OOM).
- `rootDirectory` por serviço no Railway permite monorepo com builds independentes.
- Builds nixpacks: 2-3 minutos para serviços Python, sem necessidade de manter Dockerfiles.
- Variáveis de ambiente gerenciadas via Railway dashboard ou `railway variable set`.
