/**
 * Kiosk — medidas de `docs/design/handoff-f5/Kiosk RVB.dc.html` (K1 idle,
 * K2 identificação, K3 validando, K4 verde, K5/K6 reprovado, K8 concluída),
 * via token. Cor e tipografia só por `lk.*` — zero hex solto.
 *
 * Padrão do desenho: MONO só em código/dado (piece_number, timers) — labels
 * e frases seguem a fonte de UI. `veredito` usa `lk.medida.vereditoVerificacao`
 * (56px) — o piso que a Verificação já definiu para decisão repetida.
 */
import { keyframes, style, styleVariants } from '@vanilla-extract/css'

import { lk, OVERLINE_TRACKING } from '../tokens/lk.css'

export const raiz = style({
  width: '100vw',
  height: '100vh',
  overflow: 'hidden',
  fontFamily: lk.fonte.ui,
})

const telaBase = {
  width: '100%',
  height: '100%',
  boxSizing: 'border-box',
  position: 'relative',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: lk.espaco.x2,
  padding: lk.espaco.x4,
  textAlign: 'center',
} as const

/** Telas de fundo sólido — a cor É o veredito (K1/K4/K8 do desenho). */
export const tela = styleVariants({
  neutra: { ...telaBase, background: lk.cor.preto, color: lk.cor.brancoSinal },
  aprovada: { ...telaBase, background: lk.estado.ok, color: lk.cor.preto },
})

/**
 * Reprovado NÃO é tela sólida vermelha (K5/K6 do desenho): faixa de estado no
 * topo + corpo escuro abaixo — o vermelho grita no veredito, não na leitura
 * do defeito por baixo dele.
 */
export const telaComFaixa = style({
  width: '100%',
  height: '100%',
  boxSizing: 'border-box',
  display: 'flex',
  flexDirection: 'column',
  color: lk.cor.brancoSinal,
  background: `color-mix(in srgb, ${lk.estado.nc} 16%, ${lk.cor.preto})`,
})

export const faixaEstado = style({
  flex: 'none',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: lk.espaco.x2,
  padding: `${lk.espaco.x2} ${lk.espaco.x3}`,
  background: lk.estado.nc,
  color: lk.cor.preto,
})

export const corpoFaixa = style({
  flex: 1,
  minHeight: 0,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: lk.espaco.x2,
  padding: lk.espaco.x3,
  textAlign: 'center',
})

/** Label curto, mudo — nunca a fonte do dado (essa é `codigoPeca`). */
export const overline = style({
  fontFamily: lk.fonte.ui,
  fontSize: '14px',
  letterSpacing: OVERLINE_TRACKING,
  textTransform: 'uppercase',
  opacity: 0.68,
})

export const subtitulo = style({
  fontSize: '22px',
  opacity: 0.75,
})

export const tituloEstacao = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '64px',
  letterSpacing: '.02em',
})

export const tituloMedio = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '32px',
})

/** Código de peça — mono, sempre. É dado, não rótulo. */
export const codigoPeca = style({
  fontFamily: lk.fonte.mono,
  fontWeight: 700,
  fontSize: '48px',
  letterSpacing: '.04em',
})

/** Mesma regra em tamanho de nota — usada nos rodapés de contexto. */
export const codigoNota = style({
  fontFamily: lk.fonte.mono,
  fontSize: '16px',
  opacity: 0.7,
})

/** Palavra do veredito — piso de 56px (lk.medida.vereditoVerificacao), a
 *  mesma medida que a Verificação já subiu para decisão repetida. */
export const veredito = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: lk.medida.vereditoVerificacao,
  letterSpacing: '.04em',
})

const girar = keyframes({ to: { transform: 'rotate(360deg)' } })

export const spinner = style({
  animation: `${girar} 1s linear infinite`,
})

export const linhaAcoes = style({
  display: 'flex',
  gap: lk.espaco.x2,
  flexWrap: 'wrap',
  justifyContent: 'center',
  marginTop: lk.espaco.x2,
})

/** Botões de ação do kiosk — mesmo piso de altura do veredito: é decisão
 *  repetida em pé, o alvo pequeno aqui também vira erro de operação. */
const botaoBase = {
  height: lk.medida.vereditoVerificacao,
  minWidth: '320px',
  padding: `0 ${lk.espaco.x3}`,
  borderRadius: lk.raio.m,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '19px',
  letterSpacing: '.03em',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '10px',
  cursor: 'pointer',
} as const

export const botao = styleVariants({
  primario: {
    ...botaoBase,
    border: 'none',
    background: lk.cor.cianoVisao,
    color: lk.cor.preto,
    selectors: { '&:disabled': { opacity: 0.5, cursor: 'not-allowed' } },
  },
  perigo: {
    ...botaoBase,
    border: 'none',
    background: lk.estado.nc,
    color: lk.cor.preto,
    selectors: { '&:disabled': { opacity: 0.5, cursor: 'not-allowed' } },
  },
  contorno: {
    ...botaoBase,
    background: 'transparent',
    border: `2px solid color-mix(in srgb, ${lk.cor.brancoSinal} 45%, transparent)`,
    color: lk.cor.brancoSinal,
    selectors: {
      '&:hover:not(:disabled)': {
        background: `color-mix(in srgb, ${lk.cor.brancoSinal} 8%, transparent)`,
      },
      '&:disabled': { opacity: 0.5, cursor: 'not-allowed' },
    },
  },
})

export const passos = style({ display: 'flex', alignItems: 'center', gap: lk.espaco.x1 })

export const passoConector = style({ width: '40px', height: '3px', background: lk.cor.borda })

const passoCirculoBase = {
  width: '44px',
  height: '44px',
  borderRadius: '50%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontFamily: lk.fonte.mono,
  fontWeight: 700,
  fontSize: '15px',
} as const

export const passoCirculo = styleVariants({
  inativo: { ...passoCirculoBase, background: lk.cor.grafite, border: `2px solid ${lk.cor.bordaForte}`, color: lk.cor.cinzaNevoa },
  ativo: { ...passoCirculoBase, background: lk.cor.cianoVisao, border: `2px solid ${lk.cor.cianoVisao}`, color: lk.cor.preto },
  aprovado: { ...passoCirculoBase, background: lk.estado.ok, border: `2px solid ${lk.estado.ok}`, color: lk.cor.preto },
})

export const foto = style({
  maxWidth: '480px',
  maxHeight: '280px',
  borderRadius: lk.raio.m,
  border: `3px solid ${lk.estado.nc}`,
  objectFit: 'contain',
})

export const rodape = style({
  position: 'absolute',
  bottom: '20px',
  fontSize: '13px',
  letterSpacing: '.2em',
  opacity: 0.45,
})
