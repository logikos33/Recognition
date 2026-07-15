# LGPD / Privacidade — Monitoramento por CFTV (RIPD/DPIA)

> **STATUS: SCAFFOLD — precisa de revisão jurídica antes de valer como documento de conformidade.**
> Preenchido a partir de boas práticas de mercado (ver Fontes no `docs/BENCHMARK_BOAS_PRATICAS.md`). Campos com
> `⟨TODO⟩` exigem dado real do controlador (cliente) ou decisão do Vitor/jurídico.
> **Este documento não é aconselhamento jurídico.**

## Por que existe
Recognition grava e processa imagens de pessoas identificáveis (trabalhadores usando/omitindo EPI). Isso é
**dado pessoal** sob a LGPD (Lei 13.709/2018). Como o tratamento pode gerar risco a direitos e liberdades, a
ANPD recomenda um **Relatório de Impacto à Proteção de Dados (RIPD/DPIA)**. Este doc é o esqueleto desse RIPD
por tenant, mais a política de retenção e transparência.

## 1. Agentes de tratamento
- **Controlador:** ⟨TODO: o cliente — ex. RVB Isolantes⟩ (define finalidade e meios).
- **Operador:** Logikos / Recognition (processa em nome do controlador).
- **Encarregado (DPO):** ⟨TODO: nome/contato do DPO do controlador⟩.

## 2. Finalidade e base legal
- **Finalidade:** segurança do trabalho — verificação de conformidade de EPI, contagem/carga-descarga, qualidade.
- **Base legal (art. 7º):** ⟨TODO: normalmente **legítimo interesse** (segurança/saúde ocupacional) ou
  cumprimento de obrigação legal de SST; registrar o teste de proporcionalidade (LIA)⟩.
- **Não** usar as imagens para finalidade incompatível (ex. produtividade individual) sem nova base/aviso.

## 3. Dados tratados e minimização
- Imagens de câmeras; recortes/frames; clipes de evidência (~20-30s, ADR-0033); metadados de detecção.
- **Minimização:** capturar só o necessário; evitar áreas de intimidade (refeitório, banheiro, vestiário).
- **Anonimização quando possível:** avaliar blur de rosto/placa no pipeline de evidência — ⟨TODO: decisão⟩.
- **Anotação/treino (ADR-0047, ADR-0048):** frames usados para treinar o modelo custom do cliente são
  anotados na ferramenta própria do Recognition (`AnnotationInterface.jsx`), servida na infra da própria
  Logikos, e o dataset versionado (COCO) sobe para Cloudflare R2 sob controle da Logikos/cliente — em
  nenhum ponto desse fluxo a imagem é enviada a um SaaS de anotação de terceiro (CVAT/Label Studio cloud,
  Roboflow). Ver ADR-0048 para a investigação que confirmou isso.

## 4. Retenção e descarte (ligar ao módulo `retention`)
- **Prazo de guarda:** ⟨TODO: definir — mercado típico 15–90 dias⟩. Implementado via `retention_days`
  (migrations `052_cameras_retention_days.sql`, `079_retention_days.sql`; blueprint `retention`).
- **Descarte automático** ao fim do prazo, comprovável (log de expurgo). ⟨TODO: evidenciar o job de expurgo⟩.
- Evidência sobe cloud-first para R2 (ADR-0028); o edge não é destino de armazenamento persistente.

## 5. Transparência
- Aviso de monitoramento visível no local (placas), informando finalidade — responsabilidade do controlador.
- Política de privacidade acessível aos titulares. ⟨TODO: link/versão⟩.

## 6. Direitos do titular
- Procedimento para acesso, correção e eliminação, e canal do titular. ⟨TODO: descrever o fluxo operacional⟩.

## 7. Segurança do tratamento
- Isolamento multi-tenant (schema-per-tenant, cross-tenant→404); JWT/RS256; WireGuard; secret scanning; gate de
  licença. Ver `SECURITY.md`.

## 8. Avaliação de risco (RIPD)
- ⟨TODO: matriz risco × probabilidade × impacto para: vazamento cross-tenant, acesso indevido a imagens,
  retenção excessiva, uso desviado de finalidade — com as mitigações acima⟩.

## 9. Revisão
- Revisar a cada mudança relevante de tratamento (nova câmera/finalidade/módulo) e ao menos anualmente.
- **Assinaturas/aprovações:** ⟨TODO: controlador + DPO + Logikos⟩.

## Fontes
Ver seção "Fontes" em `docs/BENCHMARK_BOAS_PRATICAS.md` (ANPD/RIPD, LGPD em CFTV, monitoramento do empregado).
