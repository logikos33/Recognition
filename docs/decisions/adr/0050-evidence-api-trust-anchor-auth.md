# ADR-0050 — Trust-anchor RS256 invertido para autenticar chamadas cloud/local → edge (mini-API de evidência)

**Status:** Proposta · **Data:** 2026-07-15 · **Autores:** Vitor Emanuel (Logikos) + Claude Code (task-090)
**Relaciona:** ADR-0019 (device tokens RS256), ADR-0020 (MikroTik/WireGuard), ADR-0045 (evidência recorder-first)
**Escopo:** `services/edge-sync-agent/app/evidence_auth.py`, `evidence_api.py`

## Contexto

Task-090 precisa de uma mini-API HTTP nova, rodando no edge, que aceita requisições **de entrada** (inbound)
vindas de dois lugares: um cliente na LAN do site, e o cloud fazendo proxy de um pedido de usuário através do
túnel WireGuard (ADR-0020). Isso é o sentido **oposto** de tudo que já existe:

- ADR-0019 (device tokens): o **device** gera seu próprio par de chaves RSA, manda a chave pública pro cloud no
  enrollment, e a partir daí assina seus próprios JWTs com a chave privada (que nunca sai do device). O cloud
  verifica usando a chave pública armazenada em `device_tokens.public_key_pem`
  (`services/api/app/core/device_auth.py::verify_device_token`). Isso autentica **edge → cloud**.
- Não existe, em lugar nenhum do repositório, um mecanismo pra autenticar **cloud/local → edge**. O
  `edge_commands` (poll de comandos) é pull-based — o device sempre pergunta, nunca é chamado. A "Mirror API"
  descrita em `AGENT.md`/`SDD.md` do `edge-sync-agent` é um placeholder nunca implementado, e nem endereça auth
  (assume LAN = confiável, o que não é aceitável pra tráfego vindo do túnel também).

## Decisão

Reusar a **mesma família de mecanismo** do ADR-0019 (RS256, par assimétrico, chave privada nunca sai de quem
assina), só que **invertido**: um "trust anchor" cujo par de chaves é gerado e mantido pelo **cloud** (não pelo
device). A chave **privada** fica em secret do Railway (nunca chega ao edge). A chave **pública** é entregue ao
device no enrollment — mesmo canal e mesmo momento em que hoje o device manda sua própria chave pública pro
cloud — e fica guardada localmente no edge (ex.: `/run/secrets/evidence_trust_public_key.pem`, análogo ao
`DEVICE_TOKEN_PATH` já documentado em `AGENT.md`).

Com isso:
- O **cloud** (segurando a chave privada) é o único emissor de "evidence access tokens" — JWTs RS256 curtos,
  com claims `tenant_id`, `site_id`, `sub` (quem pediu: `"cloud-proxy"` ou identificador do operador/ferramenta
  local), `scopes` (`evidence:read`, `evidence:stream`), `iat`, `exp`.
- O **edge** só **verifica** — nunca assina — usando `TrustAnchor` (`evidence_auth.py`), que também checa que
  `tenant_id`/`site_id` do token batem com a identidade do próprio device (defesa em profundidade, mesmo padrão
  do claims-match em `device_auth.get_device_context`).
- **Local e remoto usam o MESMO tipo de token e o MESMO código de verificação.** A diferença entre "local" e
  "remoto" é só o caminho de rede pelo qual a requisição chegou (LAN direta vs. túnel WireGuard) — o
  `validate_bind_host()` garante que a API nunca escuta em `0.0.0.0`/`::` (nunca alcançável pela internet
  pública), então o próprio overlay/LAN já é o primeiro filtro; o JWT é a segunda camada.

**Nenhuma chave privada nova precisa existir no device** — o segredo mais sensível (a chave que autoriza acesso
à evidência) nunca deixa o cloud, ao contrário de uma alternativa onde o device assinaria tokens de terceiros.

## Fora do escopo desta ADR / desta task (090)

- **Endpoint de emissão no cloud** (`POST /api/v1/edge/evidence-tokens` ou similar) que mint o "evidence access
  token" a partir de uma sessão de usuário autenticada. Task-090 implementa só o **verificador** no edge; o
  emissor é trabalho futuro (não bloqueante — os testes de `evidence_auth.py`/`evidence_api.py` cobrem a
  verificação isoladamente, gerando tokens de teste com um par de chaves efêmero).
- **Distribuição da chave pública do trust anchor no fluxo de enrollment** (`services/api/app/core/device_auth.py`
  hoje só lida com a chave pública do device, não com entregar a chave pública do trust anchor pro device) —
  também trabalho futuro; documentado aqui pra não se perder.
- **Acesso local 100% offline indefinido**: o operador local precisa ter obtido um token do cloud em algum
  momento anterior (com conectividade) e cacheá-lo; não há hoje um segundo emissor local. Isso é aceitável pro
  MVP (mesma limitação de fundo do "dual mode" já documentado, ADR-0006) e fica como gap conhecido.

## Alternativas consideradas

- **Reusar a chave privada do próprio device** (o device assina um token pra si mesmo): não resolve o problema —
  quem precisa se autenticar é o CALLER (cloud/local), não o device; o device já confia em si mesmo por
  definição.
- **mTLS sobre o túnel WireGuard**: robusto, mas adiciona uma segunda PKI (certificados, rotação, distribuição)
  quando o objetivo era reusar a infra existente ao máximo. Anotado como possível endurecimento futuro, não
  necessário agora que o WireGuard já restringe quem alcança a porta.
- **JWT HS256 com segredo compartilhado**: mesmo problema estrutural do ADR-0019 já rejeitou pra device tokens —
  comprometer um segredo expõe todos os sites; RS256 assimétrico evita isso (a chave pública espalhada não serve
  pra forjar tokens).

## Consequências

**A favor:** reusa a disciplina de PKI já validada (chave privada nunca sai de quem assina, revogação via
rotação de chave, sem segredo compartilhado); local e remoto compartilham o mesmo código de verificação (menos
superfície pra divergir); nenhuma chave privada nova no device.
**Contra / trade-off:** a emissão (cloud-side) ainda não existe — até ela ser implementada, a mini-API só pode
ser testada com tokens gerados manualmente/em teste, não em um fluxo de usuário real ponta a ponta. Precisa de
um novo secret no Railway (chave privada do trust anchor) e de um novo passo no enrollment (entregar a chave
pública) — nenhum dos dois implementado nesta task.

## Sem validação em hardware real

Esta decisão e sua implementação (`services/edge-sync-agent/app/evidence_auth.py`) foram verificadas só com
testes automatizados (chaves RSA efêmeras geradas em teste, `services/edge-sync-agent/tests/test_evidence_auth.py`
e `test_evidence_api.py`). Não há Jetson nem gravador/NVR real disponível para validar o fluxo ponta a ponta —
isso fica para o go-live (task-097) e para quando a task-091 (ONVIF real) e a emissão cloud-side existirem.
