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
 * WHITE-LABEL — o que o tenant pinta, e o que ele NÃO pinta.
 *
 * Só a COR DE MARCA vem do tenant: `--color-primary`, que o `ThemeProvider`
 * (já montado em `App.tsx`) busca em `/v1/tenant/branding`. Logo, produto e
 * cor de marca são do cliente — o resto é a identidade Logikos Vision.
 *
 * As SUPERFÍCIES (fundo, borda, texto) ficam nos valores do desenho, e isto foi
 * MEDIDO, não suposto. Ao ligá-las a `var(--color-bg-base, …)` etc., o tenant
 * RVB do DEV — que tem white-label claro, herdado do shell antigo — renderizou o
 * shell novo com fundo branco, `--color-text-primary: #0080ff` (texto azul) e
 * `--color-border: #136ec9`. Não era o desenho: era o tema do front ANTIGO
 * vazando para dentro do novo. Aqueles valores foram escolhidos para um shell
 * claro; no shell escuro eles não são personalização, são quebra de identidade.
 *
 * Isso NÃO quer dizer que tenant nunca poderá ajustar superfície — quer dizer
 * que um white-label do shell escuro precisa ser DESENHADO: quais tokens são
 * abertos e com que piso de contraste, para a legibilidade sobreviver a
 * qualquer escolha do cliente. Está na lista do design.
 *
 * Também FORA do white-label, e por outro motivo:
 *
 *  · **estado** (ok/atenção/nc) — verde, âmbar e vermelho são semântica de
 *    segurança, não marca. Um tenant repintar "não conforme" de verde é risco
 *    de segurança, não personalização.
 *  · **magentaGlitch** — assinatura do loader da Logikos, não do cliente.
 */
import { createGlobalTheme } from '@vanilla-extract/css'

export const lk = createGlobalTheme(':root', {
  cor: {
    /** fundo da aplicação */
    preto: '#0A0A0F',
    /** superfícies: topbar, sidebar, cards */
    grafite: '#14141C',
    /** bordas 1px e divisores */
    borda: '#23242F',
    /**
     * Borda mais presente: contorno de avatar, hover de controle secundário.
     * Estava faltando no contrato — o handoff usa este valor 18 vezes e eu
     * vinha escrevendo o hex à mão, que é exatamente o que os tokens existem
     * para impedir.
     */
    bordaForte: '#3A3D4A',
    /** texto principal e wordmark */
    brancoSinal: '#F4F6F8',
    /** secundário, labels overline */
    cinzaNevoa: '#8A8F98',
    /** ⚠️ SÓ interativo, ≤10%, nunca fundo de superfície. Cor de MARCA do tenant. */
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
