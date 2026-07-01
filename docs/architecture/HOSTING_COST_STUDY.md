# Estudo de Hospedagem e Custo — Railway × AWS × GCP × VPS (2 ambientes)

**Data:** 2026-06-24 · ⚠️ valores são estimativas de mercado (2026) pra dimensionar decisão, não cotação.

## Contexto que muda tudo
O **processamento pesado (inferência/GPU) roda no EDGE (Jetson)**, não na nuvem. E o treino roda na
**Vast.ai** (à parte). Então o footprint de NUVEM é LEVE: API Flask + Postgres + Redis + workers
Celery + frontend + WebSocket. Storage de evidência já é **Cloudflare R2** (sem egress — manter).
Ou seja: a decisão de nuvem é sobre rodar um web app + DB + Redis em **2 ambientes** (validação +
produção), não uma stack GPU cara.

## Opções (estimativa POR AMBIENTE — web+worker+Postgres+Redis+frontend)
| Provedor | Custo/ambiente (est.) | Esforço de ops | Observação |
|---|---|---|---|
| **Railway** (atual) | ~US$ 50–120/mês (usage-based) | **~zero** | ~2x AWS por unidade, mas DX excelente; dev/staging com sleep barateia |
| **AWS** (ECS/Fargate + RDS + ElastiCache) | ~US$ 50–80 otimizado · US$ 150–200 naive | **alto** | mais barato em tráfego constante/escala, mas exige competência DevOps |
| **GCP** (Cloud Run + Cloud SQL + Memorystore) | similar ao AWS | médio-alto | Cloud Run bom pra web; Cloud SQL/Memorystore custam parecido |
| **VPS Hetzner** (self-host) | ~€6–30/mês raw | **muito alto** | 70–90% mais barato, MAS você gerencia Postgres/backup/HA/segurança/PgBouncer — tempo de engenheiro come a economia |

**2 ambientes (validação + produção):**
- Railway: ~US$ 100–240/mês (dev/staging dormindo baixa isso). É o que temos hoje (~US$ 200 a plataforma toda).
- AWS otimizado: ~US$ 100–160/mês + tempo de ops.
- Hetzner: ~€30–60/mês raw + bastante tempo de ops (você monta HA/backup/PgBouncer na mão).

## Trade-off central
- **Railway** = paga um prêmio (~2x) pra ter **zero ops** e velocidade. Como o footprint de nuvem é
  leve, o prêmio em valor absoluto é pequeno enquanto há poucos tenants.
- **AWS/GCP** = ~metade do custo em escala, porém complexidade e tempo de DevOps reais.
- **Hetzner/VPS** = o mais barato de longe, mas você vira o time de infra (backup, HA, segurança,
  PgBouncer, monitoramento) — só compensa com competência DevOps dedicada.

## Recomendação por fase
1. **AGORA (RVB + primeiros clientes):** ficar no **Railway**. Velocidade e zero-ops valem mais que a
   economia, e como a nuvem é leve o custo absoluto é modesto. Estrutura: **dev (develop) + staging
   (validação) + produção** — dev/staging com sleep. Já resolve os 2 (na verdade 3) ambientes.
2. **AO ESCALAR (dezenas de tenants, custo pesa):** migrar o compute pra **AWS** (gerenciado, escala,
   ~metade do custo) OU **Hetzner** (mais barato, exige DevOps + o PgBouncer/HA que a task-053 já
   prevê). Manter **Cloudflare R2** em qualquer cenário (egress zero).
3. **Sweet spot híbrido:** R2 (Cloudflare) + compute onde fizer sentido; migrar só quando o gatilho bater.

## Gatilho de migração (quando sair do Railway)
Quando `conta_Railway_mensal × 12` > (custo AWS/Hetzner **+** tempo de DevOps pra operar). Como a
nuvem é leve (edge tira a GPU), esse ponto chega com **N tenants (dezenas)**, não na RVB. Reavaliar a
cada marco de crescimento; a migração é contida (é web+DB+Redis, sem GPU no cloud).

## Nota
A task-053 (PgBouncer + sizing) é pré-requisito de escala em QUALQUER provedor — no Railway hoje, e
mais ainda no dia de um AWS/Hetzner self-managed. Fazer isso primeiro deixa a migração futura simples.

Fontes no fim do resumo em chat.
