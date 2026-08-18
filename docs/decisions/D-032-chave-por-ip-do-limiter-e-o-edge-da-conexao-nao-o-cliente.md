# D-032 · Chave por-IP do limiter é o edge da conexão, não o cliente real

**Seção:** Contrato e jurídico · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · ⏸ follow-up**

Ao validar o login no DEV: 15 requisições em conexões separadas não dispararam 429, mas 15 na mesma conexão
TCP dispararam (10×401→5×429). Causa: o limiter usa `request.remote_addr` (ProxyFix `x_for=1` = **último**
hop do X-Forwarded-For = IP do edge da Railway, que varia por conexão), enquanto o log do A6 usa o
**primeiro** hop (IP real do cliente). Um browser real (conexões persistentes) acumula como o RVB acumulou;
requisições espalhadas por muitas conexões escapam. Implicação: proteção anti-brute-force é mais fraca que o
pretendido, e o cenário "fábrica atrás de um NAT" é menos severo que o temido. Ajustar `x_for` exige análise
própria (profundidade real do proxy Railway × o trade-off do NAT) — não mexido nesta rodada.
