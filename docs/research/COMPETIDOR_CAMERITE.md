# Análise de Competidor — Camerite

> VSaaS brasileiro (Joinville/SC, CNPJ 05.818.541/0001-45). Posicionamento: "a maior rede de
> câmeras colaborativas e inteligentes do Brasil" / "transformando imagens em informação".
> Fonte: camerite.com (site Framer), buscas web, jun/2026. Coletado para mapear o que oferecem
> e extrair boas práticas para a Recognition.

---

## 1. O que eles vendem (catálogo completo)

Site organizado em 5 "soluções":

| Solução | O que é |
|---------|---------|
| **Conexão e Nuvem** | Onboarding de câmeras de "dezenas de fabricantes" via **RTSP, RTMP e P2P**. Storage em nuvem escalável (HD/FullHD/4K). |
| **Plataforma e Aplicativo** | Web + app mobile. Acesso remoto, multi-câmera, multiusuário. |
| **Monitoramento e Segurança** | Alertas inteligentes em tempo real, monitoramento ativo. |
| **Analítico e Investigativo** | IA: reconhecimento facial, **leitura de placas (LPR)**, detecção de pessoas/objetos, mapas de calor, busca investigativa em gravações. |
| **Rede Colaborativa** | Câmeras de vários donos compartilhadas numa rede (bairro/cidade segura). Diferencial de marketing deles. |

**Armazenamento em nuvem (tiers):** 1, 3, 7, 15, 30 dias **ou até 1 ano** — escala conforme nº de câmeras e complexidade. Criptografado. Vendido como o "core" que sustenta tudo (sem DVR local, sem risco de furto/avaria do gravador).

**Modelos de negócio:**
- **White Label** — revenda da plataforma com a identidade visual do parceiro, mensalidade, "sem comprar equipamento". (página `contato.camerite.com/wl-camerite` — login-walled).
- **Franquia** ("Seja Franqueado") — expansão por franqueados regionais.
- Verticais atendidas: residências, condomínios, varejo, indústria, logística, escolas, setor público, etc.

---

## 2. Arquitetura técnica (o que dá pra inferir)

O site é marketing puro (Framer) — sem docs técnicos públicos. Mas o que está exposto define o modelo:

- **100% nuvem, sem edge.** Toda a IA roda no datacenter deles. A câmera só **empurra o stream** (RTSP/RTMP/P2P) pra nuvem. Isso é dito explicitamente: *"toda a tecnologia está na nuvem"*, *"você não depende de estruturas complexas"*.
- **Ingestão multi-protocolo / multi-marca.** RTSP (câmera IP padrão), RTMP (push) e **P2P** (câmera atrás de NAT sem abrir porta — onboarding fácil pra leigo). Esse é o pulo do gato comercial deles: instalador não precisa de IP fixo nem port-forward.
- **Dependência de imagem em alta qualidade.** Eles avisam que facial/LPR/heatmap *"precisam de imagens em alta qualidade, tanto na câmera quanto no armazenamento"* → a IA na nuvem consome o stream principal em alta resolução. Custo de banda/storage é deles (e do cliente, na conta).
- **Sem menção a on-prem / appliance.** Não há Jetson, NVR inteligente, nem processamento local. Tudo é OPEX de nuvem.

**Trade-off central deles vs. nós:** Camerite = tudo-nuvem (simples de instalar, mas paga banda/GPU de cloud por câmera, e depende de upload bom do cliente). Recognition = **edge (Jetson) + nuvem** (mais barato em escala de stream, roda sem internet, mas exige hardware no local).

---

## 3. Boas práticas para a Recognition adotar

### Adotar logo (alto valor, baixo custo)
1. **Onboarding de câmera multi-marca sem dor.** Hoje validamos RTSP. Camerite ganha mercado com **P2P** (câmera atrás de NAT, sem IP fixo). Vale um wizard de "adicionar câmera" no front que: detecta marca, sugere URL de substream, e tem caminho pra câmera sem IP público (relay/túnel). Reduz custo de instalação — exatamente o gargalo das 28 câmeras da RVB.
2. **Tiers de retenção configuráveis por câmera/tenant** (1/7/30/90 dias…). Já temos R2; falta expor o tier como config de front + política de expiração. Vira linha de receita e argumento LGPD ("guarda só o necessário").
3. **White-label como produto, não como favor.** Eles vendem rebrand (logo/cores/domínio) como SKU. Já está no nosso roadmap — Camerite confirma que é monetizável. Priorizar: tema por tenant + domínio próprio (`cliente.logikosvision.com.br`).
4. **Busca investigativa em gravação.** "Me mostre todos os eventos de placa X / pessoa sem capacete entre 14h-16h." Já temos alerts + frames no R2; falta a camada de busca/timeline. Alto valor pra gestor.

### Diferenciação consciente (onde NÃO copiar)
5. **Manter o edge.** A 28+ câmeras, tudo-nuvem fica caro em banda/GPU. Nosso Jetson é vantagem de custo e funciona sem internet — é um diferencial, não uma desvantagem. Vender isso.
6. **Foco vertical (EPI/qualidade/contagem industrial) vs. o "genérico segurança" deles.** Camerite é amplo/raso (facial, placa, heatmap pra "segurança"). Recognition é fundo num problema (compliance de EPI, contagem de carga/descarga) com ROI medível pro gestor. Não tentar ser "câmera colaborativa de bairro".
7. **Modelo colaborativo / franquia** é interessante a longo prazo, mas é distração agora. Anotar, não perseguir.

### Recursos deles que viram ideias de módulo
- **LPR (leitura de placas)** — encaixa direto no módulo de carga/descarga (já temos classe `plate`): identificar o caminhão na baia automaticamente.
- **Mapas de calor** — feature de dashboard barata sobre dados que já coletamos (densidade de detecções por zona).
- **Detecção de pessoa/objeto genérica** — já temos via YOLO; expor como "módulo segurança" leve é upsell fácil pro mesmo cliente industrial.

---

## 4. Resumo executivo (1 parágrafo)

Camerite é um VSaaS 100% nuvem, multi-marca, que vence pela **facilidade de onboarding** (P2P, sem IP fixo), **storage em nuvem como core** (tiers até 1 ano), um **catálogo amplo de IA de segurança** (facial, LPR, heatmap, detecção) e um **go-to-market de white-label + franquia**. A Recognition não deve competir na amplitude rasa deles; deve copiar o que reduz fricção de venda (**onboarding fácil de câmera, retenção configurável, white-label como SKU, busca investigativa**) e defender o que eles não têm: **processamento no edge** (custo e resiliência em escala de 28+ câmeras) e **profundidade vertical com ROI medível** (EPI, contagem de carga/descarga).
