# ADR-0058 — Ciclo de vida da câmera + config de coleta entregue pela nuvem

**Status:** Proposta · **Data:** 2026-07-31 · **Autores:** Vitor Emanuel (Logikos)
**Relaciona:** ADR-0054/0055 (plano de controle: config cloud→edge por pull), ADR-0057 (autonomia do edge),
ADR-0004 (multi-tenant), `docs/FLYWHEEL_ANOTACAO_EPI.md` (o loop de anotação)
**Numeração:** ⚠️ confirmar que **0058** está livre na `develop` antes do merge (colisão de ADR já derrubou deploy).

## Contexto

Ao embarcar a **câmera 1 da RVB** desenhamos, na prática, o processo de **embarque de uma câmera nova**:
gatilho por pessoa → coleta de frames → anotação humana → dataset → treino → modelo. Funciona, mas hoje:

- A configuração de coleta (mapa de canais, limiar, burst, cooldown, meta de frames, módulo) vive no **`.env` do
  box**. Embarcar uma câmera = **SSH no Jetson e editar arquivo**.
- Não existe noção de **em que estágio** cada câmera está: "coletando pra treinar" e "operando com alerta" são
  estados diferentes e o sistema não os distingue.
- Isso não escala para as **~28 câmeras** da RVB nem para o próximo cliente, e contradiz a promessa central do
  produto: **controlar o Edge pelo front, sem tocar no código**.

Já existe o mecanismo certo e ocioso para isso: **`GET /api/v1/edge/config/poll`** (ADR-0054, Plano 1) — o device já
faz poll a cada ~45s, com versionamento e ETag/304.

## Decisão

**1. A câmera passa a ter um ESTÁGIO de ciclo de vida** (por câmera **e por módulo**, já que uma câmera pode servir
EPI e Qualidade):

| Estágio | O que acontece | Alerta? |
|---|---|---|
| `aprendendo` | coleta frames para treino (gatilho configurado); **sem inferência de produto** | não |
| `validando` | modelo treinado roda em **sombra** — infere e registra, mas não notifica; compara com o humano | não |
| `ativa` | operação real | **sim** |
| `pausada` | não coleta nem infere | não |

**2. A config de coleta é AUTORITATIVA NA NUVEM e entregue pelo `config/poll`.** Por câmera/módulo:
estágio · tipo de gatilho (`movimento` \| `pessoa` \| `agenda`) · parâmetros do gatilho (limiar, burst, cooldown) ·
meta de frames · resolução/substream de captura. O coletor **lê da config**, não do `.env`.
*(Isso encerra a dívida da config duplicada nuvem×box registrada no PR #236.)*

**3. O front ganha o painel de embarque:** lista de câmeras com estágio, **progresso da coleta** (frames coletados
× meta, **e contagem por classe**), e a ação de mover a câmera entre estágios. Embarcar câmera nova = **configurar
na tela**, não SSH.

**4. Segredo continua fora da config.** Credencial de gravador **não** trafega no `config/poll` — permanece cifrada
no cadastro e no `.env` do box (ADR-0057 / runbook de rotação). O poll carrega **comportamento**, não segredo.

## Alternativas rejeitadas

- **Manter no `.env` do box.** Simples hoje, insustentável em 28 câmeras/multi-site; exige SSH por mudança;
  contradiz a promessa de produto.
- **Canal novo só para config de coleta.** O `config/poll` já existe, já versiona e já roda — criar um sexto canal
  seria duplicação sem ganho.
- **Estágio global por site** (em vez de por câmera/módulo). Perde o caso real: câmeras diferentes em fases
  diferentes, e a mesma câmera aprendendo Qualidade enquanto já opera EPI.

## Consequências

**Positivas:** embarque de câmera vira operação de tela; o processo fica **repetível por cliente**; o painel mostra
quando o dataset está pronto pra treinar; encerra a config duplicada; usa canal já existente.

**Custos/riscos:** o coletor precisa aceitar config remota (mudança no edge); mudança de config em runtime precisa
ser segura (aplicar sem restart, manter última config boa se vier ruim — padrão do ADR-0054); e o estágio vira
contrato entre front, API e edge — precisa de migration aditiva.

## Sequenciamento (importante)

> **Provar uma vez antes de generalizar.** Primeiro fechar o loop **manualmente com a câmera 1** (missão em curso).
> Só depois transformar em configuração de sistema. Abstrair antes de funcionar é como se cria a abstração errada.

1. Loop provado ponta a ponta na câmera 1 (coleta → anotação → dataset).
2. **Migration aditiva:** estágio + config de coleta por câmera/módulo.
3. `config/poll` passa a carregar esses campos; coletor lê da config (com fallback pro `.env` durante a transição).
4. Painel de embarque no front (estágio + progresso por classe).
5. Embarcar a **2ª câmera inteiramente pela tela** — é o teste real de que virou processo, não procedimento.

## Em aberto
- Nomes finais dos estágios (aqui em PT; definir os valores canônicos no banco).
- O estágio `validando` (modelo em sombra) depende do elo **modelo→edge** (Plano 4), ainda ausente.
