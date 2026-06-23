import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { DrawingCanvas } from '../../components/scenario/DrawingCanvas'
import type { Operation, RoiPoint } from '../../types/operations'

beforeEach(() => {
  // Coordenadas previsíveis: canvas virtual de 100×100 em (0,0)
  Element.prototype.getBoundingClientRect = vi.fn(
    () =>
      ({
        left: 0, top: 0, width: 100, height: 100,
        right: 100, bottom: 100, x: 0, y: 0,
        toJSON: () => ({}),
      } as DOMRect)
  )
})

describe('DrawingCanvas', () => {
  it('zone tool: click adiciona ponto normalizado; click perto do primeiro ponto não adiciona (fechamento)', () => {
    const onChange = vi.fn()
    const existingPts: RoiPoint[] = [
      { x: 0.1, y: 0.1 },
      { x: 0.5, y: 0.5 },
      { x: 0.9, y: 0.1 },
    ]
    render(
      <DrawingCanvas
        tool="zone"
        points={existingPts}
        onChange={onChange}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
      />
    )
    const layer = screen.getByTestId('canvas-interaction-layer')

    // Click longe do primeiro ponto → deve adicionar
    fireEvent.click(layer, { clientX: 50, clientY: 90 })
    expect(onChange).toHaveBeenCalledTimes(1)
    const added = onChange.mock.calls[0][0] as RoiPoint[]
    expect(added.length).toBe(4)
    expect(added[3].x).toBeGreaterThanOrEqual(0)
    expect(added[3].x).toBeLessThanOrEqual(1)
    expect(added[3].y).toBeGreaterThanOrEqual(0)
    expect(added[3].y).toBeLessThanOrEqual(1)

    onChange.mockClear()

    // Click (11,11) → normalizado (0.11, 0.11); dist do primeiro (0.1,0.1) ≈ 0.014 < 0.03
    // → NÃO deve adicionar (fechamento de zona)
    fireEvent.click(layer, { clientX: 11, clientY: 11 })
    expect(onChange).not.toHaveBeenCalled()
  })

  it('line tool: clicking após 2 pontos substitui por único ponto novo', () => {
    const onChange = vi.fn()
    render(
      <DrawingCanvas
        tool="line"
        points={[{ x: 0.1, y: 0.1 }, { x: 0.9, y: 0.9 }]}
        onChange={onChange}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
      />
    )
    const layer = screen.getByTestId('canvas-interaction-layer')
    fireEvent.click(layer, { clientX: 50, clientY: 50 })
    expect(onChange).toHaveBeenCalledWith([{ x: 0.5, y: 0.5 }])
  })

  it('point tool: sempre substitui por um único ponto ao clicar', () => {
    const onChange = vi.fn()
    render(
      <DrawingCanvas
        tool="point"
        points={[{ x: 0.1, y: 0.1 }]}
        onChange={onChange}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
      />
    )
    const layer = screen.getByTestId('canvas-interaction-layer')
    fireEvent.click(layer, { clientX: 70, clientY: 30 })
    expect(onChange).toHaveBeenCalledWith([{ x: 0.7, y: 0.3 }])
  })

  it('Ctrl+Z dispara onUndo; Ctrl+Shift+Z dispara onRedo', () => {
    const onUndo = vi.fn()
    const onRedo = vi.fn()
    render(
      <DrawingCanvas
        tool="zone"
        points={[]}
        onChange={vi.fn()}
        onUndo={onUndo}
        onRedo={onRedo}
      />
    )

    fireEvent.keyDown(window, { key: 'z', ctrlKey: true, shiftKey: false })
    expect(onUndo).toHaveBeenCalledTimes(1)
    expect(onRedo).not.toHaveBeenCalled()

    fireEvent.keyDown(window, { key: 'z', ctrlKey: true, shiftKey: true })
    expect(onRedo).toHaveBeenCalledTimes(1)
    expect(onUndo).toHaveBeenCalledTimes(1) // não chamou de novo
  })

  it('operações existentes renderizam polygon/line/circle com cores de status corretas', () => {
    const ops: Operation[] = [
      {
        id: 1, camera_id: 'c1', module_id: 'ppe', type_id: 'zone',
        name: 'Zone', status: 'active', version: 1, created_at: '',
        config: { roi: [{ x: 0.1, y: 0.1 }, { x: 0.5, y: 0.1 }, { x: 0.5, y: 0.5 }] },
      },
      {
        id: 2, camera_id: 'c1', module_id: 'ppe', type_id: 'line',
        name: 'Line', status: 'warning', version: 1, created_at: '',
        config: { roi: [{ x: 0.1, y: 0.1 }, { x: 0.9, y: 0.9 }] },
      },
      {
        id: 3, camera_id: 'c1', module_id: 'ppe', type_id: 'point',
        name: 'Point', status: 'error', version: 1, created_at: '',
        config: { roi: [{ x: 0.5, y: 0.5 }] },
      },
    ]
    const { container } = render(
      <DrawingCanvas
        tool="zone"
        points={[]}
        onChange={vi.fn()}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
        existingOperations={ops}
      />
    )
    const svg = container.querySelector('svg')!

    // Zona (≥3 pts) → polygon
    const polygon = svg.querySelector('polygon')
    expect(polygon).toBeTruthy()
    expect(polygon!.getAttribute('stroke')).toBe('#22c55e') // active

    // Linha (2 pts) → line
    const lineEl = svg.querySelector('line')
    expect(lineEl).toBeTruthy()
    expect(lineEl!.getAttribute('stroke')).toBe('#eab308') // warning

    // Ponto (1 pt) → circle
    const circles = svg.querySelectorAll('circle')
    expect(circles.length).toBeGreaterThanOrEqual(1)
    // O primeiro circle é o do ponto de status error
    const errorCircle = Array.from(circles).find(c => c.getAttribute('stroke') === '#ef4444')
    expect(errorCircle).toBeTruthy()
  })
})
