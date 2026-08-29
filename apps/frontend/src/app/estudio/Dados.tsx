/**
 * Dados — a galeria do Estúdio (`Estúdio.dc.html`, seção "Dados").
 *
 * A ORQUESTRAÇÃO é a da aba Imagens de `pages/TrainingPage.tsx` (fonte da
 * paridade, lida função a função): fila congelada ao abrir o estúdio +
 * reabastecimento com dedup e "2 páginas secas = esgotado" (família do #500),
 * barra de propagação semeada com resurface, e o estúdio de anotação como
 * overlay de tela cheia (`position: fixed` — cobre TopBar e lateral).
 *
 * Os componentes pesados são NÚCLEO COMPARTILHADO (`components/annotation`,
 * `components/training`) — importados como estão, nunca editados daqui: o
 * front antigo continua servindo `/epi/training` com os mesmos módulos.
 *
 * Diferença única desta encarnação: aba virou ROTA. Deep-link entra por query
 * string (`?camera=` / `?status=`), não por callback de outra aba — a matriz
 * de cobertura e o classificador (PRs seguintes) navegam para cá.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { AnnotationStudio } from '../../components/annotation/AnnotationStudio'
import { PropagationStatusBar } from '../../components/annotation/PropagationStatusBar'
import { dismissJob, pickJobToResurface } from '../../components/annotation/propagationUi'
import { anexarSemRepetir } from '../../components/annotation/studioQueue'
import type { StudioFrame } from '../../components/annotation/studioTypes'
import {
  TrainingGallery,
  type ContinuacaoDaFila,
  type StatusFilter,
} from '../../components/training/TrainingGallery'
import { propagationService } from '../../services/propagationService'
import * as s from './Dados.css'

/** Exaustivo de propósito: filtro novo no `TrainingGallery` quebra AQUI em
 * compilação — não vira URL aceita em silêncio nem URL recusada sem aviso. */
const STATUS_DA_URL: Record<StatusFilter, true> = {
  todos: true,
  nao_anotado: true,
  anotado: true,
  duvida: true,
  excluida: true,
  proposta_pendente: true,
}
// `in` enxerga Object.prototype: `'toString' in {}` é true, e o valor herdado
// estouraria em STATUS_LABELS[...] no render da galeria (achado do cético).
const ehStatusFilter = (v: string): v is StatusFilter =>
  Object.prototype.hasOwnProperty.call(STATUS_DA_URL, v)

export function Dados() {
  // ── estúdio de anotação (tela cheia, lista congelada) ────────────────────
  const [studio, setStudio] = useState<{
    frames: StudioFrame[]
    index: number
    continuacao?: ContinuacaoDaFila
  } | null>(null)
  // Cursor do reabastecimento (fora do state: não re-renderiza). `pagina`
  // recomeça na 1 de propósito: com `pending_review`, revisar REMOVE o frame
  // do filtro no servidor e a paginação desliza (família do #500).
  const refillRef = useRef({ pagina: 1, buscando: false, esgotado: false, secas: 0 })

  const pedirMaisFila = useCallback(async () => {
    const r = refillRef.current
    setStudio((atualExterno) => {
      if (!atualExterno?.continuacao || r.buscando || r.esgotado) return atualExterno
      r.buscando = true
      void (async () => {
        try {
          const { frames: novos, temMais } = await atualExterno.continuacao!.buscarPagina(r.pagina)
          setStudio((atual) => {
            if (!atual) return atual
            const fila = anexarSemRepetir(atual.frames, novos)
            const ineditos = fila.length - atual.frames.length
            if (ineditos === 0) {
              // Página sem trabalho novo: avança o cursor. Duas secas seguidas
              // sem `temMais` à frente = fonte esgotada de verdade.
              r.secas += 1
              r.pagina += 1
              if (!temMais && r.secas >= 2) r.esgotado = true
              return atual
            }
            r.secas = 0
            return { ...atual, frames: fila }
          })
        } catch {
          /* rede falhou: não marca esgotado — a próxima passagem re-tenta */
        } finally {
          r.buscando = false
        }
      })()
      return atualExterno
    })
  }, [])

  // Recarrega a galeria quando o estúdio fecha (anotações/curadoria mudaram).
  const [galleryReloadKey, setGalleryReloadKey] = useState(0)
  const [imgTotal, setImgTotal] = useState(0)

  // Pedido de troca de filtro pra galeria — o "Revisar" da propagação semeada.
  const [galleryFilterRequest, setGalleryFilterRequest] =
    useState<{ filter: StatusFilter; nonce: number } | null>(null)
  const requestProposalsFilter = useCallback(() => {
    setGalleryFilterRequest({ filter: 'proposta_pendente', nonce: Date.now() })
  }, [])

  // Foco em câmera vindo de fora (matriz de cobertura, PR seguinte).
  const [galleryCameraFocus, setGalleryCameraFocus] =
    useState<{ cameraId: string; nonce: number } | null>(null)

  // ── deep-link por URL: a aba virou rota ──────────────────────────────────
  const [searchParams] = useSearchParams()
  useEffect(() => {
    const camera = searchParams.get('camera')
    if (camera) setGalleryCameraFocus({ cameraId: camera, nonce: Date.now() })
    const status = searchParams.get('status')
    if (status && ehStatusFilter(status)) {
      setGalleryFilterRequest({ filter: status, nonce: Date.now() })
    }
  }, [searchParams])

  // ── propagação semeada: barra visível fora do estúdio, com resurface ─────
  const [activePropagationJob, setActivePropagationJob] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    void propagationService
      .listJobs()
      .then((jobs) => {
        if (cancelled) return
        const job = pickJobToResurface(jobs)
        if (job) setActivePropagationJob(job.id)
      })
      .catch(() => {
        /* silent — sem job ativo reconstruído, sem problema */
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (studio) {
    return (
      <AnnotationStudio
        frames={studio.frames}
        initialIndex={studio.index}
        onNearEnd={studio.continuacao ? pedirMaisFila : undefined}
        totalDisponivel={studio.continuacao?.totalDoFiltro}
        onExit={() => {
          setStudio(null)
          setGalleryReloadKey((k) => k + 1)
        }}
        onExitToProposals={() => {
          setStudio(null)
          setGalleryReloadKey((k) => k + 1)
          requestProposalsFilter()
        }}
      />
    )
  }

  return (
    <div>
      <div className={s.cabecalho}>
        <h2 className={s.titulo}>Dados{imgTotal > 0 ? ` (${imgTotal})` : ''}</h2>
      </div>
      {activePropagationJob && (
        <div className={s.barraPropagacao}>
          <PropagationStatusBar
            jobId={activePropagationJob}
            onReview={requestProposalsFilter}
            onClose={() => {
              if (activePropagationJob) dismissJob(activePropagationJob)
              setActivePropagationJob(null)
            }}
          />
        </div>
      )}
      <TrainingGallery
        reloadKey={galleryReloadKey}
        onTotalChange={setImgTotal}
        onOpenStudio={(frames, index, continuacao) => {
          refillRef.current = { pagina: 1, buscando: false, esgotado: !continuacao, secas: 0 }
          setStudio({ frames, index, continuacao })
        }}
        statusFilterRequest={galleryFilterRequest}
        cameraFocusRequest={galleryCameraFocus}
      />
    </div>
  )
}
