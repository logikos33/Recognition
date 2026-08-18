# D-125 · Medição da razão de ausência é impossível esta rodada — duplamente bloqueada

**Seção:** Rodada 16/08 (tarde) — mineração DVR Lote 1: realidade do código e bloqueios · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

> ⚠️ Renumerado **D-114→D-125** na consolidação dos PRs #385/#386/#388 (D-114 já em uso na develop).

**16/08 · Claude · 📄 análise**

**Medido.** O bloco 4 pressupõe a "tela forçando estado por EPI" — mas **D-108 não está implementado**
(`SearchFindingsPanel.tsx:44` ainda é por-caixa; foi só decisão). E o export **inclui** hoje
`curation_status='duvida'` ("não sei") no pool — só `'excluida'` é filtrada (`versioning_v2.py:18-19,80-97`),
então o **passo 4 do percurso ("não sei não vai pro dataset") é FALSO hoje**. A razão ausência÷recorte exige
recortes reais (bloqueados, D-113) **e** a tela de veredito (inexistente) → não medível. Projeção só como
fórmula no doc §3 (⛔ não é medição).

**Veredito: registrar a impossibilidade.** O ~209 do dry-run contava só o já-anotado, não o potencial.
