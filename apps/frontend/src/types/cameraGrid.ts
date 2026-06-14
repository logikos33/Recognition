/** Types for DVR-style camera grid container. */

export interface GridCell {
  position: number
  cameraId: string | null
  colspan?: number
  rowspan?: number
}

export interface GridLayout {
  id: string
  name: string
  columns: number
  rows: number
  cells: GridCell[]
  isBuiltIn: boolean
}

export interface GridPreset {
  id: string
  name: string
  layout: GridLayout
  cameraAssignments: Record<number, string | null> // position -> cameraId
  createdAt?: string
}

/** Built-in layout definitions */
export const BUILT_IN_LAYOUTS: GridLayout[] = [
  {
    id: '1x1',
    name: '1x1',
    columns: 1,
    rows: 1,
    cells: [{ position: 0, cameraId: null }],
    isBuiltIn: true,
  },
  {
    id: '2x2',
    name: '2x2',
    columns: 2,
    rows: 2,
    cells: Array.from({ length: 4 }, (_, i) => ({ position: i, cameraId: null })),
    isBuiltIn: true,
  },
  {
    id: '3x3',
    name: '3x3',
    columns: 3,
    rows: 3,
    cells: Array.from({ length: 9 }, (_, i) => ({ position: i, cameraId: null })),
    isBuiltIn: true,
  },
  {
    id: '4x4',
    name: '4x4',
    columns: 4,
    rows: 4,
    cells: Array.from({ length: 16 }, (_, i) => ({ position: i, cameraId: null })),
    isBuiltIn: true,
  },
  {
    id: '1+5',
    name: '1+5',
    columns: 3,
    rows: 3,
    cells: [
      { position: 0, cameraId: null, colspan: 2, rowspan: 2 },
      { position: 1, cameraId: null },
      { position: 2, cameraId: null },
      { position: 3, cameraId: null },
      { position: 4, cameraId: null },
      { position: 5, cameraId: null },
    ],
    isBuiltIn: true,
  },
  {
    id: '1+7',
    name: '1+7',
    columns: 4,
    rows: 3,
    cells: [
      { position: 0, cameraId: null, colspan: 2, rowspan: 2 },
      { position: 1, cameraId: null },
      { position: 2, cameraId: null },
      { position: 3, cameraId: null },
      { position: 4, cameraId: null },
      { position: 5, cameraId: null },
      { position: 6, cameraId: null },
      { position: 7, cameraId: null },
    ],
    isBuiltIn: true,
  },
]
