# ADR 0008 — Roboflow + Google Colab como Pipeline de Treinamento

## Status

Aceito

## Data

2026-05-27

## Contexto

Clientes precisam de modelos YOLO personalizados treinados em suas classes específicas de EPI (capacete, colete, óculos, luvas, etc. com variações de fabricante e cor). A plataforma precisa suportar o ciclo completo: anotação de imagens, versionamento de dataset, treinamento e upload do modelo resultante.

Três abordagens de infraestrutura de treinamento foram avaliadas:

- **Vast.ai GPU on-demand**: aluguel de GPUs por hora via API. Custo controlado, mas requer integração de SSH e orquestração de jobs. A implementação atual em `training.py` ainda é simulação (débito técnico registrado).
- **Infraestrutura de treinamento gerenciada** (AWS SageMaker, Vertex AI): escalável e automatizável, mas custo fixo alto e complexidade de integração elevada para o volume atual de treinamentos (< 10 por mês).
- **Roboflow + Google Colab**: Roboflow para anotação colaborativa, versionamento de dataset e exportação em formato YOLO. Google Colab (tier gratuito ou Pro) para execução dos jobs de treinamento com GPU T4/A100. Modelos exportados como `.pt` ou `.onnx` e enviados via API.

## Decisão

Adotar **Roboflow para anotação e versionamento de dataset** e **Google Colab para execução de treinamentos**. Modelos treinados são exportados manualmente pelo operador e carregados via endpoint `POST /api/models/upload`.

Não há pipeline de auto-retreinamento automatizado nesta fase. Cada ciclo de treinamento é disparado manualmente.

## Consequências

- Zero custo de infraestrutura de treinamento gerenciada: Colab gratuito cobre a maioria dos treinamentos de YOLOv8n/s com datasets de até ~5.000 imagens.
- Dependência de disponibilidade do Roboflow e Colab: interrupções bloqueiam o ciclo de treinamento. Aceitável dado o volume baixo e frequência mensal de treinamentos.
- Processo manual de upload de modelo: operador precisa exportar `.pt`/`.onnx` do Colab e fazer upload via API. Documentar o runbook de treinamento em `docs/runbooks/training.md`.
- Sem auto-retreinamento: novos dados anotados não disparam treinamento automaticamente. Adequado para Fase 1-2; pipeline automatizado planejado para Fase 3+.
- Versionamento de dataset no Roboflow garante rastreabilidade: cada modelo produzido referencia a versão do dataset usada no treinamento.
- Vast.ai permanece como opção futura para treinamentos maiores; integração SSH real deve ser implementada antes de ativá-la em produção.
