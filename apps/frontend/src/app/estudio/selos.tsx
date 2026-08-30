/**
 * Selos compartilhados entre `Modelo.tsx` e `Treino.tsx` (Estúdio) — porte de
 * `pages/TrainingPage.tsx` (fonte da paridade): marcação de simulação (task
 * "treino honesto", C2), proveniência do treino (`trained_models.origin`,
 * migration 090) e dono do modelo. Puro texto/paridade — nada da prancha.
 */
import { AlertTriangle } from 'lucide-react'

import { Tooltip } from '../../components/ui/Tooltip/Tooltip'
import type { TrainedModel } from '../../types'
import * as s from './selos.css'

/** Rótulos pt-BR para a proveniência do treino. */
const ORIGIN_LABELS: Record<string, string> = {
  vast_ai: 'GPU Vast.ai',
  ultralytics_hub: 'Ultralytics HUB',
  colab: 'Google Colab',
  simulated: 'Treino simulado',
  training_service: 'Serviço de treino',
  unknown: '—',
}

export function originLabel(origin?: string): string {
  return ORIGIN_LABELS[origin ?? 'unknown'] ?? origin ?? '—'
}

/**
 * `origin === 'simulated'` OU `metrics.simulated === true` (marcador escrito
 * pelo backend só quando TRAINING_SIMULATION_ENABLED roda de fato) — mesma
 * regra de `isSimulatedArtifact` em `pages/TrainingPage.tsx`.
 */
export function isSimulatedArtifact(origin?: string, metrics?: { simulated?: boolean }): boolean {
  return origin === 'simulated' || metrics?.simulated === true
}

/** Marcação visual inconfundível de simulação — NUNCA no mesmo formato de uma métrica real. */
export function SeloSimulacao() {
  return (
    <span className={s.pilulaSimulacao}>
      <AlertTriangle size={10} style={{ marginRight: 3 }} /> SIMULAÇÃO — não é treino real
    </span>
  )
}

/** Dono do modelo — nome com tooltip mostrando o e-mail (quando disponível). */
export function OwnerInfo({ model }: { model: TrainedModel }) {
  const nome = model.owner_name ?? '—'
  const texto = <span className={s.dono}>Dono: {nome}</span>
  if (!model.owner_email) return texto
  return <Tooltip label={model.owner_email}>{texto}</Tooltip>
}
