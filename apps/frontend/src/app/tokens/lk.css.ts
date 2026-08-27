/**
 * Tokens Logikos Vision — o contrato de cor, tipografia e medida.
 *
 * ⛔ NUNCA hex solto em componente. `npm run lint:hex` varre e reprova.
 *
 * Regras que estes tokens carregam (Manual Logikos / README do handoff):
 *
 *  · CIANO É SÓ INTERATIVO — ativo, foco, primário, playhead. ≤10% da tela,
 *    NUNCA como fundo. É o que separa "onde eu clico" de "o que eu leio".
 *  · MAGENTA é exclusivo da franja de glitch do loader. Em nenhum outro lugar.
 *  · ESTADO = cor + ícone + palavra, sempre. Cor sozinha não é estado — quem
 *    não distingue verde de vermelho ainda tem de conseguir operar.
 *  · TRÊS VOZES tipográficas, e só três.
 *
 * WHITE-LABEL — por que os tokens de superfície são `var(--color-*, <valor>)`:
 *
 * O `ThemeProvider` (já montado em `App.tsx`, acima das rotas) busca
 * `/v1/tenant/branding` e injeta `--color-primary`, `--color-bg-base`, etc. num
 * `<style>` no head. Referenciar essas vars AQUI faz o tema do cliente valer nas
 * telas novas sem um segundo provider, sem um segundo fetch e sem duas fontes de
 * verdade sobre a cor do tenant. Sem override, o fallback é o valor do desenho.
 *
 * O que NÃO é white-label, de propósito:
 *
 *  · **estado** (ok/atenção/nc) — verde, âmbar e vermelho são semântica de
 *    segurança, não marca. Um tenant repintar "não conforme" de verde é risco
 *    de segurança, não personalização.
 *  · **magentaGlitch** — é a assinatura do loader da Logikos, não do cliente.
 *    White-label troca a marca do produto, não a identidade de quem o fez.
 */
import { createGlobalTheme } from '@vanilla-extract/css'

export const lk = createGlobalTheme(':root', {
  cor: {
    /** fundo da aplicação */
    preto: 'var(--color-bg-base, #0A0A0F)',
    /** superfícies: topbar, sidebar, cards */
    grafite: 'var(--color-bg-surface, #14141C)',
    /** bordas 1px e divisores */
    borda: 'var(--color-border, #23242F)',
    /** texto principal e wordmark */
    brancoSinal: 'var(--color-text-primary, #F4F6F8)',
    /** secundário, labels overline */
    cinzaNevoa: 'var(--color-text-secondary, #8A8F98)',
    /** ⚠️ SÓ interativo, ≤10%, nunca fundo */
    cianoVisao: 'var(--color-primary, #00E5FF)',
    /** hover/pressed do acento */
    cianoProfundo: 'var(--color-primary-dark, #0091AD)',
    /** ⚠️ SÓ a franja de glitch do loader — NÃO entra no white-label */
    magentaGlitch: '#FF2E63',
  },
  /** semântica de segurança — fora do white-label, de propósito */
  estado: {
    ok: '#3ECF8E',
    atencao: '#E8A13C',
    nc: '#E5484D',
  },
  fonte: {
    /** títulos, números grandes, wordmark */
    titulo: "'Space Grotesk', system-ui, sans-serif",
    /** UI */
    ui: "'Inter', system-ui, sans-serif",
    /** dados, códigos, timers, labels overline */
    mono: "'JetBrains Mono', ui-monospace, monospace",
  },
  medida: {
    topbar: '56px',
    sidebar: '236px',
    sidebarColapsada: '64px',
    itemNav: '38px',
    bannerAdmin: '42px',
    conteudoMax: '1280px',
    padding: '24px',
    paletaCmdK: '600px',
    /** botões de veredito — ≥48px, e ≥56px na Verificação */
    veredito: '48px',
    vereditoVerificacao: '56px',
  },
  raio: { s: '8px', m: '10px', g: '12px' },
  /** grid 8pt */
  espaco: { x1: '8px', x2: '16px', x3: '24px', x4: '32px', x5: '40px' },
})

/** Overline: mono, caixa alta, tracking .16–.22em. Usado em labels de dado. */
export const OVERLINE_TRACKING = '0.18em'
