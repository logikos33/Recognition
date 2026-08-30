import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

const veu = (cor: string, pct: number) => `color-mix(in srgb, ${cor} ${pct}%, transparent)`

/** Marcação indelével de simulação — NUNCA no mesmo formato de uma métrica real. */
export const pilulaSimulacao = style({
  display: 'inline-flex',
  alignItems: 'center',
  fontSize: '11.5px',
  fontWeight: 700,
  borderRadius: '999px',
  padding: '2px 9px',
  color: lk.estado.nc,
  background: veu(lk.estado.nc, 14),
})

export const dono = style({
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
})
