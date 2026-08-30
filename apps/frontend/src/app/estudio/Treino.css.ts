import { style } from '@vanilla-extract/css'

import { lk, OVERLINE_TRACKING } from '../tokens/lk.css'

const veu = (cor: string, pct: number) => `color-mix(in srgb, ${cor} ${pct}%, transparent)`

export const raiz = style({ display: 'flex', flexDirection: 'column', gap: lk.espaco.x2 })

export const cabecalho = style({ display: 'flex', alignItems: 'center', gap: lk.espaco.x2 })

export const titulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '22px',
  margin: 0,
})

export const espacador = style({ flex: 1 })

export const botaoPrimario = style({
  height: '38px',
  padding: `0 ${lk.espaco.x2}`,
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontFamily: lk.fonte.ui,
  fontSize: '13.5px',
  fontWeight: 700,
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  selectors: { '&:disabled': { opacity: 0.6, cursor: 'default' } },
})

export const botaoSecundario = style({
  height: '34px',
  padding: '0 13px',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  background: 'transparent',
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '12.5px',
  fontWeight: 600,
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  selectors: { '&:disabled': { opacity: 0.6, cursor: 'default' } },
})

export const botaoParar = style([
  botaoSecundario,
  { color: lk.estado.nc, borderColor: veu(lk.estado.nc, 40) },
])

export const botaoIcone = style({
  background: 'none',
  border: 'none',
  color: lk.cor.cinzaNevoa,
  cursor: 'pointer',
  padding: '4px',
  display: 'inline-flex',
})

// ── banner GPU off ───────────────────────────────────────────────────────────

export const bannerGpu = style({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  padding: '10px 14px',
  background: veu(lk.estado.atencao, 12),
  border: `1px solid ${lk.estado.atencao}`,
  borderRadius: lk.raio.s,
  color: lk.estado.atencao,
  fontSize: '13px',
})

export const linkBanner = style({
  color: lk.cor.cianoVisao,
  display: 'flex',
  alignItems: 'center',
  gap: '4px',
  textDecoration: 'none',
  whiteSpace: 'nowrap',
  fontSize: '13px',
})

// ── cartão do job ────────────────────────────────────────────────────────────

export const cartao = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
  padding: '20px',
})

export const cartaoAoVivo = style({ borderColor: veu(lk.cor.cianoVisao, 35) })

export const linhaAoVivo = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x2,
  flexWrap: 'wrap',
})

export const nomeJob = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '17px',
})

export const pilulaAoVivo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  color: lk.cor.cianoVisao,
  border: `1px solid ${veu(lk.cor.cianoVisao, 40)}`,
  borderRadius: '5px',
  padding: '3px 8px',
  letterSpacing: OVERLINE_TRACKING,
})

export const infoMono = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
})

export const dataJob = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
  marginLeft: 'auto',
  whiteSpace: 'nowrap',
})

// pílula de status (cor por status — ver estadoCor em Treino.tsx)
export const pilula = style({
  display: 'inline-flex',
  alignItems: 'center',
  fontSize: '11.5px',
  fontWeight: 600,
  borderRadius: '999px',
  padding: '2px 9px',
})

export const pilulaOk = style([pilula, { color: lk.estado.ok, background: veu(lk.estado.ok, 14) }])
export const pilulaAtencao = style([pilula, { color: lk.estado.atencao, background: veu(lk.estado.atencao, 14) }])
export const pilulaNc = style([pilula, { color: lk.estado.nc, background: veu(lk.estado.nc, 14) }])
export const pilulaNeutra = style([pilula, { color: lk.cor.cinzaNevoa, background: veu(lk.cor.cinzaNevoa, 14) }])

export const progressoLinha = style({ display: 'flex', alignItems: 'center', gap: lk.espaco.x2 })

export const progressoTrilho = style({
  flex: 1,
  height: '10px',
  background: lk.cor.preto,
  borderRadius: '5px',
  overflow: 'hidden',
})

export const progressoPreenchido = style({ height: '100%', background: lk.cor.cianoVisao })

export const progressoLabel = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
  whiteSpace: 'nowrap',
})

export const progressoValor = style({ color: lk.cor.brancoSinal })

// ── gráficos ao vivo ─────────────────────────────────────────────────────────

export const grade2 = style({ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' })

export const cardGrafico = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '8px',
  padding: '14px',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
})

export const rotuloGrafico = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: OVERLINE_TRACKING,
  color: lk.cor.cinzaNevoa,
})

export const svgGrafico = style({ width: '100%', height: '80px', display: 'block' })

export const linhaPerda = style({ stroke: lk.estado.atencao })
export const linhaAcerto = style({ stroke: lk.estado.ok })

// ── métricas finais ──────────────────────────────────────────────────────────

export const metricas = style({ display: 'flex', gap: '14px', flexWrap: 'wrap' })

export const metrica = style({ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1px' })

export const metricaRotulo = style({
  fontSize: '9px',
  color: lk.cor.cinzaNevoa,
  textTransform: 'uppercase',
  letterSpacing: OVERLINE_TRACKING,
  fontWeight: 600,
})

export const metricaValor = style({ fontSize: '14px', fontWeight: 700, fontFamily: lk.fonte.mono })
export const metricaDestaque = style({ color: lk.cor.cianoVisao })

export const erroJob = style({
  padding: '8px 10px',
  background: veu(lk.estado.nc, 10),
  borderRadius: lk.raio.s,
  fontSize: '12px',
  color: lk.estado.nc,
})

export const vazio = style({ color: lk.cor.cinzaNevoa, fontSize: '13px', margin: 0 })

// ── formulário de configuração ───────────────────────────────────────────────

export const formulario = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
  padding: '14px 16px',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
})

export const grade = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
  gap: lk.espaco.x2,
})

export const campo = style({ display: 'flex', flexDirection: 'column', gap: '4px' })

export const rotuloCampo = style({
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
  display: 'flex',
  alignItems: 'center',
  gap: '4px',
})

const controle = style({
  height: '34px',
  padding: '0 10px',
  borderRadius: lk.raio.s,
  border: `1px solid ${lk.cor.borda}`,
  background: lk.cor.grafite,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
})

export const selectCampo = style([controle])
export const inputCampo = style([controle])

export const acoesFormulario = style({ display: 'flex', gap: '8px' })

// ── logs ─────────────────────────────────────────────────────────────────────

export const logsCabecalho = style({ display: 'flex', justifyContent: 'space-between', alignItems: 'center' })

export const logsTitulo = style({
  fontSize: '12px',
  fontWeight: 600,
  color: lk.cor.cinzaNevoa,
  textTransform: 'uppercase',
  letterSpacing: OVERLINE_TRACKING,
})

export const limparLogs = style({
  background: 'none',
  border: 'none',
  color: lk.cor.cinzaNevoa,
  fontSize: '11px',
  cursor: 'pointer',
})

export const logsCaixa = style({
  height: '180px',
  overflowY: 'auto',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  padding: '8px 10px',
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
})

export const logLinha = style({ lineHeight: 1.6 })
export const logLinhaWs = style([logLinha, { color: lk.cor.cianoVisao }])

// ── histórico (linhas) ───────────────────────────────────────────────────────

export const historicoTitulo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: OVERLINE_TRACKING,
  color: lk.cor.cinzaNevoa,
  textTransform: 'uppercase',
})

export const historicoLista = style({ display: 'flex', flexDirection: 'column', gap: '8px' })

export const historicoLinha = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x2,
  flexWrap: 'wrap',
  padding: '12px 16px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '9px',
})

export const historicoLinhaFalhou = style({ borderColor: veu(lk.estado.nc, 40) })

export const historicoNome = style({ fontSize: '13px', fontWeight: 600 })

export const historicoData = style({ fontFamily: lk.fonte.mono, fontSize: '11px', color: lk.cor.cinzaNevoa })

export const historicoEpocas = style({ fontFamily: lk.fonte.mono, fontSize: '12px', color: lk.cor.cinzaNevoa })

export const historicoErro = style({ fontSize: '12.5px', color: lk.estado.nc, fontWeight: 600 })
