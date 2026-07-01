# ADR-0027 — Training Environment UI

## Status: Accepted (2026-07-01)

## Contexto

O fluxo de treinamento atual depende de:
1. Exportar dataset via API (`GET /api/training/download-dataset`)
2. Fazer upload manual para Google Colab (ADR-0008)
3. Treinar externamente e fazer upload do modelo resultante

Isso cria atrito e opacidade: o operador não vê o que está treinando, não
acompanha o progresso em tempo real e não tem visibilidade sobre qualidade
por classe. A dependência de Colab como interface exposta também cria risco de
acesso não controlado.

Plataformas de treinamento avaliadas para integração direta:

| Plataforma | Modelo de uso | Decisão |
|------------|--------------|---------|
| Google Colab | Integração via notebooks | Descontinuado como UI principal |
| Vast.ai | GPU spot market, SSH | Adotado como provedor de compute |
| Railway GPU | Plano Enterprise | Custo proibitivo para MVP |
| Local GPU | Hardware do cliente | Opcional via agent futuro |

O objetivo é trazer a experiência de treinamento para dentro do produto, sem
expor credenciais de plataformas externas na UI principal.

## Decisão

### Princípio geral

O produto fornece a UI completa de treinamento. Plataformas externas (Vast.ai)
são **credenciais em Integrações**, não interfaces abertas ao operador.

### Componentes da UI de treinamento

#### 1. Galeria de imagens do dataset

- `GET /api/training/datasets/{id}/images` — paginado, filtrado por classe
- Grid de imagens com:
  - Classe(s) anotada(s) por imagem (badge)
  - Status: anotada / pendente / rejeitada
  - Botão de remoção do dataset (não apaga do R2, apenas desvincula)
- Filtros: classe, status, câmera de origem, data de captura

#### 2. Configuração de classes

- Checklist de classes disponíveis no módulo (`GET /api/modules/{code}/classes`)
- Operador seleciona quais classes incluir no treino
- Aviso automático se classe tem < 50 imagens anotadas (threshold mínimo recomendado)

#### 3. Métricas por classe (pós-treino)

- `GET /api/training/jobs/{id}/metrics` retorna mAP por classe, precision, recall
- Exibido como tabela + mini gráfico de barras por classe
- Comparação com versão anterior do modelo (delta mAP)

#### 4. Acompanhamento ao vivo (epoch/loss via WebSocket)

- Training-service publica progresso em `Redis PUBLISH training:progress:{job_id}`:
  ```json
  { "epoch": 45, "total_epochs": 100, "train_loss": 0.043, "val_loss": 0.051, "status": "running" }
  ```
- Frontend subscreve via Socket.IO room `training:{job_id}` ao abrir a página do job
- Exibe: barra de progresso de epochs, gráfico de loss (train vs val) em tempo real,
  status (`queued | running | completed | failed`)
- Ao finalizar, exibe botão "Publicar modelo" e link para métricas

#### 5. Vast.ai como credencial em Integrações

- Nova seção `Configurações > Integrações > Vast.ai`:
  - Campos: `API Key`, `GPU type preference`, `max_price_per_hour`
  - `POST /api/integrations/vast-ai` salva credenciais criptografadas (não em JSONB puro —
    usar campo `TEXT ENCRYPTED` ou variável de ambiente por tenant via Railway)
- Training-service usa a credencial do tenant para provisionar instância Vast.ai
- Operador nunca vê a interface do Vast.ai — apenas dispara treino pelo produto
- Fallback: se credencial ausente, job entra em fila local (simulação / CPU lenta)

### Localização dos componentes

```
pages/training/
├── TrainingJobsPage.tsx        # lista de jobs + botão "Novo treino"
├── TrainingJobDetailPage.tsx   # acompanhamento ao vivo + métricas
└── DatasetPage.tsx             # galeria de imagens + configuração de classes

components/training/
├── EpochProgressChart.tsx      # gráfico loss ao vivo
├── ClassMetricsTable.tsx       # mAP por classe
├── DatasetImageGrid.tsx        # galeria paginada
└── canvas/RoiDrawer.tsx        # (existente — reutilizado, ver ADR-0024)
```

## Consequências

- Operadores treinam modelos sem sair do produto e sem conta em Colab.
- Visibilidade de qualidade por classe antes de publicar o modelo.
- Vast.ai como credencial isola o produto de mudanças na API da plataforma —
  apenas o `training-service` conhece o protocolo Vast.ai.
- Débito atual: `_dispatch_vast_ai` em `training.py` é simulação (log de warning).
  Implementação SSH real é pré-requisito para o fluxo de treino ao vivo funcionar
  em produção. Rastreado em CLAUDE.md como débito técnico.
- WebSocket de progresso requer que o browser mantenha conexão durante o treino
  (pode durar horas). Frontend deve lidar com reconexão transparente e carregar
  estado atual do job ao reconectar.
