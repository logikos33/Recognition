/**
 * Testes Vitest/RTL para ZoneTuningForm (task-039) — usado no OperationEditModal
 * para editar exclude_zones / day_night_profile de operações epi_zone e defect_trigger.
 */
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ZoneTuningForm } from '../../components/training/operationTypeForms/ZoneTuningForm'

describe('ZoneTuningForm', () => {
  it('renderiza zonas de exclusão existentes do config', () => {
    const config = {
      zone_points: [[0, 0], [1, 0], [1, 1]],
      watch_classes: ['no_helmet'],
      exclude_zones: [[[0.1, 0.1], [0.5, 0.1], [0.3, 0.5]]],
    }
    render(<ZoneTuningForm typeId="epi_zone" config={config} onChange={vi.fn()} />)
    expect(screen.getByTestId('exclude-zone-item-0').textContent).toMatch(/Zona 1.*3 pontos/)
  })

  it('remover zona de exclusão chama onChange sem tocar em outros campos', () => {
    const onChange = vi.fn()
    const config = {
      zone_points: [[0, 0], [1, 0], [1, 1]],
      exclude_zones: [[[0.1, 0.1], [0.5, 0.1], [0.3, 0.5]]],
    }
    render(<ZoneTuningForm typeId="epi_zone" config={config} onChange={onChange} />)
    fireEvent.click(screen.getByLabelText('Remover zona de exclusão 1'))

    expect(onChange).toHaveBeenCalledOnce()
    const [next] = onChange.mock.calls[0]
    expect(next.exclude_zones).toEqual([])
    expect(next.zone_points).toEqual([[0, 0], [1, 0], [1, 1]])
  })

  it('habilitar perfil dia/noite popula defaults 0.5/0.5', () => {
    const onChange = vi.fn()
    render(<ZoneTuningForm typeId="defect_trigger" config={{}} onChange={onChange} />)
    fireEvent.click(screen.getByLabelText('Habilitar perfil dia/noite'))

    expect(onChange).toHaveBeenCalledOnce()
    const [next] = onChange.mock.calls[0]
    expect(next.day_night_profile).toEqual({ day: { confidence: 0.5 }, night: { confidence: 0.5 } })
  })

  it('alterar confidence de dia preserva confidence de noite já configurado', () => {
    const onChange = vi.fn()
    const config = { day_night_profile: { day: { confidence: 0.5 }, night: { confidence: 0.7 } } }
    render(<ZoneTuningForm typeId="epi_zone" config={config} onChange={onChange} />)

    fireEvent.change(screen.getByTestId('day-confidence-input'), { target: { value: '0.3' } })

    const [next] = onChange.mock.calls[0]
    expect(next.day_night_profile).toEqual({ day: { confidence: 0.3 }, night: { confidence: 0.7 } })
  })

  it('confidence fora de [0.1, 1.0] é limitada (validação client-side)', () => {
    const onChange = vi.fn()
    const config = { day_night_profile: { day: { confidence: 0.5 }, night: { confidence: 0.5 } } }
    render(<ZoneTuningForm typeId="epi_zone" config={config} onChange={onChange} />)

    fireEvent.change(screen.getByTestId('night-confidence-input'), { target: { value: '99' } })
    const [next] = onChange.mock.calls[0]
    expect(next.day_night_profile.night.confidence).toBe(1.0)
  })

  it('desabilitar perfil dia/noite remove day_night_profile do config', () => {
    const onChange = vi.fn()
    const config = {
      zone_points: [[0, 0], [1, 0], [1, 1]],
      day_night_profile: { day: { confidence: 0.4 }, night: { confidence: 0.8 } },
    }
    render(<ZoneTuningForm typeId="epi_zone" config={config} onChange={onChange} />)

    fireEvent.click(screen.getByLabelText('Habilitar perfil dia/noite'))
    const [next] = onChange.mock.calls[0]
    expect(next.day_night_profile).toBeUndefined()
    expect(next.zone_points).toEqual([[0, 0], [1, 0], [1, 1]])
  })

  it('JSON avançado inválido exibe erro e não chama onChange', () => {
    const onChange = vi.fn()
    render(<ZoneTuningForm typeId="epi_zone" config={{ zone_points: [] }} onChange={onChange} />)

    fireEvent.change(screen.getByTestId('zone-tuning-advanced-json'), { target: { value: '{ invalid' } })

    expect(onChange).not.toHaveBeenCalled()
    expect(screen.getByRole('alert').textContent).toMatch(/JSON inválido/)
  })

  it('JSON avançado válido atualiza config preservando exclude_zones/day_night_profile atuais', () => {
    const onChange = vi.fn()
    const config = {
      zone_points: [[0, 0], [1, 0], [1, 1]],
      watch_classes: ['no_helmet'],
      exclude_zones: [[[0.1, 0.1], [0.5, 0.1], [0.3, 0.5]]],
    }
    render(<ZoneTuningForm typeId="epi_zone" config={config} onChange={onChange} />)

    fireEvent.change(screen.getByTestId('zone-tuning-advanced-json'), {
      target: { value: JSON.stringify({ zone_points: [[0, 0], [1, 0], [1, 1]], watch_classes: ['no_vest'] }) },
    })

    const [next] = onChange.mock.calls[0]
    expect(next.watch_classes).toEqual(['no_vest'])
    expect(next.exclude_zones).toEqual(config.exclude_zones)
  })
})
