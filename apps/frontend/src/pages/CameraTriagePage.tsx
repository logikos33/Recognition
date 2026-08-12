/**
 * CameraTriagePage — triagem dos 29 canais do gravador da RVB.
 *
 * Contexto (ver prompt da task): canais 1-8 já ativos, canais 9-29 recém
 * cadastrados como draft (is_active=false). O Vitor olha a imagem de cada
 * canal novo, renomeia com nome de lugar, ativa os que servem e arquiva os
 * demais. Regras duras:
 *   - arquivar NUNCA apaga (só is_active=false — reversível);
 *   - preview mostra UMA câmera por vez (ativar as 29 juntas derruba o edge);
 *   - toda câmera tem badge de posição não confirmada até alguém conferir na
 *     fábrica (position_confirmed nasce false para todas, inclusive as 8
 *     originais — nenhuma foi conferida ainda).
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { cameraService } from '../services/cameraService'
import { CameraPlayer } from '../components/monitoring/CameraPlayer'
import { CameraSnapshotThumbnail, CameraSnapshotViewer } from '../components/CameraSnapshotThumbnail'
import { useLiveView } from '../hooks/useLiveView'
import { Badge } from '../components/ui/Badge/Badge'
import { Button } from '../components/ui/Button/Button'
import { ConfirmDialog } from '../components/ui/ConfirmDialog/ConfirmDialog'
import { Modal } from '../components/ui/Modal/Modal'
import type { Camera } from '../types'
import * as s from './CameraTriagePage.css'

// ── Totalizador de consequência — fórmulas medidas, não estimadas de cabeça ──

// D-74/D-78: 37 Mbps de upload medidos com 8 câmeras no stream principal
// (subtype 0); ~6 Mbps medidos com 8 câmeras no substream (subtype 1).
const UPLOAD_MBPS_PER_MAIN_STREAM = 37 / 8 // 4.63
const UPLOAD_MBPS_PER_SUB_STREAM = 6 / 8 // 0.75

// D-85: ~US$150/mês de egress medido com 8 câmeras no principal; ~US$110/mês
// com 29 câmeras no substream (grade de operação de 8h/dia).
const EGRESS_USD_PER_MAIN_STREAM_MONTH = 150 / 8 // 18.75
const EGRESS_USD_PER_SUB_STREAM_MONTH = 110 / 29 // 3.79 ≈ 3.8

// ⛔ não inventar número: dizer "68% de carga" sem ter medido é pior do que
// admitir que não se sabe. Acima de 8 streams simultâneos no Orin não existe
// medição — a linha abaixo é SEMPRE este texto literal, nunca um percentual.
const ORIN_LOAD_WARNING = '⚠️ não medida acima de 8 streams'

function roundLegible(value: number, decimals: number): number {
  const factor = 10 ** decimals
  return Math.round(value * factor) / factor
}

function isH265(codec: string | null | undefined): boolean {
  return !!codec && codec.toLowerCase().includes('265')
}

export function CameraTriagePage() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [batchIds, setBatchIds] = useState<Set<string>>(new Set())
  const [batchErrorMsg, setBatchErrorMsg] = useState<string | null>(null)
  const [confirmArchiveOpen, setConfirmArchiveOpen] = useState(false)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [savingName, setSavingName] = useState(false)

  const [previewId, setPreviewId] = useState<string | null>(null)
  // Snapshot ampliado (câmeras draft — nunca ativa a câmera, ver
  // CameraSnapshotViewer). Estado independente do preview ao vivo acima:
  // os dois nunca abrem ao mesmo tempo (verImagem fecha um antes do outro).
  const [snapshotModalCameraId, setSnapshotModalCameraId] = useState<string | null>(null)

  const { hlsUrl } = useLiveView(previewId ?? undefined)

  // ── Load ──────────────────────────────────────────────────────────────────

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const list = await cameraService.list()
      setCameras(list)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Erro ao carregar câmeras')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const sortedCameras = useMemo(
    () => [...cameras].sort((a, b) => a.channel - b.channel),
    [cameras],
  )

  // ── Totalizador ──────────────────────────────────────────────────────────

  const ativas = cameras.filter((c) => c.is_active).length
  const altaOp = cameras.filter((c) => c.is_active && c.live_view_subtype === 0).length
  const subOp = ativas - altaOp
  const uploadMbps = roundLegible(
    altaOp * UPLOAD_MBPS_PER_MAIN_STREAM + subOp * UPLOAD_MBPS_PER_SUB_STREAM,
    1,
  )
  const egressUsd = roundLegible(
    altaOp * EGRESS_USD_PER_MAIN_STREAM_MONTH + subOp * EGRESS_USD_PER_SUB_STREAM_MONTH,
    0,
  )

  // ── Seleção ──────────────────────────────────────────────────────────────

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleSelectAll() {
    setSelectedIds((prev) =>
      prev.size === cameras.length ? new Set() : new Set(cameras.map((c) => c.id)),
    )
  }

  // ── Renomear em linha ────────────────────────────────────────────────────

  function startEdit(cam: Camera) {
    setEditingId(cam.id)
    setEditName(cam.name)
  }

  function cancelEdit() {
    setEditingId(null)
  }

  async function saveEdit(id: string) {
    const name = editName.trim()
    if (!name) return
    setSavingName(true)
    try {
      await cameraService.update(id, { name })
      setCameras((prev) => prev.map((c) => (c.id === id ? { ...c, name } : c)))
      setEditingId(null)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Erro ao renomear câmera')
    } finally {
      setSavingName(false)
    }
  }

  // ── Posição confirmada ───────────────────────────────────────────────────

  async function confirmarPosicao(cam: Camera) {
    setCameras((prev) =>
      prev.map((c) => (c.id === cam.id ? { ...c, position_confirmed: true } : c)),
    )
    try {
      await cameraService.update(cam.id, { position_confirmed: true })
    } catch (e) {
      setCameras((prev) =>
        prev.map((c) => (c.id === cam.id ? { ...c, position_confirmed: false } : c)),
      )
      setLoadError(e instanceof Error ? e.message : 'Erro ao confirmar posição')
    }
  }

  // ── Lote: ativar / arquivar ──────────────────────────────────────────────

  const batchBusy = batchIds.size > 0

  async function runBatchUpdate(ids: string[], isActive: boolean) {
    setBatchErrorMsg(null)
    setBatchIds((prev) => {
      const next = new Set(prev)
      ids.forEach((id) => next.add(id))
      return next
    })
    let errors = 0
    // Loop SEQUENCIAL de propósito (não Promise.all) — mesmo padrão de
    // probeSelected em AdminInventoryPage: evita martelar o backend com N
    // requests simultâneas para uma ação em lote do operador.
    for (const id of ids) {
      try {
        await cameraService.update(id, { is_active: isActive })
        setCameras((prev) => prev.map((c) => (c.id === id ? { ...c, is_active: isActive } : c)))
      } catch {
        errors += 1
      } finally {
        setBatchIds((prev) => {
          const next = new Set(prev)
          next.delete(id)
          return next
        })
      }
    }
    if (errors > 0) {
      setBatchErrorMsg(`${errors} câmera(s) não puderam ser atualizadas.`)
    }
    setSelectedIds(new Set())
  }

  async function handleActivateSelected() {
    await runBatchUpdate(Array.from(selectedIds), true)
  }

  function handleArchiveSelected() {
    setConfirmArchiveOpen(true)
  }

  async function confirmArchive() {
    await runBatchUpdate(Array.from(selectedIds), false)
    setConfirmArchiveOpen(false)
  }

  // ── Preview ao vivo — UMA câmera ATIVA por vez (invariante central) ─────
  //
  // Ativar uma câmera draft "temporariamente" pra preview era o
  // comportamento PROIBIDO que este módulo substituiu (mexia no
  // channel_map, ligava o pipeline HLS, deixava estado sujo se a
  // restauração falhasse) — draft nunca mais passa por aqui, ver
  // verImagem()/CameraSnapshotViewer abaixo.

  function fecharPreview() {
    setPreviewId(null)
  }

  function abrirPreviewAoVivo(cam: Camera) {
    if (previewId === cam.id) return // já é o preview aberto
    setSnapshotModalCameraId(null) // invariante: nunca preview + snapshot juntos
    setPreviewId(cam.id)
  }

  // ── "Ver imagem": ativa (câmera ativa) → preview ao vivo; draft → snapshot ──

  function verImagem(cam: Camera) {
    if (cam.is_active) {
      abrirPreviewAoVivo(cam)
      return
    }
    setPreviewId(null) // invariante: nunca preview + snapshot juntos
    setSnapshotModalCameraId(cam.id)
  }

  function fecharSnapshotModal() {
    setSnapshotModalCameraId(null)
  }

  const previewCamera = previewId ? cameras.find((c) => c.id === previewId) ?? null : null
  const snapshotModalCamera = snapshotModalCameraId
    ? cameras.find((c) => c.id === snapshotModalCameraId) ?? null
    : null

  // ── Render ───────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className={s.pageWrapper}>
        <div className={s.loadingText}>Carregando câmeras...</div>
      </div>
    )
  }

  return (
    <div className={s.pageWrapper}>
      <div className={s.pageHeader}>
        <h1 className={s.pageTitle}>Triagem de canais</h1>
        <div className={s.headerCounts}>
          {cameras.length} canais · {ativas} ativas · {cameras.length - ativas} não ativadas
        </div>
        <div className={s.headerNote}>3 canais livres no gravador (30–32)</div>
      </div>

      {loadError && <div className={s.errorBanner}>{loadError}</div>}

      <div className={s.totalizer}>
        <div className={s.totalizerHeadline}>
          {ativas} câmeras ativas · {altaOp} em alta na operação
        </div>
        <div className={s.totalizerRow}>
          <span className={s.totalizerLabel}>Upload estimado</span>
          <span>{uploadMbps} Mbps de 400 disponíveis</span>
        </div>
        <div className={s.totalizerRow}>
          <span className={s.totalizerLabel}>Egress/mês (8h/dia)</span>
          <span>~US$ {egressUsd}</span>
        </div>
        <div className={s.totalizerRow}>
          <span className={s.totalizerLabel}>Carga no Orin</span>
          <span className={s.totalizerWarn}>{ORIN_LOAD_WARNING}</span>
        </div>
      </div>

      {selectedIds.size > 0 && (
        <div className={s.batchBar}>
          <span className={s.batchCount}>{selectedIds.size} selecionada(s)</span>
          <Button size="sm" variant="primary" disabled={batchBusy} onClick={() => void handleActivateSelected()}>
            Ativar ({selectedIds.size})
          </Button>
          <Button size="sm" variant="danger" disabled={batchBusy} onClick={handleArchiveSelected}>
            Arquivar ({selectedIds.size})
          </Button>
        </div>
      )}

      {batchErrorMsg && <div className={s.errorBanner}>{batchErrorMsg}</div>}

      {cameras.length === 0 ? (
        <div className={s.emptyText}>Nenhuma câmera encontrada.</div>
      ) : (
        <div className={s.tableWrapper}>
          <table className={s.table}>
            <thead className={s.thead}>
              <tr>
                <th className={s.th}>
                  <input
                    type="checkbox"
                    aria-label="Selecionar todas"
                    checked={selectedIds.size === cameras.length && cameras.length > 0}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th className={s.th}>Canal</th>
                <th className={s.th}>Miniatura</th>
                <th className={s.th}>Nome</th>
                <th className={s.th}>Posição</th>
                <th className={s.th}>Codec</th>
                <th className={s.th}>Status</th>
                <th className={s.th}>Ação</th>
              </tr>
            </thead>
            <tbody>
              {sortedCameras.map((cam) => (
                <tr
                  key={cam.id}
                  data-testid={`camera-row-${cam.channel}`}
                  className={selectedIds.has(cam.id) ? `${s.tr} ${s.trSelected}` : s.tr}
                >
                  <td className={s.td}>
                    <input
                      type="checkbox"
                      aria-label={`Selecionar câmera ${cam.name}`}
                      checked={selectedIds.has(cam.id)}
                      onChange={() => toggleSelect(cam.id)}
                    />
                  </td>
                  <td className={`${s.td} ${s.channelCell}`}>{cam.channel}</td>
                  <td className={s.td}>
                    <CameraSnapshotThumbnail cameraId={cam.id} />
                  </td>
                  <td className={s.td}>
                    {editingId === cam.id ? (
                      <div className={s.editRow}>
                        <input
                          className={s.editInput}
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          aria-label={`Novo nome do canal ${cam.channel}`}
                        />
                        <button
                          className={s.saveBtn}
                          disabled={savingName}
                          onClick={() => void saveEdit(cam.id)}
                        >
                          {savingName ? 'Salvando...' : 'Salvar'}
                        </button>
                        <button className={s.cancelBtn} onClick={cancelEdit}>
                          Cancelar
                        </button>
                      </div>
                    ) : (
                      <div className={s.nameCell}>
                        <span className={s.nameText}>{cam.name}</span>
                        <button className={s.renameBtn} onClick={() => startEdit(cam)}>
                          Renomear
                        </button>
                      </div>
                    )}
                  </td>
                  <td className={s.td}>
                    <div className={s.positionCell}>
                      {cam.position_confirmed ? (
                        <Badge variant="success">posição confirmada</Badge>
                      ) : (
                        <>
                          <Badge variant="warning">posição não confirmada</Badge>
                          <button
                            className={s.confirmPositionBtn}
                            title="Só marque depois de conferir na fábrica que o canal mostra este lugar"
                            onClick={() => void confirmarPosicao(cam)}
                          >
                            Confirmar posição
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                  <td className={s.td}>
                    {cam.codec_detected ? (
                      <span
                        className={s.codecText}
                        title={
                          isH265(cam.codec_detected)
                            ? 'Principal H265: Firefox/Chromium sem VAAPI não decodifica (D-79) — live view usa substream'
                            : undefined
                        }
                      >
                        {cam.codec_detected}
                      </span>
                    ) : (
                      <span className={s.codecText}>—</span>
                    )}
                  </td>
                  <td className={s.td}>
                    {cam.is_active ? (
                      <Badge variant="success">Ativa</Badge>
                    ) : (
                      <Badge variant="neutral">Não ativada</Badge>
                    )}
                  </td>
                  <td className={s.td}>
                    <button className={s.actionBtn} onClick={() => verImagem(cam)}>
                      Ver imagem
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {previewId && (
        <div className={s.previewPanel}>
          <div className={s.previewHeader}>
            <span className={s.previewTitle}>
              Preview — {previewCamera ? `Canal ${previewCamera.channel} · ${previewCamera.name}` : previewId}
            </span>
            <Button size="sm" variant="ghost" onClick={fecharPreview}>
              Fechar
            </Button>
          </div>

          <div className={s.previewVideoWrap}>
            {hlsUrl ? (
              <CameraPlayer cameraId={previewId} hlsUrl={hlsUrl} width={480} height={270} />
            ) : (
              <div className={s.previewPlaceholder}>Conectando...</div>
            )}
          </div>
        </div>
      )}

      <Modal
        open={snapshotModalCameraId !== null}
        onClose={fecharSnapshotModal}
        title={
          snapshotModalCamera
            ? `Snapshot — Canal ${snapshotModalCamera.channel} · ${snapshotModalCamera.name}`
            : 'Snapshot'
        }
      >
        {snapshotModalCameraId && <CameraSnapshotViewer cameraId={snapshotModalCameraId} />}
      </Modal>

      <ConfirmDialog
        open={confirmArchiveOpen}
        onClose={() => setConfirmArchiveOpen(false)}
        onConfirm={() => void confirmArchive()}
        title={`Arquivar ${selectedIds.size} câmera(s)?`}
        description="Arquivar tira a câmera da operação (não transmite, não coleta, não infere). Nada é apagado — dá para reativar depois."
        confirmLabel="Arquivar"
        variant="danger"
        loading={batchBusy}
      />
    </div>
  )
}

export default CameraTriagePage
