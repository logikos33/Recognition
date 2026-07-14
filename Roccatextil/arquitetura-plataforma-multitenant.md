# Arquitetura da Plataforma — Multi-login, Limites por Cliente e Plug-and-Play

**Pesquisa + recomendação** · 11/06/2026 · Visão: cliente acessa web, conecta câmeras e PC próprio, treina e opera sozinho
**Premissa de custo:** time pequeno, custo marginal por cliente ≈ zero, expandir só quando o gatilho disparar

---

## 1. Multi-login e limitação por cliente

### Modelo recomendado
- **Identidade única por usuário + tabela `memberships`** (usuário ↔ tenant ↔ papel). `tenant_id` e papel viram claims no JWT no login. RBAC por tenant (admin do cliente, gestor, operador, leitura).
- **Limite de assentos (seats):** contagem em `memberships` por tenant; convite bloqueado quando `count >= plano.seats`. É o padrão B2B mais simples e auditável.
- **Sessões concorrentes:** política "última sessão ganha" (login novo derruba o anterior) via tabela de sessões ativas + invalidação de refresh token — mata compartilhamento de senha sem falso positivo.
- **Dashboard de assentos para o admin do tenant** + grace period antes de bloquear (reduz atrito comercial).

### Provedor de auth — comparativo

| Opção | Custo | Veredicto |
|---|---|---|
| **Supabase Auth + RLS + claims** | Free até 50k MAU; o mais barato | ✅ **Recomendado** — enforcement de seats é nosso (trigger), mas é trivial |
| Clerk | Free 10k MAU; seats/billing prontos | Atalho se quisermos billing por assento sem código; ~US$0,02/MAU depois |
| Auth0 | Escala caro (~US$0,07/MAU; B2B em planos altos) | ❌ Não compensa pro nosso porte |
| Keycloak self-host | Grátis + VPS | Só se exigirem on-premise; custo é manutenção |

### Isolamento de dados — atenção ao nosso schema-per-tenant
A pesquisa aponta que **schema-per-tenant (nosso modelo atual) funciona bem até dezenas de tenants, mas degrada com centenas** (catálogo do Postgres incha, migração vira N execuções por deploy, connection pool sofre).

- **Agora (<50 clientes):** manter schema-per-tenant — já existe e o isolamento é forte. Não migrar nada.
- **Gatilho de mudança:** quando passar de ~50 tenants OU o tempo de migração por deploy incomodar → novos tenants nascem em **shared schema + RLS**; schema dedicado vira tier premium ("isolamento dedicado") cobrado à parte.
- Cliente enterprise com exigência contratual → database dedicado (cobrar como add-on).

## 2. Requisições como plataforma (API)

- **Rate limit por tenant no middleware da própria API** (token bucket em Redis/Postgres, chave = tenant_id, limites lidos da tabela de planos). Zero infra nova — Kong/gateway dedicado só quando houver API pública para terceiros.
- **Metering desde o dia 1:** tabela de eventos de uso (sessões processadas, streams ativos, chamadas de API, GB de evidência) por tenant — é o que permite cobrar por uso depois e identificar "noisy neighbor".
- **Edge → nuvem sempre outbound** (WebSocket/MQTT do agente para o backend): nenhuma porta aberta no cliente, atravessa firewall corporativo sem conversa com TI deles.

## 3. Plug-and-play: o cliente se instala sozinho

### O fluxo-alvo (validado pelo mercado — referência mais próxima: Lumeo)

1. **Cadastro web** → cria tenant, plano define seats/câmeras
2. **Conectar o computador:** web app gera **claim code** (código curto/QR); cliente roda instalador (`curl | bash` ou imagem pronta) no PC/Jetson dele; agente troca o código por credencial de device e aparece "online" na web — padrão Balena/Viam/Lumeo
3. **Câmeras descobertas automaticamente:** o agente roda **descoberta ONVIF** (multicast WS-Discovery + netscan na faixa de IP informada) na LAN do cliente e lista as câmeras na web; cliente informa usuário/senha da câmera no wizard; sem ONVIF → colar URL RTSP manual
4. **Workflow guiado:** desenhar a linha/zona de contagem sobre o preview da câmera (já temos o editor de cenários — task 023), escolher o que contar, threshold
5. **Treino do modelo pelo cliente:** upload/captura de imagens → anotação assistida → treino → deploy no device dele
6. **Operação:** dashboard, sessões, evidências — tudo no tenant dele

### Decisões técnicas e custo-benefício

| Peça | Recomendação | Prós | Contras |
|---|---|---|---|
| **Agente edge** | Docker Compose + agente próprio com claim code (DIY, padrão Balena/Viam sem o custo) | Custo por device ≈ R$ 0; controle total; já temos stack de deploy | Manter o agente e canal de update é nosso (usar Mender open source ou Watchtower p/ OTA) |
| Alternativa: Balena | Frota gerenciada pronta, ótima DX em Jetson | 10 devices grátis | ~US$159/mês a partir de 30 devices + lock-in no balenaOS |
| **Descoberta de câmeras** | ONVIF no agente (multicast + netscan por CIDR) | Funciona offline, na LAN do cliente | Não atravessa VLAN (wizard pede a faixa de IP); câmera sem ONVIF = RTSP manual |
| **Treino self-service** | Fase 1: pipeline próprio assistido (nosso time treina com 1 clique). Fase 2: **API do Roboflow embutida na nossa UI** (white-label via API) | Roboflow Core ~US$79/mês resolve anotação+treino sem construirmos AutoML | Deploy edge comercial white-label exige plano Enterprise — negociar quando chegar a hora |
| **Acesso remoto p/ suporte** | Tailscale (free até 3 users) ou Headscale self-host | Manutenção nos Jetsons sem abrir porta | Só para suporte; operação normal não depende de túnel |

### O que NÃO fazer agora
- Não construir AutoML próprio (Vertex custa US$3,46/node-hora e exige UX inteira; Roboflow via API entrega 90% disso)
- Não adotar gateway de API dedicado (Kong) antes de existir API pública
- Não prometer "treina sozinho" no contrato da Rocabella — o modelo de rolo da Fase 1 é treinado por nós (CD-04); o self-service é evolução da plataforma

## 4. Gatilhos de expansão (quando investir em cada etapa)

| Estágio | Clientes | O que construir | Custo novo |
|---|---|---|---|
| **Agora (Rocabella)** | 1-3 | Seats + RBAC + sessões concorrentes; metering; agente com claim code em versão interna (NÓS instalamos usando ele — vira dogfooding do futuro self-service) | ~R$ 0/mês |
| **Tração** | 3-10 | Descoberta ONVIF no wizard; onboarding guiado da câmera→linha→operação; Tailscale/Headscale para suporte | ~R$ 0-50/mês |
| **Escala inicial** | 10-30 | Treino via Roboflow API embutido; billing automatizado (assinatura + assento extra); status page e alertas de frota | ~US$ 80-200/mês |
| **Plataforma** | 30-50+ | Decisão RLS para novos tenants; NOC multi-site (já previsto na Fase 3 do produto); white-label completo; avaliar gateway | conforme receita |

**Regra de ouro:** cada estágio só começa quando o anterior doer de verdade — o claim code é a exceção (construir já, porque nós mesmos seremos os primeiros usuários na instalação da Rocabella, e o esforço vira ativo do self-service depois).

## 5. Modelo de cobrança da plataforma (benchmark)

Mercado de visão SaaS precifica **por câmera/mês** (Eagle Eye ~US$5-30/câmera/mês; Verkada ~US$12-42/câmera/mês via licença anual), com tiers por retenção de vídeo e features de IA, e assentos inclusos por plano.

**Sugestão:** R$/câmera/mês em 2-3 tiers (retenção de evidência + recursos), seats inclusos por tier (ex.: 5/15/ilimitado) + assento extra. O contrato Rocabella (R$ 4.500/mês ÷ 12 câmeras = R$ 375/câmera/mês com tudo incluso) já fica coerente com a régua internacional para um plano full-service com hardware.

---

*Fontes principais: [Supabase pricing](https://supabase.com/pricing) · [Clerk seat plans](https://clerk.com/docs/guides/billing/seat-limit-plans) · [Auth0 entity limits](https://auth0.com/docs/troubleshoot/customer-support/operational-policies/entity-limit-policy) · [Postgres multi-tenancy (PlanetScale)](https://planetscale.com/blog/approaches-to-tenancy-in-postgres) · [RLS multi-tenant (AWS)](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/) · [Kong vs Traefik](https://ohmyops.dev/guides/api-gateway-kong-vs-traefik/) · [Balena pricing](https://www.balena.io/pricing) · [Viam](https://docs.viam.com/) · [Lumeo gateway/câmeras](https://docs.lumeo.com/docs/gateway) · [Frigate/ONVIF](https://docs.frigate.video/configuration/cameras/) · [Roboflow pricing](https://roboflow.com/pricing) · [Edge Impulse white label](https://www.edgeimpulse.com/pricing) · [Tailscale pricing](https://tailscale.com/pricing) · [Eagle Eye pricing](https://getsafeandsound.com/blog/eagle-eye-networks-pricing/) · [Verkada (Vendr)](https://www.vendr.com/marketplace/verkada)*
