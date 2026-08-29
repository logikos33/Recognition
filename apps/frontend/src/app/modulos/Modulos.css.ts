import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

/**
 * O fundo do desenho: duas tramas diagonais a 66° e −66°, linha de 1px a cada
 * 85px. Medidas literais da spec — não são grid de 8pt, são a textura.
 */
export const raiz = style({
  minHeight: '100vh',
  display: 'flex',
  flexDirection: 'column',
  background: lk.cor.preto,
  backgroundImage: `repeating-linear-gradient(66deg,transparent 0 84px,${lk.cor.grafite} 84px 85px),repeating-linear-gradient(-66deg,transparent 0 84px,${lk.cor.grafite} 84px 85px)`,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
})

export const topo = style({
  height: '64px',
  flex: 'none',
  display: 'flex',
  alignItems: 'center',
  gap: '14px',
  padding: '0 32px',
})

export const marca = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '16px',
  letterSpacing: '0.14em',
})

export const divisor = style({ width: '1px', height: '22px', background: lk.cor.borda })
export const tenant = style({ fontSize: '13.5px', color: lk.cor.cinzaNevoa })
export const espacador = style({ flex: 1 })

export const identidade = style({ display: 'flex', alignItems: 'center', gap: '9px' })

export const avatar = style({
  width: '30px',
  height: '30px',
  borderRadius: '50%',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.bordaForte}`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '12px',
  fontWeight: 600,
})

export const nome = style({ fontSize: '13px', fontWeight: 600, lineHeight: 1.2 })
export const papel = style({ fontSize: '11px', color: lk.cor.cinzaNevoa, lineHeight: 1.2 })

export const sair = style({
  height: '32px',
  display: 'flex',
  alignItems: 'center',
  padding: '0 13px',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '7px',
  background: 'transparent',
  color: lk.cor.cinzaNevoa,
  fontSize: '12.5px',
  fontWeight: 600,
  cursor: 'pointer',
  ':hover': { color: lk.cor.brancoSinal, borderColor: lk.cor.bordaForte },
})

export const centro = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '26px',
  padding: lk.medida.padding,
  boxSizing: 'border-box',
})

export const cabecalho = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '6px',
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '26px',
})

export const subtitulo = style({ fontSize: '13px', color: lk.cor.cinzaNevoa })

export const grade = style({
  display: 'flex',
  gap: '14px',
  flexWrap: 'wrap',
  justifyContent: 'center',
  maxWidth: '1080px',
})

export const cartao = style({
  position: 'relative',
  width: '240px',
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
  padding: '20px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '14px',
  color: lk.cor.brancoSinal,
  textAlign: 'left',
  cursor: 'pointer',
  textDecoration: 'none',
  ':hover': { borderColor: 'rgba(0,229,255,.5)' },
})

/** Último módulo visitado: borda ciano tênue, como no desenho. */
export const cartaoUltimo = style({ borderColor: 'rgba(0,229,255,.35)' })

export const linhaIcone = style({ display: 'flex', alignItems: 'center', gap: '10px' })

export const tecla = style({
  marginLeft: 'auto',
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '5px',
  padding: '2px 8px',
})

export const textos = style({ display: 'flex', flexDirection: 'column', gap: '2px' })

export const nomeModulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '18px',
})

export const descricao = style({
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.5,
})

export const rodapeCartao = style({
  display: 'flex',
  alignItems: 'center',
  gap: '7px',
  padding: '9px 11px',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
})

export const ponto = style({ width: '8px', height: '8px', borderRadius: '50%', flex: 'none' })
export const pendencia = style({ fontSize: '12px', fontWeight: 600 })

export const selo = style({
  position: 'absolute',
  top: '-9px',
  left: '16px',
  fontFamily: lk.fonte.mono,
  fontSize: '9px',
  letterSpacing: '0.12em',
  color: lk.cor.cianoVisao,
  background: lk.cor.preto,
  border: '1px solid rgba(0,229,255,.4)',
  borderRadius: '4px',
  padding: '2px 7px',
})

export const admin = style({
  display: 'flex',
  alignItems: 'center',
  gap: '9px',
  height: '38px',
  padding: `0 ${lk.espaco.x2}`,
  border: '1px solid rgba(232,161,60,.45)',
  borderRadius: '9px',
  background: 'transparent',
  color: lk.estado.atencao,
  fontSize: '13px',
  fontWeight: 600,
  textDecoration: 'none',
  cursor: 'pointer',
})

export const nota = style({ fontSize: '12px', color: lk.cor.cinzaNevoa })

export const vazio = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: lk.espaco.x1,
  maxWidth: '420px',
  textAlign: 'center',
})
