# Produto: Recognition Carga & Descarga (módulo `fueling` → produto)

> **Data:** 2026-06-11 · **Cliente âncora:** Roccabela (têxtil) · **Base:** módulo `fueling` existente.
> **Norte:** tudo configurável pelo front (sem codar) · multi-tenant → caminho whitelabel.
> Companion: `ARQUITETURA_E_MELHORIAS.md`, `PLATAFORMA_CENARIOS.md`.

## 1. Contexto (Roccabela)
Têxtil. Quer **contar rolos de tecido na carga E na descarga** (doca/baias). Dor declarada: **lentidão da doca,
erro de contagem e erro de expedição**. MVP: **só contar + auditar + dashboard** — a *conferência contra o
esperado* (romaneio/NF/ERP) é desejável mas fica pra fase 2.

## 2. O que JÁ temos (módulo `fueling`)
É, na prática, um **Controle de Carga e Descarga** já esboçado:
- Classes de detecção: `truck`, `plate`, `forklift`, `product_box`, `pallet` (migration 041).
- Conceito de **baias/docas**, **dashboard** (KPIs + séries), feed de **eventos**.
- **Mas é demo/mock**: superadmin vê dados fictícios (pra vender); cliente vê vazio. Falta o **pipeline real
  de contagem** e o **registro de sessão**.
→ O esqueleto do produto existe; falta o miolo que gera valor.

## 3. O que o mercado valida (pesquisa 2026)
Video analytics em doca: **−25–35% erro de carregamento**, **−30–50% furto/quebra**, **+~20% dock-to-stock**,
**ROI 200–350% em 12–18 meses**. Gartner: até 2027, 50% dos armazéns trocam conferência manual por visão.
O grande valor é **contar + CONFERIR contra o esperado** (fase 2); a fase 1 (contagem objetiva + tempo de doca +
auditoria) já entrega produtividade e registro.

## 4. Visão de produto
**A câmera conta os rolos que entram/saem por baia, registra cada operação (caminhão + horário + vídeo) e entrega
ao gestor um painel de produtividade e auditoria — depois passa a CONFERIR contra o esperado.**

Valor pro gestor (os 3 que a Roccabela marcou):
- **Produtividade (lentidão):** tempo de carregamento por baia/sessão, ociosidade da doca, throughput, gargalo por turno.
- **Erro:** contagem **objetiva e com vídeo** por sessão (substitui a contagem manual que erra).
- **Dados pra decisão:** dashboard por baia/turno/dia/caminhão + tendências + alertas + export.
- **Expedição/auditoria:** cada operação ligada a **placa/caminhão + horário + clipe de vídeo** = registro/prova.

## 5. Conceito central: **Sessão de carga/descarga**
A unidade de tudo. Uma sessão = **baia + caminhão(placa) + direção (carga|descarga) + total de rolos + início/fim
+ clipe de vídeo + evidência**. Começa quando um caminhão atraca, acumula a contagem, fecha quando sai.
- Fase 1: total contado (sem esperado). Campos `esperado` e `divergencia` já existem no modelo, **nulos** (plug da fase 2).
- Métricas derivadas: duração (lentidão), rolos/min, ociosidade entre sessões.

## 6. Fases
**Fase 1 — Contagem real + auditoria + dashboard (MVP que gera valor):**
1. **Operation-type de contagem de rolo na doca** (reusa `counting_line` + DeepSORT + voto multi-amostra da task-038;
   direção in=descarga / out=carga). Por baia/câmera.
2. **Sessões** (`loading_sessions`): agrupar contagem por baia+caminhão+direção+tempo+vídeo (migration nova).
3. **Ingest real** substituindo o mock: eventos de cruzamento → sessões + totais.
4. **Dashboard real** (troca o mock): tempo por baia/sessão, ociosidade, throughput, por turno/caminhão, export (reusa task-043).
5. **Config pelo front:** definir baias (câmera + linha + direção), o que conta, threshold, modelo por câmera (045), tuning (039).
6. **Evidência:** clipe + placa + timestamp por sessão (reusa `frames`/R2).

**Fase 2 — Conferência (onde o valor explode):** fonte do esperado (manual / **ERP-WMS** / **OCR do romaneio-NF**,
já temos OCR no Qualidade) → alerta de divergência ("faltou/sobrou X" + janela + vídeo). Anti-furto e anti-disputa.

**Fase 3 — Produto/whitelabel:** branding por tenant, onboarding self-serve, NOC multi-site, empacotamento comercial.

## 7. Reuso (quase nada é do zero)
| Peça do produto | Reusa |
|---|---|
| Contar rolo na linha da doca | `counting_line` + DeepSORT + **038** (voto multi-amostra) |
| Config por baia/câmera | motor de `operations`/cenários + editor (023) |
| Modelo de rolo por câmera | **045** (modelo por câmera) + **039** (tuning) |
| Evidência/auditoria | `frames` + R2 |
| Relatórios pro gestor | **043** (relatórios de compliance, generalizado) |
| Alertas | `alert_rules` + **042** (notificação) |
| Multi-tenant / whitelabel | schema-por-tenant existente |
| OCR (fase 2) | PaddleOCR do módulo Qualidade |

## 8. Risco principal
**Modelo de detecção de "rolo de tecido"** — é o único item de trilha humana+dados (treino custom, como Qualidade).
Rolo tem formato/empilhamento próprios; precisa de dataset da doca da Roccabela. O resto **reusa o que já temos**.
Mitiga começando com coleta de vídeo da doca real cedo (mesma lição da pesquisa de 30+ câmeras).

## 9. Próximos passos (Fase 1 → tasks)
- `loading_sessions` (migration) + ingest real (substitui mock).
- operation-type de contagem de rolo (reusa counting_line/038) + direção carga/descarga.
- dashboard real (tempo/ociosidade/throughput por baia/turno/caminhão) + export.
- config de baia pelo front (câmera+linha+direção+modelo+threshold).
- coleta de dataset de rolo (trilha de modelo).
