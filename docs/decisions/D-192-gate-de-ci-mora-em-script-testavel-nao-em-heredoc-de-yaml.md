# D-192 · Gate de CI mora em script testável, ⛔ não em heredoc de YAML

**Data:** 2026-09-05 · **Status:** ✅ vigente

Dois PRs consertaram a mesma #421 (`security-scan` verde com astro vulnerável). O da onda 1,
já na develop, escreveu a política como **heredoc de 55 linhas dentro do `security-scan.yml`**.
O #568, aberto seis dias antes, escreveu como script separado com suíte de testes — semântica
mais fraca, fatoração melhor.

**Decisão:** lógica de gate de CI vive em `scripts/ci/*.py`, com teste em
`services/api/tests/unit/ci/`. O workflow chama; ⛔ não decide. Consolidado em #742; o #568 foi
fechado com o registro do que foi portado e do que não foi.

**Por quê:** heredoc em YAML ⛔ não roda em pytest. São linhas de política de segurança que
nenhum teste pode exercitar — e um gate sem teste é a próxima #421, porque a única forma de
descobrir que ele parou de reprovar é ele deixar de reprovar. Efeito colateral medido: o log do
CI imprimia as 55 linhas do heredoc antes de rodar, enterrando as duas linhas de veredito.

**Consequência de desenho:** a função de avaliação recebe `hoje` como argumento em vez de chamar
`date.today()` lá dentro. É o que torna "allowlist vencida reprova" um teste de verdade em vez de
um comentário otimista — sem congelar relógio e sem esperar outubro.

**Como consolidar sem trocar um defeito por outro:** rodar as duas implementações lado a lado
sobre o mesmo conjunto de entradas e exigir **zero divergência** de código de saída, antes de
apagar a antiga. Feito em #742 com 8 casos. Cheiro de equivalência ⛔ não é prova de equivalência.

**Descartado:** manter os dois gates (o defeito que a consolidação existe para não criar);
mergear o #568 (o diff dele foi escrito contra um `security-scan.yml` que já não existe, e
traria de volta o `continue-on-error` já removido); allowlist em `.json` por app (um arquivo a
mais em `apps/` para colidir com quem mexe no frontend, sem ganho — a política é revisada junto
com o workflow).
