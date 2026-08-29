#!/usr/bin/env node
/**
 * Gera docs/migration/MANIFESTO-FRONT-ANTIGO.md a partir do REPOSITÓRIO.
 *
 * Pedido do Vitor (27/08): nada do front antigo é removido nesta rodada, mas
 * TUDO fica sinalizado para a etapa de remoção. Este manifesto é a lista, e é
 * GERADA — não escrita à mão, senão envelhece no primeiro PR.
 *
 * Status por arquivo:
 *   MIGRADO      — substituta existe E a paridade foi fechada; PODE ser removido
 *   SUBSTITUIDA  — substituta existe, mas a paridade NÃO fechou; NÃO pode ser
 *                  removido (a lista do que falta está em
 *                  docs/migration/PARIDADE-ANTIGO-VS-NOVO.md)
 *   PENDENTE     — ainda serve rota viva que a migração vai cobrir
 *   SEM-DESENHO  — serve rota que o handoff NÃO desenhou; fica até o design desenhar
 *   INFRA        — não é tela (api, hooks, tipos, tema); decisão caso a caso
 *
 * ⛔ A remoção só pode apagar MIGRADO. SUBSTITUIDA fica.
 */
import { readFileSync, writeFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));
const RAIZ = join(AQUI, "..");
const SRC = join(RAIZ, "src");
/**
 * Destino. `MANIFESTO_SAIDA` permite gerar para outro lugar — é o que o teste
 * de frescor usa para COMPARAR sem escrever no arquivo versionado.
 *
 * Sem isso o teste se auto-curava: falhava na primeira execução, consertava o
 * arquivo, e passava na segunda. Quem rodasse duas vezes via verde e commitava
 * um manifesto velho — foi assim que um manifesto desatualizado chegou ao CI.
 */
const SAIDA = process.env.MANIFESTO_SAIDA
  ? process.env.MANIFESTO_SAIDA
  : join(RAIZ, "..", "..", "docs", "migration", "MANIFESTO-FRONT-ANTIGO.md");

/** Rotas sem desenho no handoff — Fase 0 §3.2. Ficam vivas até o design desenhar. */
const SEM_DESENHO = [
  "ModuleSelectionPage", "CameraTriagePage", "EpiOperationsPage",
  "EpiScenarioEditorPage", "StreamHealthRedirect", "SitesHealthRedirect",
  "EpiSitesPage", "DashboardIntegradoPage", "InvestigationPage",
  "EdgeMonitoringGate",
];

const MARCA = "@migrado-para";

/**
 * Marca que o arquivo AINDA tem função que a substituta não faz.
 *
 * Sem esta distinção o manifesto dizia "MIGRADO = pode apagar" para 7 telas em
 * que a comparação função-a-função achou 22 perdas confirmadas. "Tem substituta"
 * e "pode ser apagado" não são a mesma coisa, e tratá-las como se fossem é o
 * caminho mais curto para apagar função que o cliente usa.
 */
const PARIDADE_ABERTA = "@paridade-pendente";

/**
 * O front NOVO. Não entra no manifesto: este documento é a lista do que SAI, e
 * `src/app/` é o que FICA. Sem este corte o gerador classificava `Shell.tsx`
 * como INFRA e o punha no inventário de remoção — quem lesse a lista na Fase 3
 * veria o front novo entre os candidatos a apagar.
 */
const FRONT_NOVO = "src/app/";

function varrer(dir, saida = []) {
  for (const nome of readdirSync(dir)) {
    const p = join(dir, nome);
    if (statSync(p).isDirectory()) {
      if (nome === "test" || nome === "__snapshots__") continue;
      varrer(p, saida);
    } else if (/\.(tsx?)$/.test(nome) && !nome.includes(".test.")) {
      saida.push(p);
    }
  }
  return saida;
}

const arquivos = varrer(SRC).filter(
  (p) => !relative(RAIZ, p).startsWith(FRONT_NOVO),
);
const linhas = arquivos.map((p) => {
  const rel = relative(RAIZ, p);
  const txt = readFileSync(p, "utf8");
  const migrado = txt.includes(MARCA);
  const nomeBase = rel.split("/").pop().replace(/\.tsx?$/, "");
  let status;
  if (migrado) status = txt.includes(PARIDADE_ABERTA) ? "SUBSTITUIDA" : "MIGRADO";
  else if (SEM_DESENHO.includes(nomeBase)) status = "SEM-DESENHO";
  else if (/(^|\/)(pages|modules)\//.test(rel)) status = "PENDENTE";
  else status = "INFRA";
  const destino = migrado ? (txt.match(/@migrado-para\s+(\S+)/) || [])[1] || "?" : "—";
  return { rel, status, destino, linhas: txt.split("\n").length };
});

const porStatus = linhas.reduce((a, l) => ((a[l.status] = (a[l.status] || 0) + 1), a), {});
const total = linhas.reduce((a, l) => a + l.linhas, 0);

const md = `# Manifesto do front antigo — o que sai, e quando

**Gerado por \`npm run manifesto\`.** Não editar à mão.

Pedido do Vitor (27/08): a migração roda com as rotas novas **coexistindo**, e
tudo do front antigo fica **sinalizado** para uma etapa de remoção própria,
depois que a migração inteira estiver feita.

| status | significado | pode remover? |
|---|---|---|
| \`MIGRADO\` | tem substituta E a paridade fechou (marcado com \`${MARCA}\`) | ✅ sim, na Fase 3 |
| \`SUBSTITUIDA\` | tem substituta, mas ela AINDA NÃO FAZ TUDO (\`${PARIDADE_ABERTA}\`) | ⛔ não — ver [PARIDADE-ANTIGO-VS-NOVO.md](./PARIDADE-ANTIGO-VS-NOVO.md) |
| \`PENDENTE\` | ainda serve rota viva que a migração vai cobrir | ⛔ não |
| \`SEM-DESENHO\` | serve rota que o handoff não desenhou (Fase 0 §3.2) | ⛔ não — espera o design |
| \`INFRA\` | não é tela (api, hooks, tipos, tema) | ⛔ caso a caso |

## Situação — ${arquivos.length} arquivos, ${total.toLocaleString("pt-BR")} linhas

| status | arquivos |
|---|---:|
${Object.entries(porStatus).sort((a, b) => b[1] - a[1]).map(([s, n]) => `| \`${s}\` | ${n} |`).join("\n")}

## Como marcar um arquivo como migrado

No topo do arquivo substituído:

\`\`\`ts
/** ${MARCA} src/app/epi/eventos/EventosPage.tsx — F3, PR #NNN */
\`\`\`

Rodar \`npm run manifesto\` no mesmo PR. **A Fase 3 só apaga \`MIGRADO\`** —
\`SUBSTITUIDA\` fica de pé até a paridade fechar. Ter substituta e poder ser
apagado não são a mesma coisa.

## Inventário

| arquivo | status | migrado para | linhas |
|---|---|---|---:|
${linhas.sort((a, b) => a.status.localeCompare(b.status) || a.rel.localeCompare(b.rel))
  .map((l) => `| \`${l.rel}\` | \`${l.status}\` | ${l.destino} | ${l.linhas} |`).join("\n")}
`;
writeFileSync(SAIDA, md);
console.log(`manifesto: ${arquivos.length} arquivos, ${total} linhas`);
for (const [s, n] of Object.entries(porStatus).sort((a, b) => b[1] - a[1])) {
  console.log(`  ${s.padEnd(14)}${n}`);
}
