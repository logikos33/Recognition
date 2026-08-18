# D-062 · 🔴 O PRIMEIRO MODELO EPI É DE CURTA DISTÂNCIA — NÃO é produto pronto

**Seção:** Rodada 5 — Triagem dos 679 frames RVB (05/08 · Claude) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**05/08 · Claude**

A triagem descarta os frames de longe (pessoa < 80 px) e sobra o de perto. **Um
dataset de closes ensina closes.** O primeiro modelo vai funcionar **só de
perto** e vai falhar em pessoa ao fundo/no vão do portão — exatamente os frames
descartados.

Isto **NÃO invalida a volta 1**: ela existe para **provar que a corrente
conecta** (coleta → triagem → anotação → treino → deploy → detecção). Mas está
registrado **em letras grandes**: quando a primeira caixa aparecer na tela do
cliente, é um modelo de curta distância — **não confundir com produto pronto**.
Cobertura de distância é trabalho de ondas seguintes (mais câmeras/posições,
mais dado de longe anotável, ou câmeras reposicionadas).
