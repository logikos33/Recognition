/**
 * GridPanel — sidebar panel inside the camera grid container.
 * Lists cameras with status, layout presets, custom presets, and new camera wizard trigger.
 */
import { useState, useMemo } from 'react'
import { X, Plus, Search, Save, Trash2 } from 'lucide-react'
import { useCameraGridStore } from '../../stores/cameraGridStore'
import { BUILT_IN_LAYOUTS } from '../../types/cameraGrid'
import { CameraWizard } from '../cameras/CameraWizard'
import type { Camera } from '../../types'
import {
  panelOverlay, panel, panelHeader, panelTitle, panelBody,
  panelSection, panelSectionTitle, panelSearchInput,
  panelCameraItem, panelCameraDot, panelCameraName, panelCameraLocation,
  panelAddBtn, panelPresetGrid, panelPresetBtn, panelPresetBtnActive,
  panelCustomPreset,
  modalOverlay, modalBox, modalTitle, modalInput, modalActions,
  modalBtnPrimary, modalBtnSecondary,
} from './CameraGrid.css'

interface GridPanelProps {
  cameras: Camera[]
  onClose: () => void
  onCamerasChanged: () => void
}

export function GridPanel({ cameras, onClose, onCamerasChanged }: GridPanelProps) {
  const activeLayoutId = useCameraGridStore((s) => s.activeLayoutId)
  const setLayout = useCameraGridStore((s) => s.setLayout)
  const cellAssignments = useCameraGridStore((s) => s.cellAssignments)
  const assignCamera = useCameraGridStore((s) => s.assignCamera)
  const customPresets = useCameraGridStore((s) => s.customPresets)
  const savePreset = useCameraGridStore((s) => s.savePreset)
  const loadPreset = useCameraGridStore((s) => s.loadPreset)
  const deletePreset = useCameraGridStore((s) => s.deletePreset)
  const getActiveLayout = useCameraGridStore((s) => s.getActiveLayout)

  const [search, setSearch] = useState('')
  const [wizardOpen, setWizardOpen] = useState(false)
  const [showSaveModal, setShowSaveModal] = useState(false)
  const [newPresetName, setNewPresetName] = useState('')

  const filtered = useMemo(() => {
    if (!search.trim()) return cameras
    const q = search.toLowerCase()
    return cameras.filter(
      (c) => c.name.toLowerCase().includes(q) || c.location?.toLowerCase().includes(q)
    )
  }, [cameras, search])

  const assignedIds = new Set(Object.values(cellAssignments).filter(Boolean))

  const assignToNextEmpty = (cameraId: string) => {
    const layout = getActiveLayout()
    const totalCells = layout.cells.length
    for (let i = 0; i < totalCells; i++) {
      if (!cellAssignments[i]) {
        assignCamera(i, cameraId)
        return
      }
    }
  }

  const handleSavePreset = () => {
    if (newPresetName.trim()) {
      savePreset(newPresetName.trim())
      setNewPresetName('')
      setShowSaveModal(false)
    }
  }

  return (
    <>
      <div className={panelOverlay} onClick={onClose} />
      <div className={panel}>
        <div className={panelHeader}>
          <span className={panelTitle}>Painel de Controle</span>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: 4 }}
            aria-label="Fechar painel"
          >
            <X size={16} />
          </button>
        </div>

        <div className={panelBody}>
          {/* Search */}
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 8, top: 8, color: 'rgba(255,255,255,0.3)', pointerEvents: 'none' }} />
            <input
              className={panelSearchInput}
              style={{ paddingLeft: 28 }}
              placeholder="Buscar camera..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {/* Camera list */}
          <div className={panelSection}>
            <div className={panelSectionTitle}>Cameras</div>
            {filtered.length === 0 ? (
              <div style={{ padding: '8px', fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>
                Nenhuma camera encontrada
              </div>
            ) : (
              filtered.map((cam) => {
                const isOnline = cam.is_active || cam.stream_status === 'active'
                const isAssigned = assignedIds.has(cam.id)
                return (
                  <button
                    key={cam.id}
                    className={panelCameraItem}
                    onClick={() => !isAssigned && assignToNextEmpty(cam.id)}
                    style={isAssigned ? { opacity: 0.5 } : undefined}
                    title={isAssigned ? 'Ja no grid' : 'Adicionar ao grid'}
                  >
                    <span
                      className={panelCameraDot}
                      style={{ background: isOnline ? '#22c55e' : '#64748b' /* allow: status dot semantics */ }}
                    />
                    <span className={panelCameraName}>{cam.name}</span>
                    {cam.location && (
                      <span className={panelCameraLocation}>{cam.location}</span>
                    )}
                    {!isAssigned && <Plus size={14} style={{ flexShrink: 0, opacity: 0.5 }} />}
                  </button>
                )
              })
            )}
            <button className={panelAddBtn} onClick={() => setWizardOpen(true)}>
              <Plus size={14} /> Nova Camera
            </button>
          </div>

          {/* Layout presets */}
          <div className={panelSection}>
            <div className={panelSectionTitle}>Presets</div>
            <div className={panelPresetGrid}>
              {BUILT_IN_LAYOUTS.map((layout) => (
                <button
                  key={layout.id}
                  className={activeLayoutId === layout.id ? panelPresetBtnActive : panelPresetBtn}
                  onClick={() => setLayout(layout.id)}
                >
                  {layout.name}
                </button>
              ))}
            </div>
          </div>

          {/* Custom presets */}
          <div className={panelSection}>
            <div className={panelSectionTitle}>Meus Presets</div>
            {customPresets.map((p) => (
              <div key={p.id} className={panelCustomPreset}>
                <span onClick={() => loadPreset(p.id)} style={{ flex: 1, cursor: 'pointer' }}>
                  {p.name}
                </span>
                <button
                  onClick={() => deletePreset(p.id)}
                  style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: 2 }}
                  aria-label={`Remover ${p.name}`}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
            <button
              className={panelAddBtn}
              onClick={() => setShowSaveModal(true)}
              disabled={customPresets.length >= 10}
            >
              <Save size={14} /> Salvar Layout Atual
            </button>
          </div>
        </div>
      </div>

      {/* Camera Wizard modal */}
      <CameraWizard
        isOpen={wizardOpen}
        onClose={() => setWizardOpen(false)}
        onSuccess={() => { setWizardOpen(false); onCamerasChanged() }}
      />

      {/* Save preset modal */}
      {showSaveModal && (
        <div className={modalOverlay} onClick={() => setShowSaveModal(false)}>
          <div className={modalBox} onClick={(e) => e.stopPropagation()}>
            <h3 className={modalTitle}>Salvar Preset</h3>
            <input
              className={modalInput}
              value={newPresetName}
              onChange={(e) => setNewPresetName(e.target.value)}
              placeholder="Nome do preset (ex: Portaria + Estoque)"
              maxLength={30}
              autoFocus
              onKeyDown={(e) => { if (e.key === 'Enter') handleSavePreset() }}
            />
            <div className={modalActions}>
              <button className={modalBtnSecondary} onClick={() => setShowSaveModal(false)}>
                Cancelar
              </button>
              <button
                className={modalBtnPrimary}
                onClick={handleSavePreset}
                disabled={!newPresetName.trim()}
              >
                Salvar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
