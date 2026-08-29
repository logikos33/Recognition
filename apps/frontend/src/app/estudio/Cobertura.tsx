/**
 * Cobertura — matriz classe×câmera do Estúdio (`Estúdio.dc.html`).
 *
 * Embrulha `CoverageMatrix` (núcleo compartilhado — o mesmo core que
 * `pages/TrainingPage.tsx` usa na aba Cobertura, importado como está, nunca
 * editado daqui). Os saltos que lá trocavam de aba viram navegação de rota:
 * "anotar" leva pra Dados focado na câmera; "classificar" leva pra
 * Classificar focado na câmera (e na classe, quando a lacuna já sabe qual é).
 */
import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

import { CoverageMatrix } from '../../components/training/CoverageMatrix'
import { rotaNova } from '../RotasNovas'
import * as s from './Cobertura.css'

export function Cobertura() {
  const navigate = useNavigate()

  const onAnnotateCamera = useCallback(
    (cameraId: string) => {
      navigate(rotaNova(`/estudio/dados?camera=${encodeURIComponent(cameraId)}`))
    },
    [navigate],
  )

  const onClassifyCell = useCallback(
    (cameraId: string, classId?: number) => {
      const query = new URLSearchParams({ camera: cameraId })
      if (classId != null) query.set('classe', String(classId))
      navigate(rotaNova(`/estudio/classificar?${query.toString()}`))
    },
    [navigate],
  )

  return (
    <div>
      <div className={s.cabecalho}>
        <h2 className={s.titulo}>Cobertura</h2>
      </div>
      <CoverageMatrix onAnnotateCamera={onAnnotateCamera} onClassifyCell={onClassifyCell} />
    </div>
  )
}
