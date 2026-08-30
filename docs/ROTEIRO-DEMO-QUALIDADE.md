# Roteiro de demo — Qualidade (quarta 02/09)

**Objetivo:** Mostrar a segunda ala da casa (módulo Qualidade no front novo) sem prometer o que não está pronto.

**Base:** https://frontend-desenvolvimento-be93.up.railway.app (front novo sob `/novo/` até o FLIP; pós-flip as mesmas rotas valem sem `/novo/`).

---

## Passos da demo

### 1. Login → Dashboard Gestão
- **URL:** https://frontend-desenvolvimento-be93.up.railway.app/novo/quality/gestao
- **Mostrar:** Painel com 6 KPIs (Peças hoje, % aprovadas, NC hoje, Retrabalho ativo, Estações, Fila de revisão) + três gráficos: Retrabalho por etapa de validação, Defeitos por categoria, Fila de revisão. Navegar entre abas (Dashboard → Peças & OPs → Relatórios).
- **Dizer:** "Aqui o gestor vê tudo que aconteceu hoje: quantas peças, aprovação, o que deu ruim e como estão as estações. Os números vêm direto do servidor, não é imaginação."

### 2. Revisão de inspeções
- **URL:** https://frontend-desenvolvimento-be93.up.railway.app/novo/quality/revisao
- **Mostrar:** Fila de revisão com inspeções pendentes (ID, câmera, IA apontou OK/NOK, classe, idade). Clicar em um item para ver detalhe: foto da inspeção, botões CONFORME (A) e NÃO CONFORME (N) — atalhos de teclado funcionam. ⚠️ Escolher ANTES um item cuja câmera tenha referência assinada (o painel direito fica vazio sem ela — não abrir esse na frente do cliente).
- **Dizer:** "O operador revisa o que a IA achou — confirma ou corrige com dois cliques. Os filtros de turno e câmera ajudam a focar. Tudo o que foi decidido sai da fila."

### 3. Configuração de estações e câmeras
- **URL:** https://frontend-desenvolvimento-be93.up.railway.app/novo/quality/configuracao
- **Mostrar:** Aba "Limiares & estações" (C2). Tabela de câmeras com limiares de confiança (em cinza, travado) + tabela de estações com código, nome, câmeras vinculadas e situação (somente leitura). Aba "Pontos & rotas" (C1) está vazia propositalmente — explica por escrito por que não há ponto de inspeção no banco ainda.
- **Dizer:** "Aqui vivem as estações (bancadas da fábrica) e qual câmera está em cada uma. Os limiares da IA estão travados de propósito nesta fase — a calibração fina entra na próxima etapa."

### 4. Retrabalho (abas Qualidade)
- **URL:** https://frontend-desenvolvimento-be93.up.railway.app/novo/quality
- **Mostrar:** Tela Qualidade com duas abas. Aba "Retrabalho": fila de peças que saíram com defeito, quando entraram, quanto tempo levaram, status (em retrabalho / concluído), botão "Concluir retrabalho". Aba "Câmeras das estações": lista de câmeras com status (ativa/inativa), teste de conexão com 5 passos.
- **Dizer:** "Quando uma peça dá não-conforme, entra nesta fila. O operador mexe nela, a gente aqui acompanha quanto tempo leva e quando acaba. A outra aba testa se cada câmera está respondendo."

---

## Kiosk
Fora desta demo. (app não existe ainda no código)

---

## NÃO PROMETER (setembro)

- Filtros avançados e drawer na Revisão (U5)
- Criação/edição de estações na Config (a tabela é só leitura)
- Export em lote na Gestão
- Start/stop de contagem na Carga
- Relatórios e treinamento de Qualidade (sem tela nova; o retrabalho JÁ é demoado no passo 4)
- Edição de câmera na visão Qualidade

---

**Congela terça 02/09 às 18h · dúvidas:** `tools/agent-driver/tasks/ESTADO-F5LEVE.md`
