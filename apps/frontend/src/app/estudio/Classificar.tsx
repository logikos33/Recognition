/**
 * Classificar — recorte a recorte (`Estúdio.dc.html`), via `CropClassifier`
 * (núcleo compartilhado — o mesmo componente que `pages/TrainingPage.tsx` usa
 * na aba Classificar, importado como está; PR #498 em voo mexe no retry
 * interno dele, mas isso é problema do componente, não deste wrapper).
 *
 * Deep-link de entrada (`?camera=`/`?classe=`, da matriz de Cobertura) vira o
 * foco inicial do classificador. `CropClassifier` só lê esse foco na
 * montagem (não sincroniza por efeito) — por isso a `key={foco.nonce}`: se o
 * link mudar com a tela já aberta, força remontagem em vez de ficar preso no
 * foco antigo.
 *
 * "Ajustar" abre o MESMO `AnnotationStudio` que a aba Dados usa — a conexão é
 * idêntica à de `TrainingPage` (`onOpenAdjust` → `setStudio`), sem fila
 * paginada: o recorte ajustado é uma lista fixa de 1 frame, não a galeria.
 *
 * "Sair para propostas" (`onExitToProposals`, paridade com
 * `TrainingPage.tsx:453`): em vez do callback interno que a aba Dados usa
 * (mesma tela, troca de aba local), aqui é NAVEGAÇÃO — `Classificar` é uma
 * rota própria — para `/estudio/dados?status=proposta_pendente`, que
 * `Dados.tsx` já lê da query string.
 */
import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { AnnotationStudio } from '../../components/annotation/AnnotationStudio'
import { CropClassifier } from '../../components/annotation/CropClassifier'
import type { StudioFrame } from '../../components/annotation/studioTypes'
import { rotaNova } from '../RotasNovas'
import * as s from './Classificar.css'

export function Classificar() {
  const [studio, setStudio] = useState<{ frames: StudioFrame[]; index: number } | null>(null)
  const navigate = useNavigate()

  const [searchParams] = useSearchParams()
  const foco = useMemo(() => {
    const cameraId = searchParams.get('camera')
    const classeRaw = searchParams.get('classe')
    const classId =
      classeRaw !== null && classeRaw !== '' && !Number.isNaN(Number(classeRaw))
        ? Number(classeRaw)
        : null
    return { cameraId, classId, nonce: Date.now() }
  }, [searchParams])

  if (studio) {
    return (
      <AnnotationStudio
        frames={studio.frames}
        initialIndex={studio.index}
        onExit={() => setStudio(null)}
        onExitToProposals={() => {
          setStudio(null)
          navigate(rotaNova('/estudio/dados?status=proposta_pendente'))
        }}
      />
    )
  }

  return (
    <div>
      <div className={s.cabecalho}>
        <h2 className={s.titulo}>Classificar</h2>
      </div>
      <CropClassifier
        key={foco.nonce}
        initialCameraId={foco.cameraId}
        initialClassId={foco.classId}
        onOpenAdjust={(frames, index) => setStudio({ frames, index })}
      />
    </div>
  )
}
