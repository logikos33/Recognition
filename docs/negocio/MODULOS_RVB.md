# Módulos RVB — mapa canônico (não esquecer nenhum)

> Fonte de verdade dos módulos ativos da RVB. Cada câmera tem um `active_module`; o loop **coletar → anotar →
> treinar → atribuir por câmera** roda por módulo, com pools/metas/anotação/ponto-focal **separados**.

## 1. EPI / Segurança — âncora (piloto atual: 1 câmera instalada)
- **Reconhecer:** **protetor auricular · luvas · óculos de proteção** (+ **pessoa**, que vem do gatilho de coleta).
  *(NÃO é capacete/colete — o default genérico do sistema está errado para esta operação.)*
- **Ponto focal:** Paulo (segurança).
- **✅ Protetor auricular — RESOLVIDO (Vitor, 2026-07-31): a classe é TREINÁVEL.** A RVB usa os **dois** tipos, e a
  câmera está **posicionada em ângulo que pega o protetor**:
  - **Concha/abafador** → anotar **a concha** sobre a orelha.
  - **Plug de inserção** → o plug em si é invisível, mas tem **cordão**, e **o cordão é treinável** → anotar **o cordão**.
  > ⚠️ **Regra de anotação (crítica):** no tipo plug o alvo é o **cordão**, não o plug. Se cada anotador marcar uma
  > coisa diferente, o modelo aprende ruído. Isto vai no guia de anotação.
- **Complexidade: MÉDIA-ALTA.** Itens **pequenos e sensíveis a ângulo/oclusão** (cabeça/rosto/mãos) — exige boa
  resolução na cabeça e nas mãos. Bootstrap PPE público ajuda pouco no protetor auricular.
- **Classe rara:** violação (sem o EPI) — **fácil de encenar** (atravessar sem o item, de propósito).
- **✅ CLASSES SÃO POR ZONA/CÂMERA — não globais do módulo (Vitor, 2026-07-31).** Cada zona tem sua exigência de
  EPI; **nem toda zona exige todos os itens**. Separar duas coisas:
  - **O que o modelo DETECTA** → um modelo só, treinado com todas as classes (protetor, óculos, luvas, capacete…).
  - **O que é EXIGIDO onde** → **regra por zona/câmera**. A mesma detecção alimenta regras diferentes.
  Consequência: adicionar zona nova é **configuração**, não retreino. E cada câmera tem seu **enquadramento ótimo**
  (itens de cabeça pedem enquadramento diferente de itens de mão).
- **Plano de câmeras (inicial):** câmera 1 → **protetor auricular + óculos** (cabeça). Depois, embarque de câmera
  específica para **luvas** (mãos). Capacete e demais: a definir por zona.
- **✅ Modelagem de classes — DECIDIDO (Vitor, 2026-07-31): SÓ CLASSES POSITIVAS.** As classes são
  `protetor auricular` · `luvas` · `óculos` · `pessoa`. **NÃO** criar classes `no_*` — a **ausência vira regra**
  (pessoa detectada sem o item dentro da bbox = violação). Menos anotação, mais flexível.
- **✅ Limpeza — DECIDIDO:** **desabilitar `helmet` e `vest`** no tenant da RVB (não usam; só poluem a tela do anotador).

## 2. Qualidade — piloto do Jonas (arranca quando as câmeras da linha subirem)
- **Reconhecer:** tipos de defeito no **anel** (conforme × não conforme).
- **Ponto focal:** Jonas. **Integra com o Wiser** (contexto de produção; ponto focal Alexandre).
- **Complexidade: ALTA.** Client-specific, do zero; defeito é raro → **encenar lote NOK**.

## 3. Estacionamento / Pátio
- **Reconhecer:** **passagem de pessoas e carros** + **atividades suspeitas**.
- **Ponto focal:** *a definir.*
- **Complexidade: MISTA.** Pessoa/carro = detecção padrão (bootstrap COCO). **Atividade suspeita = detecção de
  EVENTO/comportamento** (zona restrita, permanência, horário) — bloco à parte, e exige **definir "o que é
  suspeito"** com a RVB antes.

## Regra comum
3 módulos = 3 trilhas do mesmo loop. Não confundir pools nem pontos focais.
**Prioridade atual: EPI** (1 câmera). Qualidade e Estacionamento entram conforme câmeras/definições.
