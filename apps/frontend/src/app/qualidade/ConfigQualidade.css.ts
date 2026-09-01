import { style } from '@vanilla-extract/css'

import { lk, OVERLINE_TRACKING } from '../tokens/lk.css'

export const raiz = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '18px',
  maxWidth: lk.medida.conteudoMax,
  width: '100%',
})

export const cabecalho = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x2,
  flexWrap: 'wrap',
})

/** Link de saída da tela — mesmo recipe de `Qualidade.css.ts`. */
export const voltar = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  padding: '0 12px 0 0',
  borderRight: `1px solid ${lk.cor.borda}`,
  fontSize: '13.5px',
  color: lk.cor.cinzaNevoa,
  textDecoration: 'none',
  selectors: {
    '&:hover': { color: lk.cor.brancoSinal },
  },
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '26px',
})

/** Grupo de abas do desenho: pílula sobre grafite, 3px de folga interna. */
export const abas = style({
  display: 'flex',
  background: lk.cor.grafite,
  borderRadius: lk.raio.s,
  padding: '3px',
  gap: '2px',
})

export const aba = style({
  height: '36px',
  padding: `0 18px`,
  border: 'none',
  borderRadius: '6px',
  background: 'transparent',
  color: lk.cor.cinzaNevoa,
  fontSize: '14px',
  fontWeight: 600,
  cursor: 'pointer',
  selectors: {
    '&[aria-selected="true"]': {
      background: lk.cor.preto,
      color: lk.cor.cianoVisao,
    },
  },
})

export const espacador = style({ flex: 1 })

/**
 * A legenda do desenho ("valem imediatamente nas estações — sem deploy") é
 * falsa no caminho servido. Este é o lugar dela, com o texto verdadeiro.
 */
export const avisoTopo = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
  maxWidth: '440px',
  lineHeight: 1.45,
})

export const secaoTitulo = style({
  margin: 0,
  fontFamily: lk.fonte.mono,
  fontSize: '11.5px',
  letterSpacing: OVERLINE_TRACKING,
  color: lk.cor.cinzaNevoa,
  fontWeight: 600,
  textTransform: 'uppercase',
})

export const secaoCabecalho = style({
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
})

export const colunas = style({
  display: 'flex',
  gap: '18px',
  alignItems: 'flex-start',
  flexWrap: 'wrap',
})

export const colunaPrincipal = style({
  flex: 1,
  minWidth: '360px',
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
})

export const painelLateral = style({
  width: '340px',
  flex: 'none',
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
  padding: '18px',
})

export const painelTitulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '18px',
})

export const rotulo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  letterSpacing: OVERLINE_TRACKING,
  color: lk.cor.cinzaNevoa,
  textTransform: 'uppercase',
})

export const listaFalta = style({
  margin: 0,
  paddingLeft: '18px',
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  fontSize: '13px',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.5,
})

export const botaoPrimario = style({
  height: lk.medida.veredito,
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '15px',
  letterSpacing: '.03em',
  cursor: 'pointer',
  ':disabled': { opacity: 0.4, cursor: 'not-allowed' },
})

export const botaoContorno = style({
  height: '34px',
  padding: `0 14px`,
  background: 'transparent',
  border: `1px solid ${lk.cor.cianoVisao}`,
  borderRadius: '6px',
  color: lk.cor.cianoVisao,
  fontSize: '13px',
  fontWeight: 600,
  cursor: 'pointer',
  flex: 'none',
  ':disabled': { opacity: 0.4, cursor: 'not-allowed', borderColor: lk.cor.borda, color: lk.cor.cinzaNevoa },
})

export const acao = style({
  height: '32px',
  padding: `0 12px`,
  background: 'transparent',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '7px',
  color: lk.cor.brancoSinal,
  fontSize: '12.5px',
  fontWeight: 600,
  cursor: 'pointer',
  flex: 'none',
  ':disabled': { opacity: 0.4, cursor: 'not-allowed' },
})

/** Linha de limiar: uma por câmera (não por ponto — ponto não existe). */
export const linhaLimiar = style({
  display: 'flex',
  alignItems: 'center',
  gap: '18px',
  padding: '14px 16px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  flexWrap: 'wrap',
})

export const nomeCamera = style({
  fontSize: '14px',
  fontWeight: 600,
  minWidth: '180px',
})

export const localCamera = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
})

export const identificacao = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
  minWidth: 0,
})

export const parLimiar = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '3px',
  flex: 'none',
})

export const valor = style({
  fontFamily: lk.fonte.mono,
  fontSize: '15px',
  fontWeight: 700,
})

export const valorAusente = style({
  fontFamily: lk.fonte.mono,
  fontSize: '13px',
  color: lk.cor.cinzaNevoa,
})

/** Tabela de estações — as colunas que o servidor realmente entrega. */
export const tabela = style({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr 130px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  overflow: 'hidden',
})

export const th = style({
  padding: '10px 14px',
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
  letterSpacing: OVERLINE_TRACKING,
  color: lk.cor.cinzaNevoa,
  borderBottom: `1px solid ${lk.cor.borda}`,
  textTransform: 'uppercase',
})

export const td = style({
  padding: '13px 14px',
  fontSize: '14px',
  borderBottom: `1px solid ${lk.cor.borda}`,
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
  minWidth: 0,
})

export const codigoEstacao = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
})

export const estado = style({
  display: 'flex',
  alignItems: 'center',
  gap: '7px',
  fontSize: '12px',
  fontWeight: 700,
})

export const faixaFalta = style({
  display: 'flex',
  alignItems: 'flex-start',
  gap: '10px',
  padding: '12px 16px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.55,
})

export const vazio = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '10px',
  textAlign: 'center',
  padding: '32px 24px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
})

export const vazioTitulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '17px',
})

export const vazioTexto = style({
  fontSize: '13.5px',
  color: lk.cor.cinzaNevoa,
  maxWidth: '520px',
  lineHeight: 1.55,
})

export const centro = style({
  minHeight: '60vh',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '14px',
  textAlign: 'center',
  padding: lk.medida.padding,
})

export const centroTitulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '19px',
})

export const centroTecnico = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
})

export const botaoRetry = style({
  height: '38px',
  padding: `0 ${lk.espaco.x2}`,
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontSize: '13px',
  fontWeight: 700,
  cursor: 'pointer',
})
