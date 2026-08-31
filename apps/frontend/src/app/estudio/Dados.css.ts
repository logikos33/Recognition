import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

export const cabecalho = style({
  display: 'flex',
  alignItems: 'baseline',
  justifyContent: 'space-between',
  marginBottom: '16px',
})

export const titulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '20px',
  margin: 0,
})

export const barraPropagacao = style({
  marginBottom: '12px',
})

/**
 * F5-LEVE (tema não pode estourar): `TrainingGallery` é núcleo compartilhado
 * com o front antigo (`components/training/TrainingGallery`, docstring de
 * `Dados.tsx`) — não se edita o grid dela daqui. Contendo o scroll POR FORA,
 * num wrapper só desta rota, a galeria (que cresce sem paginação com o total
 * de frames) rola dentro de si em vez de empurrar a página inteira, sem
 * tocar no componente compartilhado. O cálculo não desconta `cabecalho` +
 * `barraPropagacao` (altura variável) — a folga que sobra é constante, não
 * proporcional ao nº de frames, que era o bug de verdade.
 */
export const galeriaRolavel = style({
  maxHeight: `calc(100vh - ${lk.medida.topbar} - ${lk.medida.padding} * 2 - var(--global-banner-offset, 0px))`,
  overflowY: 'auto',
})
