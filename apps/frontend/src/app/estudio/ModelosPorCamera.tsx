/**
 * ModelosPorCamera — aba "Modelos por câmera" do Estúdio (`Estúdio.dc.html`).
 *
 * O NÚCLEO é `components/training/CameraModelScope` — a mesma aba "modelos" de
 * `pages/TrainingPage.tsx` (`<CameraModelScope classesCatalogo={classes} />`),
 * NÚCLEO COMPARTILHADO: nunca editado daqui, importado como está. Ele já
 * carrega câmeras + modelos + deployments sozinho, e já tem os PRÓPRIOS
 * estados de carregando/erro/vazio internos (loop de câmeras, `Banner` de
 * erro com retry) — duplicar um loader/erro aqui por cima seria dois avisos
 * empilhados para a mesma falha.
 *
 * `classesCatalogo` é só o FALLBACK de nomes de classe quando um modelo não
 * tem `class_distribution` própria (ver doc do componente, linha ~18-24) —
 * é por isso que o antigo (`TrainingPage.tsx`) busca `/classes` em paralelo
 * com os modelos e passa o estado adiante SEM bloquear a aba nisso: um
 * fallback que ainda não chegou não impede a tela de existir. Replicado aqui:
 * busca silenciosa, sem gate próprio de loading/erro por cima do componente.
 */
import { useEffect, useState } from 'react'

import { api } from '../../services/api'
import { CameraModelScope } from '../../components/training/CameraModelScope'
import type { ApiResponse, YoloClass } from '../../types'
import * as s from './ModelosPorCamera.css'

export function ModelosPorCamera() {
  const [classes, setClasses] = useState<YoloClass[]>([])

  useEffect(() => {
    let vivo = true
    api
      .get<ApiResponse<YoloClass[]>>('/classes')
      .then((r) => {
        if (vivo) setClasses(r?.data ?? [])
      })
      .catch(() => {
        /* silencioso — classesCatalogo é só fallback (ver doc acima) */
      })
    return () => {
      vivo = false
    }
  }, [])

  return (
    <div className={s.raiz}>
      <h2 className={s.titulo}>Modelos por câmera</h2>
      <CameraModelScope classesCatalogo={classes} />
    </div>
  )
}
