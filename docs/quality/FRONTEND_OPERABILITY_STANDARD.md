# Padrão de Operabilidade pelo Frontend (regra para TODA funcionalidade)

**Data:** 2026-06-24 · **Regra inegociável a partir de agora.**

## Princípio
Nenhuma funcionalidade está "pronta" se precisa de código/script/SQL para ser operada. **Tudo que
envolve a plataforma tem que ser feito NA plataforma** (é um SaaS — auto-administrável, ver
AUTOADMIN_STUDY.md). Se para usar a feature o usuário teria que rodar um `.py` ou editar um arquivo,
a feature está **incompleta**, não importa se o backend funciona.

## O que muda no jeito de especificar
Toda spec de feature (task) DEVE incluir, ANTES de construir, o **Contrato de Operabilidade**:

1. **Entradas que o usuário fornece pela UI** — cada campo, com: tipo, validação, obrigatório?, valor
   default, e ONDE na tela fica. Ex.: chave de API, nº de câmeras, limiar, linha de cruzamento, classes.
2. **Segredos/credenciais** — nunca digitados a cada uso: vão numa área de **Configurações/Integrações**
   (cifrados), reaproveitados. (Ex.: chave da Vast, credenciais de câmera, tokens.)
3. **Ações** — botões/fluxos que disparam o backend (start/stop/salvar/testar), com estados
   (loading/erro/sucesso) e feedback ao vivo quando aplicável.
4. **Configuração visual quando o domínio pede** — ex.: desenhar a **linha de cruzamento** pra contar,
   marcar **zona/ROI**, escolher **classes a detectar**, definir dia/noite. Não pode ser JSON na mão.
5. **Endpoint(s) de backend** que cada entrada/ação chama, e o shape esperado.
6. **Papel/permissão** (role) que vê/usa cada campo.

**Definition of Done (adição):** uma feature só fecha se um operador consegue executá-la de ponta a
ponta **pela UI**, sem terminal, com todas as entradas acima presentes e validadas. PR sem o Contrato
de Operabilidade atendido = não fecha.

## Exemplos concretos (o que faltava)
- **Console de teste (task-056):** faltava onde digitar a chave da Vast (→ Configurações/Integrações,
  cifrada), o seletor de nº de câmeras, e a config do modelo. Corrigido na task.
- **Criar/configurar modelo:** precisa de uma tela onde o usuário escolhe o que o modelo faz —
  **linha de cruzamento pra contagem**, **classes/objetos a reconhecer**, **zona/ROI**, limiares. (O
  editor visual de cenário existe — task-023/024 — mas precisa estar surfaçado e completo no fluxo de
  criação de modelo. A auditoria confirma.)

## Aplicação
- **Retroativo:** auditoria completa frontend↔backend (task-057) — o que existe no backend/código mas
  não tem UI, o que a UI chama e não existe, e reorganização de IA/UX do painel admin.
- **Daqui pra frente:** toda task nova nasce com o Contrato de Operabilidade preenchido; sem ele, não
  entra na fila.
