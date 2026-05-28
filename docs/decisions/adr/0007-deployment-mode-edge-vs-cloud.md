# ADR 0007 — Modo de Deployment: Edge vs Cloud-Only

## Status

Aceito

## Data

2026-05-27

## Contexto

A inferência YOLO pode ser executada de duas formas distintas:

- **Cloud-only**: frames ou streams são enviados ao worker Celery no Railway para inferência centralizada. Simples de operar, sem hardware dedicado no cliente, mas dependente de internet estável e introduz latência de rede.
- **Edge (local)**: inferência executa diretamente no edge box instalado no cliente (GPU NVIDIA local). Latência mínima, operação offline possível, mas requer hardware dedicado e processo de deploy no cliente.

Clientes como RVB Isolantes possuem câmeras em rede interna sem internet confiável ou com restrições de firewall que impedem o envio de streams para a nuvem. Para esses casos, cloud-only é inviável.

## Decisão

Introduzir a variável de ambiente `DEPLOYMENT_MODE` para selecionar o modo de operação:

- `DEPLOYMENT_MODE=cloud_only`: inferência via Celery worker no Railway. Streams não saem da nuvem. Modo padrão para Fases 0-2.
- `DEPLOYMENT_MODE=edge`: inferência local via `services/inference` (DeepStream ou Ultralytics conforme `INFERENCE_ENGINE`). Edge box publica resultados no Redis local; `edge-sync-agent` sincroniza eventos relevantes com a API cloud.

Ambos os modos usam a mesma interface Redis pub/sub (`detections:{camera_id}`) e a mesma API REST/WebSocket, tornando o frontend agnóstico ao modo de deployment.

## Consequências

- Edge habilita operação offline e em redes isoladas: requisito crítico para clientes industriais.
- Edge requer hardware NVIDIA com CUDA e stack DeepStream ou PyTorch instalados no cliente.
- `edge-sync-agent` é necessário no modo edge para sincronizar alertas, frames anotados e métricas com a nuvem quando a internet estiver disponível.
- Fases 0-2 usam exclusivamente `cloud_only`; Fase 3 introduz `edge` com o primeiro cliente piloto.
- Testes de integração cobrem ambos os modos via mock do Redis pub/sub.
- Documentação de onboarding de cliente deve especificar claramente qual modo está sendo configurado e os requisitos de hardware correspondentes.
