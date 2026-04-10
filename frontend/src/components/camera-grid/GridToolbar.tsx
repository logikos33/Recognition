/**
 * GridToolbar — layout presets, save, fullscreen controls.
 */
import { useState } from 'react'
import { Grid3X3, Save, Maximize, Minimize, Eye, EyeOff, Trash2 } from 'lucide-react'
import { useCameraGridStore } from '../../stores/cameraGridStore'
import { BUILT_IN_LAYOUTS } from '../../types/cameraGrid'
import {
  toolbar, toolbarGroup, toolbarBtn, toolbarBtnActive,
  toolbarSpacer, presetName,
  modalOverlay, modalBox, modalTitle, modalInput, modalActions,
  modalBtnPrimary, modalBtnSecondary,
} from './CameraGrid.css'

interface GridToolbarProps {
  isFullscreen: boolean
  onToggleFullscreen: () => void
}

export function GridToolbar({ isFullscreen, onToggleFullscreen }: GridToolbarProps) {
  const activeLayoutId = useCameraGridStore((s) => s.activeLayoutId)
  const setLayout = useCameraGridStore((s) => s.setLayout)
  const showLabels = useCameraGridStore((s) => s.showLabels)
  const toggleLabels = useCameraGridStore((s) => s.toggleLabels)
  const customPresets = useCameraGridStore((s) => s.customPresets)
  const savePreset = useCameraGridStore((s) => s.savePreset)
  const loadPreset = useCameraGridStore((s) => s.loadPreset)
  const deletePreset = useCameraGridStore((s) => s.deletePreset)

  const [showSaveModal, setShowSaveModal] = useState(false)
  const [newPresetName, setNewPresetName] = useState('')

  const handleSave = () => {
    if (newPresetName.trim()) {
      savePreset(newPresetName.trim())
      setNewPresetName('')
      setShowSaveModal(false)
    }
  }

  return (
    <>
      <div className={toolbar}>
        {/* Layout presets */}
        <div className={toolbarGroup}>
          <Grid3X3 size={14} style={{ color: 'var(--text-muted)', marginRight: 4 }} />
          {BUILT_IN_LAYOUTS.map((layout) => (
            <button
              key={layout.id}
              className={activeLayoutId === layout.id ? toolbarBtnActive : toolbarBtn}
              onClick={() => setLayout(layout.id)}
              aria-label={`Layout ${layout.name}`}
            >
              {layout.name}
            </button>
          ))}
        </div>

        {/* Custom presets */}
        {customPresets.length > 0 && (
          <div className={toolbarGroup}>
            <span className={presetName}>|</span>
            {customPresets.map((p) => (
              <div key={p.id} className={toolbarGroup}>
                <button
                  className={toolbarBtn}
                  onClick={() => loadPreset(p.id)}
                >
                  {p.name}
                </button>
                <button
                  className={toolbarBtn}
                  onClick={() => deletePreset(p.id)}
                  aria-label={`Deletar preset ${p.name}`}
                  style={{ padding: '4px 6px' }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className={toolbarSpacer} />

        {/* Actions */}
        <button className={toolbarBtn} onClick={toggleLabels} aria-label="Toggle labels">
          {showLabels ? <Eye size={14} /> : <EyeOff size={14} />}
        </button>
        <button
          className={toolbarBtn}
          onClick={() => setShowSaveModal(true)}
          aria-label="Salvar preset"
          disabled={customPresets.length >= 10}
        >
          <Save size={14} />
          <span>Salvar</span>
        </button>
        <button className={toolbarBtn} onClick={onToggleFullscreen} aria-label="Fullscreen">
          {isFullscreen ? <Minimize size={14} /> : <Maximize size={14} />}
        </button>
      </div>

      {/* Save Preset Modal */}
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
              onKeyDown={(e) => { if (e.key === 'Enter') handleSave() }}
            />
            <div className={modalActions}>
              <button className={modalBtnSecondary} onClick={() => setShowSaveModal(false)}>
                Cancelar
              </button>
              <button
                className={modalBtnPrimary}
                onClick={handleSave}
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
