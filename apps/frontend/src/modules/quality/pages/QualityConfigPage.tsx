/**
 * QualityConfigPage — configurações do Quality Gate RVB.
 *
 * Exibe e permite editar:
 *   - Lista de estações (bancadas): tipo de controlador de torre, câmeras
 *   - Padrão OCR (regex de identificação de peça)
 *   - Thresholds de votação por validação (V1/V2/V3)
 *
 * Usa fetch direto com JWT (mesmo padrão das outras páginas do módulo).
 */
import { useState, useEffect } from 'react'
import type { QualityStation, StationCode } from '../types/gate'
import { api } from '../../../services/api'
import { vars } from '../../../styles/theme.css'

// ── Tipos de configuração ─────────────────────────────────────────────────────

interface GateConfig {
  ocr_pattern: string
  voting_threshold_v1: number
  voting_threshold_v2: number
  voting_threshold_v3: number
  frames_per_validation: number
  confidence_min: number
}

interface NewStationForm {
  name: string
  station_code: string
  tower_controller_type: string
  is_active: boolean
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATION_LABELS: Record<StationCode, string> = {
  bench_a: 'Bancada A — V1 e V2',
  bench_b: 'Bancada B — V3',
}

const EMPTY_NEW_STATION: NewStationForm = {
  name: '',
  station_code: '',
  tower_controller_type: 'gpio',
  is_active: true,
}

// ── Componente principal ──────────────────────────────────────────────────────

export function QualityConfigPage() {
  const [stations, setStations] = useState<QualityStation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Estado de edição da configuração global
  const [editConfig, setEditConfig] = useState<GateConfig | null>(null)
  const [configSaving, setConfigSaving] = useState(false)
  const [configSaved, setConfigSaved] = useState(false)

  // Estado de edição de estação individual: station_code → QualityStation editado
  const [editStation, setEditStation] = useState<Partial<QualityStation> | null>(null)
  const [editStationCode, setEditStationCode] = useState<string | null>(null)
  const [stationSaving, setStationSaving] = useState(false)

  // Estado de criação de nova estação
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newStation, setNewStation] = useState<NewStationForm>(EMPTY_NEW_STATION)
  const [createSaving, setCreateSaving] = useState(false)

  // Carrega estações e configurações ao montar
  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const json = await api.get<{ data: { stations: QualityStation[] } }>('/v1/quality/gate/stations')
        setStations(json.data?.stations ?? [])
      } catch (e) {
        setError('Não foi possível carregar as estações.')
        console.error('config_page:load_error', e)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  // Salva configurações globais do gate
  const handleSaveConfig = async () => {
    if (!editConfig) return
    setConfigSaving(true)
    try {
      await api.patch<{ data: GateConfig }>('/v1/quality/gate/config', editConfig)
      setConfigSaved(true)
      setTimeout(() => setConfigSaved(false), 3000)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao salvar configurações.')
      console.error('config_page:save_config_error', e)
    } finally {
      setConfigSaving(false)
    }
  }

  // Abre editor inline de uma estação
  const handleEditStation = (station: QualityStation) => {
    setEditStationCode(station.station_code)
    setEditStation({ ...station })
  }

  // Cancela edição de estação
  const handleCancelStation = () => {
    setEditStationCode(null)
    setEditStation(null)
  }

  // Salva edição de uma estação
  const handleSaveStation = async () => {
    if (!editStation || !editStationCode) return
    setStationSaving(true)
    try {
      const json = await api.patch<{ data: { station: QualityStation } }>(`/v1/quality/gate/stations/${editStationCode}`, editStation)
      setStations(prev =>
        prev.map(s =>
          s.station_code === editStationCode
            ? { ...s, ...json.data?.station }
            : s
        )
      )
      setEditStationCode(null)
      setEditStation(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao salvar estação.')
      console.error('config_page:save_station_error', e)
    } finally {
      setStationSaving(false)
    }
  }

  // Cria nova estação
  const handleCreateStation = async () => {
    if (!newStation.name || !newStation.station_code) return
    setCreateSaving(true)
    try {
      const json = await api.post<{ data: { station: QualityStation } }>('/v1/quality/gate/stations', newStation)
      setStations(prev => [...prev, json.data.station])
      setShowCreateModal(false)
      setNewStation(EMPTY_NEW_STATION)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao criar estação.')
      console.error('config_page:create_station_error', e)
    } finally {
      setCreateSaving(false)
    }
  }

  if (loading) {
    return <div style={{ padding: 32, color: vars.color.textSecondary }}>Carregando configurações...</div>
  }

  return (
    <div style={{ padding: '24px', maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24, color: vars.color.textPrimary }}>
        Configurações — Quality Gate
      </h1>

      {error && (
        <div style={{ padding: '12px 16px', background: vars.color.dangerMuted, borderRadius: 8, color: vars.color.danger, marginBottom: 20 }}>
          {error}
        </div>
      )}

      {/* ── Estações ── */}
      <section style={{ marginBottom: 36 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: vars.color.textPrimary, margin: 0 }}>
            Estações (Bancadas)
          </h2>
          <button
            onClick={() => setShowCreateModal(true)}
            style={{
              padding: '8px 16px', borderRadius: 8, border: 'none',
              background: vars.color.primary, color: vars.color.textOnPrimary, cursor: 'pointer',
              fontSize: 14, fontWeight: 600,
            }}
          >
            + Adicionar estação
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {stations.length === 0 && (
            <div style={{
              padding: 32, textAlign: 'center', border: `2px dashed ${vars.color.borderDefault}`,
              borderRadius: 12, background: vars.color.bgSurface,
            }}>
              <div style={{ fontSize: 14, color: vars.color.textMuted, marginBottom: 12 }}>
                Nenhuma estação configurada.
              </div>
              <button
                onClick={() => setShowCreateModal(true)}
                style={{
                  padding: '8px 20px', borderRadius: 8, border: `1px solid ${vars.color.primary}`,
                  background: vars.color.primaryAlpha, color: vars.color.primary, cursor: 'pointer',
                  fontSize: 14, fontWeight: 600,
                }}
              >
                Criar primeira estação
              </button>
            </div>
          )}

          {stations.map(station => {
            const isEditing = editStationCode === station.station_code
            const editData = isEditing ? editStation! : station

            return (
              <div
                key={station.station_code}
                style={{
                  background: vars.color.bgSurface, border: `1px solid ${vars.color.borderDefault}`,
                  borderRadius: 12, padding: 20,
                }}
              >
                {/* Cabeçalho da estação */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: vars.color.textPrimary }}>
                      {STATION_LABELS[station.station_code as StationCode] ?? station.name}
                    </div>
                    <div style={{ fontSize: 12, color: vars.color.textSecondary, marginTop: 2 }}>
                      {station.station_code}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    {/* Toggle ativo/inativo */}
                    <span
                      style={{
                        padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                        background: station.is_active ? '#D1FAE5' : vars.color.bgSurface,
                        color: station.is_active ? '#059669' : vars.color.textSecondary,
                      }}
                    >
                      {station.is_active ? 'Ativa' : 'Inativa'}
                    </span>
                    {!isEditing && (
                      <button
                        onClick={() => handleEditStation(station)}
                        style={{
                          padding: '6px 14px', borderRadius: 8, border: `1px solid ${vars.color.borderDefault}`,
                          background: vars.color.bgCard, cursor: 'pointer', fontSize: 13, color: vars.color.textPrimary,
                        }}
                      >
                        Editar
                      </button>
                    )}
                  </div>
                </div>

                {/* Campos da estação */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <div>
                    <label
                      htmlFor={`station-${station.station_code}-name`}
                      style={{ fontSize: 12, color: vars.color.textSecondary, fontWeight: 500, display: 'block', marginBottom: 4 }}
                    >
                      Nome da estação
                    </label>
                    {isEditing ? (
                      <input
                        id={`station-${station.station_code}-name`}
                        name={`station-${station.station_code}-name`}
                        type="text"
                        value={editData.name ?? ''}
                        onChange={e => setEditStation(s => ({ ...s, name: e.target.value }))}
                        style={{
                          width: '100%', padding: '8px 12px', borderRadius: 8,
                          border: `1px solid ${vars.color.primary}`, fontSize: 14,
                          background: vars.color.bgCard, boxSizing: 'border-box',
                        }}
                      />
                    ) : (
                      <div style={{ fontSize: 14, color: vars.color.textPrimary }}>{station.name}</div>
                    )}
                  </div>

                  <div>
                    <label
                      htmlFor={`station-${station.station_code}-controller`}
                      style={{ fontSize: 12, color: vars.color.textSecondary, fontWeight: 500, display: 'block', marginBottom: 4 }}
                    >
                      Controlador de torre
                    </label>
                    {isEditing ? (
                      <select
                        id={`station-${station.station_code}-controller`}
                        name={`station-${station.station_code}-controller`}
                        value={editData.tower_controller_type ?? 'gpio'}
                        onChange={e => setEditStation(s => ({ ...s, tower_controller_type: e.target.value }))}
                        style={{
                          width: '100%', padding: '8px 12px', borderRadius: 8,
                          border: `1px solid ${vars.color.primary}`, fontSize: 14, background: vars.color.bgCard,
                        }}
                      >
                        <option value="gpio">GPIO (Raspberry Pi)</option>
                        <option value="modbus">Modbus TCP</option>
                        <option value="mqtt">MQTT</option>
                        <option value="simulated">Simulado (teste)</option>
                      </select>
                    ) : (
                      <div style={{ fontSize: 14, color: vars.color.textPrimary }}>{station.tower_controller_type}</div>
                    )}
                  </div>

                  <div>
                    <label
                      htmlFor={`station-${station.station_code}-overview-cam`}
                      style={{ fontSize: 12, color: vars.color.textSecondary, fontWeight: 500, display: 'block', marginBottom: 4 }}
                    >
                      Câmera overview (ID)
                    </label>
                    {isEditing ? (
                      <input
                        id={`station-${station.station_code}-overview-cam`}
                        name={`station-${station.station_code}-overview-cam`}
                        type="text"
                        value={editData.overview_camera_id ?? ''}
                        onChange={e => setEditStation(s => ({ ...s, overview_camera_id: e.target.value || null }))}
                        placeholder="UUID da câmera"
                        style={{
                          width: '100%', padding: '8px 12px', borderRadius: 8,
                          border: `1px solid ${vars.color.primary}`, fontSize: 14,
                          background: vars.color.bgCard, boxSizing: 'border-box',
                        }}
                      />
                    ) : (
                      <div style={{ fontSize: 14, color: station.overview_camera_id ? vars.color.textPrimary : vars.color.textMuted }}>
                        {station.overview_camera_id ?? 'Não configurada'}
                      </div>
                    )}
                  </div>

                  <div>
                    <label
                      htmlFor={`station-${station.station_code}-closeup-cam`}
                      style={{ fontSize: 12, color: vars.color.textSecondary, fontWeight: 500, display: 'block', marginBottom: 4 }}
                    >
                      Câmera closeup (ID)
                    </label>
                    {isEditing ? (
                      <input
                        id={`station-${station.station_code}-closeup-cam`}
                        name={`station-${station.station_code}-closeup-cam`}
                        type="text"
                        value={editData.closeup_camera_id ?? ''}
                        onChange={e => setEditStation(s => ({ ...s, closeup_camera_id: e.target.value || null }))}
                        placeholder="UUID da câmera"
                        style={{
                          width: '100%', padding: '8px 12px', borderRadius: 8,
                          border: `1px solid ${vars.color.primary}`, fontSize: 14,
                          background: vars.color.bgCard, boxSizing: 'border-box',
                        }}
                      />
                    ) : (
                      <div style={{ fontSize: 14, color: station.closeup_camera_id ? vars.color.textPrimary : vars.color.textMuted }}>
                        {station.closeup_camera_id ?? 'Não configurada'}
                      </div>
                    )}
                  </div>
                </div>

                {/* Botões de ação ao editar */}
                {isEditing && (
                  <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
                    <button
                      onClick={handleCancelStation}
                      style={{
                        padding: '8px 16px', borderRadius: 8, border: `1px solid ${vars.color.borderDefault}`,
                        background: vars.color.bgCard, cursor: 'pointer', fontSize: 14, color: vars.color.textSecondary,
                      }}
                    >
                      Cancelar
                    </button>
                    <button
                      onClick={handleSaveStation}
                      disabled={stationSaving}
                      style={{
                        padding: '8px 20px', borderRadius: 8, border: 'none',
                        background: stationSaving ? vars.color.textSecondary : vars.color.primary,
                        color: vars.color.textPrimary, cursor: stationSaving ? 'not-allowed' : 'pointer',
                        fontSize: 14, fontWeight: 600,
                      }}
                    >
                      {stationSaving ? 'Salvando...' : 'Salvar'}
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      {/* ── Configurações globais do gate ── */}
      {editConfig && (
        <section>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: vars.color.textPrimary, marginBottom: 16 }}>
            Parâmetros de Inspeção
          </h2>

          <div
            style={{
              background: vars.color.bgSurface, border: `1px solid ${vars.color.borderDefault}`,
              borderRadius: 12, padding: 24,
            }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              {/* Padrão OCR */}
              <div style={{ gridColumn: '1 / -1' }}>
                <label
                  htmlFor="gate-ocr-pattern"
                  style={{ fontSize: 13, fontWeight: 600, color: vars.color.textPrimary, display: 'block', marginBottom: 6 }}
                >
                  Padrão OCR (Regex)
                </label>
                <input
                  id="gate-ocr-pattern"
                  name="gate-ocr-pattern"
                  type="text"
                  value={editConfig.ocr_pattern}
                  onChange={e => setEditConfig(c => c ? { ...c, ocr_pattern: e.target.value } : c)}
                  placeholder="Ex: ^[A-Z]{2}-\d{6}$"
                  style={{
                    width: '100%', padding: '10px 14px', borderRadius: 8,
                    border: `1px solid ${vars.color.borderDefault}`, fontSize: 14,
                    background: vars.color.bgCard, boxSizing: 'border-box', fontFamily: 'monospace',
                  }}
                />
                <div style={{ fontSize: 12, color: vars.color.textMuted, marginTop: 4 }}>
                  Expressão regular para validar o número da peça lido pelo OCR.
                </div>
              </div>

              {/* Threshold V1 */}
              <div>
                <label
                  htmlFor="gate-threshold-v1"
                  style={{ fontSize: 13, fontWeight: 600, color: vars.color.textPrimary, display: 'block', marginBottom: 6 }}
                >
                  Threshold V1 (votação)
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <input
                    id="gate-threshold-v1"
                    name="gate-threshold-v1"
                    type="range" min={0.5} max={1} step={0.05}
                    value={editConfig.voting_threshold_v1}
                    onChange={e => setEditConfig(c => c ? { ...c, voting_threshold_v1: parseFloat(e.target.value) } : c)}
                    style={{ flex: 1 }}
                  />
                  <span style={{ fontSize: 14, fontWeight: 600, color: vars.color.warning, minWidth: 40 }}>
                    {(editConfig.voting_threshold_v1 * 100).toFixed(0)}%
                  </span>
                </div>
                <div style={{ fontSize: 12, color: vars.color.textMuted, marginTop: 4 }}>
                  Proporção mínima de frames OK para aprovar em V1.
                </div>
              </div>

              {/* Threshold V2 */}
              <div>
                <label
                  htmlFor="gate-threshold-v2"
                  style={{ fontSize: 13, fontWeight: 600, color: vars.color.textPrimary, display: 'block', marginBottom: 6 }}
                >
                  Threshold V2 (votação)
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <input
                    id="gate-threshold-v2"
                    name="gate-threshold-v2"
                    type="range" min={0.5} max={1} step={0.05}
                    value={editConfig.voting_threshold_v2}
                    onChange={e => setEditConfig(c => c ? { ...c, voting_threshold_v2: parseFloat(e.target.value) } : c)}
                    style={{ flex: 1 }}
                  />
                  <span style={{ fontSize: 14, fontWeight: 600, color: vars.color.primaryDark, minWidth: 40 }}>
                    {(editConfig.voting_threshold_v2 * 100).toFixed(0)}%
                  </span>
                </div>
                <div style={{ fontSize: 12, color: vars.color.textMuted, marginTop: 4 }}>
                  Proporção mínima de frames OK para aprovar em V2.
                </div>
              </div>

              {/* Threshold V3 */}
              <div>
                <label
                  htmlFor="gate-threshold-v3"
                  style={{ fontSize: 13, fontWeight: 600, color: vars.color.textPrimary, display: 'block', marginBottom: 6 }}
                >
                  Threshold V3 (votação)
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <input
                    id="gate-threshold-v3"
                    name="gate-threshold-v3"
                    type="range" min={0.5} max={1} step={0.05}
                    value={editConfig.voting_threshold_v3}
                    onChange={e => setEditConfig(c => c ? { ...c, voting_threshold_v3: parseFloat(e.target.value) } : c)}
                    style={{ flex: 1 }}
                  />
                  <span style={{ fontSize: 14, fontWeight: 600, color: vars.color.primary, minWidth: 40 }}>
                    {(editConfig.voting_threshold_v3 * 100).toFixed(0)}%
                  </span>
                </div>
                <div style={{ fontSize: 12, color: vars.color.textMuted, marginTop: 4 }}>
                  Proporção mínima de frames OK para aprovar em V3.
                </div>
              </div>

              {/* Frames por validação */}
              <div>
                <label
                  htmlFor="gate-frames-per-validation"
                  style={{ fontSize: 13, fontWeight: 600, color: vars.color.textPrimary, display: 'block', marginBottom: 6 }}
                >
                  Frames por Validação
                </label>
                <input
                  id="gate-frames-per-validation"
                  name="gate-frames-per-validation"
                  type="number" min={1} max={30} step={1}
                  value={editConfig.frames_per_validation}
                  onChange={e => setEditConfig(c => c ? { ...c, frames_per_validation: parseInt(e.target.value) || 5 } : c)}
                  style={{
                    width: '100%', padding: '10px 14px', borderRadius: 8,
                    border: `1px solid ${vars.color.borderDefault}`, fontSize: 14,
                    background: vars.color.bgCard, boxSizing: 'border-box',
                  }}
                />
                <div style={{ fontSize: 12, color: vars.color.textMuted, marginTop: 4 }}>
                  Número de frames capturados para calcular a votação.
                </div>
              </div>

              {/* Confiança mínima */}
              <div>
                <label
                  htmlFor="gate-confidence-min"
                  style={{ fontSize: 13, fontWeight: 600, color: vars.color.textPrimary, display: 'block', marginBottom: 6 }}
                >
                  Confiança Mínima YOLO
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <input
                    id="gate-confidence-min"
                    name="gate-confidence-min"
                    type="range" min={0.3} max={0.95} step={0.05}
                    value={editConfig.confidence_min}
                    onChange={e => setEditConfig(c => c ? { ...c, confidence_min: parseFloat(e.target.value) } : c)}
                    style={{ flex: 1 }}
                  />
                  <span style={{ fontSize: 14, fontWeight: 600, color: vars.color.textPrimary, minWidth: 40 }}>
                    {(editConfig.confidence_min * 100).toFixed(0)}%
                  </span>
                </div>
                <div style={{ fontSize: 12, color: vars.color.textMuted, marginTop: 4 }}>
                  Detecções abaixo deste threshold são ignoradas.
                </div>
              </div>
            </div>

            {/* Botão salvar configurações */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24 }}>
              {/* Feedback de sucesso */}
              {configSaved && (
                <span style={{ fontSize: 14, color: vars.color.success, alignSelf: 'center' }}>
                  ✓ Configurações salvas
                </span>
              )}
              <button
                onClick={handleSaveConfig}
                disabled={configSaving}
                style={{
                  padding: '10px 24px', borderRadius: 8, border: 'none',
                  background: configSaving ? vars.color.textSecondary : vars.color.primary,
                  color: vars.color.textPrimary, cursor: configSaving ? 'not-allowed' : 'pointer',
                  fontSize: 15, fontWeight: 600,
                }}
              >
                {configSaving ? 'Salvando...' : 'Salvar Configurações'}
              </button>
            </div>
          </div>
        </section>
      )}

      {/* ── Modal criar estação ── */}
      {showCreateModal && (
        <div
          style={{
            position: 'fixed', inset: 0, background: vars.color.overlay /* TODO-WS1: converter para Modal do kit */,
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          }}
          onClick={e => { if (e.target === e.currentTarget) setShowCreateModal(false) }}
        >
          <div
            style={{
              background: vars.color.bgCard, borderRadius: 16, padding: 32,
              width: 480, boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
            }}
          >
            <h3 style={{ fontSize: 18, fontWeight: 700, color: vars.color.textPrimary, marginBottom: 24, marginTop: 0 }}>
              Adicionar estação
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <label
                  htmlFor="new-station-name"
                  style={{ fontSize: 13, fontWeight: 600, color: vars.color.textPrimary, display: 'block', marginBottom: 6 }}
                >
                  Nome *
                </label>
                <input
                  id="new-station-name"
                  name="new-station-name"
                  type="text"
                  value={newStation.name}
                  onChange={e => setNewStation(s => ({ ...s, name: e.target.value }))}
                  placeholder="Ex: Bancada A"
                  style={{
                    width: '100%', padding: '10px 14px', borderRadius: 8,
                    border: `1px solid ${vars.color.borderDefault}`, fontSize: 14,
                    background: vars.color.bgCard, boxSizing: 'border-box',
                  }}
                  autoFocus
                />
              </div>

              <div>
                <label
                  htmlFor="new-station-code"
                  style={{ fontSize: 13, fontWeight: 600, color: vars.color.textPrimary, display: 'block', marginBottom: 6 }}
                >
                  Código *
                </label>
                <input
                  id="new-station-code"
                  name="new-station-code"
                  type="text"
                  value={newStation.station_code}
                  onChange={e => setNewStation(s => ({ ...s, station_code: e.target.value.toLowerCase().replace(/\s+/g, '_') }))}
                  placeholder="Ex: bench_a"
                  style={{
                    width: '100%', padding: '10px 14px', borderRadius: 8,
                    border: `1px solid ${vars.color.borderDefault}`, fontSize: 14,
                    background: vars.color.bgCard, boxSizing: 'border-box', fontFamily: 'monospace',
                  }}
                />
                <div style={{ fontSize: 12, color: vars.color.textMuted, marginTop: 4 }}>
                  Identificador único da estação. Use snake_case.
                </div>
              </div>

              <div>
                <label
                  htmlFor="new-station-controller"
                  style={{ fontSize: 13, fontWeight: 600, color: vars.color.textPrimary, display: 'block', marginBottom: 6 }}
                >
                  Controlador de torre
                </label>
                <select
                  id="new-station-controller"
                  name="new-station-controller"
                  value={newStation.tower_controller_type}
                  onChange={e => setNewStation(s => ({ ...s, tower_controller_type: e.target.value }))}
                  style={{
                    width: '100%', padding: '10px 14px', borderRadius: 8,
                    border: `1px solid ${vars.color.borderDefault}`, fontSize: 14, background: vars.color.bgCard,
                  }}
                >
                  <option value="gpio">GPIO (Raspberry Pi)</option>
                  <option value="modbus">Modbus TCP</option>
                  <option value="mqtt">MQTT</option>
                  <option value="simulated">Simulado (teste)</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, marginTop: 28, justifyContent: 'flex-end' }}>
              <button
                onClick={() => { setShowCreateModal(false); setNewStation(EMPTY_NEW_STATION) }}
                style={{
                  padding: '10px 20px', borderRadius: 8, border: `1px solid ${vars.color.borderDefault}`,
                  background: vars.color.bgCard, cursor: 'pointer', fontSize: 14, color: vars.color.textSecondary,
                }}
              >
                Cancelar
              </button>
              <button
                onClick={handleCreateStation}
                disabled={createSaving || !newStation.name || !newStation.station_code}
                style={{
                  padding: '10px 24px', borderRadius: 8, border: 'none',
                  background: (createSaving || !newStation.name || !newStation.station_code) ? vars.color.textMuted : vars.color.primary,
                  color: vars.color.textPrimary,
                  cursor: (createSaving || !newStation.name || !newStation.station_code) ? 'not-allowed' : 'pointer',
                  fontSize: 14, fontWeight: 600,
                }}
              >
                {createSaving ? 'Criando...' : 'Criar estação'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
