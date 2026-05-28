# ADR 0002 — Redis Pub/Sub como Transporte de Eventos de Inferência

## Status

Aceito

## Data

2026-05-27

## Contexto

Os resultados de inferência YOLO (bounding boxes, classes detectadas, confiança) produzidos pelo worker ou pelo edge box precisam chegar à camada de API para serem transmitidos via WebSocket aos clientes do frontend. Três opções foram avaliadas:

- **Polling no banco de dados**: API consulta tabela de detecções periodicamente. Simples, mas introduz latência e carga desnecessária no banco.
- **Redis pub/sub**: Mensagens publicadas pelo producer (inference engine) e consumidas pela API em tempo real. Mesmo Redis já usado como broker Celery.
- **Kafka**: Alta throughput, persistência de mensagens, particionamento. Overhead operacional elevado para o volume atual.

O volume de detecções esperado é de 5 FPS por câmera, com até 12 câmeras por tenant. Detecções são efêmeras — não há requisito de replay ou auditoria de eventos de inferência em tempo real.

## Decisão

Usar **Redis pub/sub** como transporte de eventos de inferência. Canal por câmera: `detections:{camera_id}`. A API assina os canais relevantes e faz broadcast via Flask-SocketIO para os clientes conectados.

A escolha aproveita a instância Redis já existente (broker Celery), eliminando a necessidade de infraestrutura adicional.

## Consequências

- Latência baixa: pub/sub Redis é sub-milissegundo na mesma rede.
- Sem persistência de eventos: mensagens perdidas durante reconexão do assinante não são recuperadas. Aceitável para detecções em tempo real (ephemeral by design).
- Acoplamento à disponibilidade do Redis: se o Redis ficar indisponível, tanto o Celery quanto o pub/sub de detecções são afetados simultaneamente. Redis é, portanto, componente crítico de disponibilidade.
- Escalabilidade horizontal limitada: múltiplas instâncias da API precisam assinar os mesmos canais — padrão suportado nativamente pelo Redis pub/sub.
- Monitoramento de Redis deve incluir alertas de memória e latência de pub/sub.
