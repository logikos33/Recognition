/**
 * Estilos compartilhados das 3 telas de Acesso (Entrar, Esqueci senha,
 * Redefinir senha) — spec: `docs/design/handoff-f5/Acesso Logikos.dc.html`.
 *
 * UM módulo só para as três: as telas são visualmente idênticas (mesma
 * moldura, mesmo cartão, mesmos campos) — duplicar em 3 arquivos seria
 * copiar-colar sem motivo. Zero hex solto: só tokens de `lk.css.ts`.
 */
import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

const veu = (cor: string, pct: number) => `color-mix(in srgb, ${cor} ${pct}%, transparent)`

export const pagina = style({
  minHeight: '100vh',
  width: '100%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: lk.cor.preto,
  backgroundImage: `repeating-linear-gradient(66deg,transparent 0 64px,${lk.cor.grafite} 64px 65px),repeating-linear-gradient(-66deg,transparent 0 64px,${lk.cor.grafite} 64px 65px)`,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  padding: lk.espaco.x2,
  boxSizing: 'border-box',
})

export const coluna = style({
  width: '400px',
  maxWidth: '100%',
  display: 'flex',
  flexDirection: 'column',
  gap: '22px',
})

export const marcaWrap = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '12px',
})

export const marcaTitulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '22px',
  letterSpacing: '0.16em',
})

export const marcaSub = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '0.24em',
  color: lk.cor.cinzaNevoa,
})

export const cartao = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
  padding: '26px',
  boxShadow: '0 24px 80px rgba(0,0,0,.5)',
})

/** Pilha de campos dentro do cartão (form) — mesmo gap do cartão, sem moldura. */
export const formStack = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
})

export const tituloTela = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '19px',
})

export const textoApoio = style({
  fontSize: '13px',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.55,
})

export const campo = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
})

export const linhaRotulo = style({
  display: 'flex',
  alignItems: 'baseline',
})

export const rotulo = style({
  fontSize: '13px',
  color: lk.cor.cinzaNevoa,
})

export const linkCanto = style({
  marginLeft: 'auto',
  fontSize: '12.5px',
  fontWeight: 600,
  color: lk.cor.cianoVisao,
  cursor: 'pointer',
  background: 'none',
  border: 'none',
  padding: 0,
})

export const input = style({
  height: '44px',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '14px',
  padding: '0 13px',
  outline: 'none',
  '::placeholder': { color: lk.cor.cinzaNevoa },
  ':focus': { borderColor: lk.cor.cianoVisao },
})

export const botao = style({
  height: '48px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '9px',
  border: 'none',
  borderRadius: lk.raio.m,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontFamily: lk.fonte.ui,
  fontSize: '14.5px',
  fontWeight: 700,
  cursor: 'pointer',
  ':disabled': { cursor: 'not-allowed', opacity: 0.6 },
})

export const erroBox = style({
  display: 'flex',
  alignItems: 'center',
  gap: '9px',
  padding: '10px 12px',
  background: veu(lk.estado.nc, 7),
  border: `1px solid ${veu(lk.estado.nc, 40)}`,
  borderRadius: lk.raio.s,
})

export const erroTexto = style({
  fontSize: '12.5px',
  color: lk.estado.nc,
  fontWeight: 600,
})

export const sucessoWrap = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '10px',
  padding: '14px',
  textAlign: 'center',
})

export const sucessoTitulo = style({
  fontSize: '14px',
  fontWeight: 600,
})

export const sucessoTexto = style({
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.55,
})

export const linkVoltar = style({
  fontSize: '13px',
  fontWeight: 600,
  color: lk.cor.cianoVisao,
  textAlign: 'center',
  cursor: 'pointer',
  textDecoration: 'none',
})

export const rodape = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '0.14em',
  color: lk.cor.cinzaNevoa,
  textAlign: 'center',
})

export const requisitos = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '5px',
  padding: '12px',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
})

export const requisitoItem = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  fontSize: '12.5px',
})

export const requisitoMarcador = style({
  fontWeight: 700,
  width: '12px',
  textAlign: 'center',
  flex: 'none',
})

/** Overlay de tela cheia — o `variante="fullscreen"` do LogikosLoader não é
 * `position:fixed` por padrão (preenche o contêiner onde é montado), então
 * quem pede "loader cobrindo a tela toda" precisa dar a posição. */
export const overlayCarregando = style({
  position: 'fixed',
  inset: 0,
  zIndex: 120,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: lk.cor.preto,
})
