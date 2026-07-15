# ADR-0051 — Cloud-only: trade-off de segurança de câmera e quando exige edge mínimo

**Status:** Aceito · **Data:** 2026-07-15 · **Autores:** Vitor Emanuel (Logikos) + Claude Code (task-094)
**Estende:** ADR-0046 (deployment modes configuráveis) · **Relaciona:** ADR-0020 (MikroTik/WireGuard),
ADR-0045 (evidência recorder-first), ADR-0028 (evidência cloud-first)
**Escopo:** documentação — nenhuma migration, nenhuma mudança de comportamento server-side nesta ADR

## Contexto

ADR-0046 define `cloud_only` como feature explícita para cliente sem edge, mas deixa em aberto: *"o design de
isolamento de câmera (lockout) pode exigir um edge mínimo — a decidir por cliente"*. A task-094 pediu para
investigar o que já existe (C-04) antes de construir qualquer coisa nova, e documentar essa decisão.

### O que já é o comportamento padrão hoje (investigado, não presumido)

1. **Caminho câmera→nuvem já é o default.** `stream_handlers.py::stream_info` retorna `stream_type="hls"`
   (nuvem) para toda câmera, e só muda para `"edge_hls"` quando a câmera pertence a um `edge_site` com
   `deployment_mode='edge'`. Tenant sem nenhum `edge_site`, ou com sites em `cloud`/`hybrid`, já opera 100%
   via nuvem sem nenhum código especial.
2. **Criação de câmera não exige site.** `POST /api/cameras` (`crud_handlers.py::create_camera`) só exige
   `name` e `host` no body — `site_id` não é campo obrigatório nem é lido no fluxo de criação. Um tenant nunca
   precisa cadastrar um `edge_site` para operar.
3. **O gate de evidência (task-092, `quality_clips.py::_should_upload_evidence_to_r2`) já é fail-safe para
   cloud-only.** Ordem de resolução: feature flag explícita → `edge_sites.deployment_mode` do tenant (upload
   desliga só se **algum** site estiver em `edge`) → **fail-safe: mantém upload pro R2** se não houver
   `edge_sites` cadastrado ou se qualquer leitura falhar. Ou seja, cloud-only nunca perde evidência por
   ausência de configuração.

Nenhum desses três pontos precisou de código novo nesta task — são o comportamento já existente, confirmado
por leitura de código (não por migration antiga/memória, C-04).

### O que estava de fato faltando

**Isolamento de câmera não é resolvido só por "estar na nuvem".** ADR-0020 (aceito, 2026-06-04) já estabelece
que câmeras Hikvision/Intelbras **nunca podem ser expostas diretamente à internet** — poucas tentativas de
autenticação incorreta (varredura por bots) acionam o lockout anti-brute-force do firmware, derrubando a
câmera. Isso vale **independente de existir ou não um edge Jetson fazendo inferência local** — é uma
propriedade da câmera, não do modo de deployment.

ADR-0020 já havia previsto a mitigação (`site_gateways`, MikroTik WireGuard hub-and-spoke) como camada de rede
padrão de **todo** site cliente, edge ou cloud-only — mas o texto desta task-094 pedia confirmação de que isso
está de fato implementado e não é só uma intenção de ADR. Confirmado:

- `infra/migrations/072_site_gateways.sql` cria `public.site_gateways` (`tenant_id`, `site_id`, `kind`
  default `'mikrotik'`, `wg_public_key`, `wg_endpoint`, `status`) — já existe, não é só design.
- `services/api/app/api/v1/cameras/probe_handler.py::probe_camera` já tem o parâmetro `is_behind_nat`: quando
  a câmera está atrás de NAT (o caso comum — cliente sem IP público na câmera), o probe direto é impossível e
  o endpoint consulta `_check_gateway_available()` (`SELECT ... FROM public.site_gateways ... WHERE status =
  'active'`), retornando ao frontend se o tenant já tem um gateway ativo ou se precisa configurar um.

**Isso já é o "edge mínimo" que faltava nomear.** Não é o Jetson (que faz inferência local) — é o MikroTik
(que só faz relay de rede). A infraestrutura de dados e o probe já existem; o gap era **não estar
documentado/nomeado** como parte do fluxo cloud-only (era tratado só como um detalhe do fluxo de probe de
câmera).

## Decisão

Formalizar três níveis de deployment, não dois, e documentar quando cada um se aplica:

| Nível | Hardware no site | Quem faz inferência | Isolamento de câmera |
|---|---|---|---|
| **Edge** | Jetson Orin NX + MikroTik | Local (DeepStream) | MikroTik relay, mesma topologia |
| **Cloud-only COM gateway** | Só MikroTik (sem Jetson) | Nuvem (RTSP via túnel WG) | MikroTik relay — câmera nunca exposta |
| **Cloud-only SEM gateway** | Nenhum | Nuvem (RTSP direto câmera→internet) | ⚠️ **Não recomendado em produção** |

- **Cloud-only COM gateway é o mínimo seguro recomendado** para qualquer cliente cujas câmeras estão atrás de
  NAT (a esmagadora maioria — câmera IP residencial/comercial típica não tem IP público). O MikroTik já é
  gerenciável pelo mesmo modelo de `site_gateways` usado no probe; falta apenas o fluxo de provisionamento
  ponta-a-ponta pelo front (fora do escopo desta task — ver "Timing" do ADR-0020, item 3).
- **Cloud-only SEM gateway só é aceitável quando a câmera já está numa rede que o cliente controla com
  isolamento equivalente** (ex.: câmera com IP público só acessível via firewall que já restringe a origem, ou
  ambiente de laboratório/demo). Isso **não é o caminho recomendado para produção** e deve ser tratado como
  exceção documentada por cliente, nunca como default. O `probe_camera` já reflete essa distinção via
  `is_behind_nat`/`gateway_available` — não introduzimos um novo gate técnico nesta ADR, apenas nomeamos a
  decisão que o código já expressa.
- **Não bloqueamos tecnicamente o modo "sem gateway"** nesta task — o objetivo era documentar o trade-off, não
  adicionar enforcement novo. Se o cliente RVB ou outro cliente futuro tentar operar cloud-only sem gateway em
  produção, isso deve ser sinalizado no onboarding comercial/checklist de go-live (fora do código), não
  travado silenciosamente pela API.

### `public.tenants.deployment_mode` — coluna morta, decisão de não usar

Investigado (C-04): `infra/migrations/067_site_id_attribution.sql` adiciona `public.tenants.deployment_mode`
(`TEXT NOT NULL DEFAULT 'cloud'`, mesmo `CHECK` de `edge_sites`). Busca completa em
`services/api/app` (excluindo testes) confirma que **nenhum código lê ou escreve essa coluna** — só
`edge_sites.deployment_mode` é usado (`stream_handlers.py`, `quality_clips.py`, `edge/routes.py`,
`EpiSitesPage.tsx` via task-093).

**Decisão: manter a coluna como está (default seguro, nunca lida), não wireá-la nesta task.** Razões:
- A fonte de verdade real e correta é **por site**, não por tenant — um tenant pode ter sites mistos (um
  edge, outro cloud-only), e é exatamente isso que a UI da task-093 (`EpiSitesPage`) já gerencia. Popular
  `tenants.deployment_mode` a partir de uma pergunta de onboarding ("seu site tem edge?") criaria uma
  **segunda fonte de verdade** dessincronizável da primeira (ex.: tenant marca `edge` no onboarding, depois
  muda o único site para `cloud` pela UI — a coluna do tenant ficaria mentindo).
- Nenhuma tela ou fluxo hoje precisa de uma resposta "sim/não" agregada por tenant — o gap real de UX
  (indicar ao admin que "tenant sem sites = já opera cloud-only") é resolvido computando ao vivo a partir de
  `edge_sites` (zero sites, ou nenhum em modo `edge`), não a partir da coluna do tenant. Essa é a mudança de
  UI feita nesta task (`EpiSitesPage.tsx`, estado vazio).
- Não construímos wizard de onboarding — não há evidência de que falte um; camera CRUD já funciona sem
  `site_id` (ponto 2 acima), então "não fazer nada" já é o fluxo cloud-only completo.

Se um caso de uso futuro precisar de fato de um modo agregado por tenant (ex.: billing, relatório comercial),
a coluna já existe com um default seguro (`'cloud'`) e pode ser adotada então — não precisa de nova migration
para isso, só passar a lê-la. Até lá, permanece documentada aqui como vestigial para não ser reinterpretada
como fonte de verdade por engano numa sessão futura (C-04).

## Consequências

**A favor:** nenhum código de produção mudou (zero risco de regressão); o trade-off de segurança fica
explícito e nomeado (3 níveis, não 2) em vez de implícito num parâmetro de probe; a UI passa a explicar ao
admin, no ponto exato onde ele notaria "não tem nada aqui" (`EpiSitesPage` vazio), que isso é esperado e é o
próprio modo cloud-only funcionando.
**Contra / trade-off:** o provisionamento ponta-a-ponta do MikroTik pelo front (mencionado no ADR-0020 como
"pós go-live") continua não implementado — esta ADR documenta que ele é o "edge mínimo" recomendado, mas não o
constrói. Cliente cloud-only sem gateway continua tecnicamente possível (não bloqueado pela API) — o controle
hoje é operacional/comercial, não técnico.

## Não implementado nesta task (fora de escopo, documentado para não se perder)

- Provisionamento self-service do MikroTik pelo front (chaves WG, config via RouterOS REST API) — previsto no
  ADR-0020, ainda não construído.
- Enforcement técnico que bloqueie/avise no probe quando `is_behind_nat=true` e `gateway_available=false` além
  do aviso textual já retornado (`"Configure um gateway de site para acesso remoto."`) — poderia evoluir para
  um warning mais forte na UI de cadastro de câmera; não fizemos isso aqui para não expandir escopo sem
  evidência de que os clientes atuais precisam.
