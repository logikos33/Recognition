import { useState, useMemo, type ReactNode } from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { wrapper, table, thead, th, thSortable, td, tr, paginationRow } from './DataTable.css'
import { Skeleton } from '../Skeleton/Skeleton'
import { EmptyState } from '../EmptyState/EmptyState'
import { Button } from '../Button/Button'

export interface Column<T> {
  key: keyof T | string
  header: string
  sortable?: boolean
  render?: (row: T) => ReactNode
  width?: number | string
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  loading?: boolean
  pageSize?: number
  emptyTitle?: string
  emptyDescription?: string
  rowKey: (row: T) => string | number
}

type SortDir = 'asc' | 'desc' | null

export function DataTable<T extends Record<string, unknown>>({
  columns, data, loading = false, pageSize = 20,
  emptyTitle = 'Nenhum resultado', emptyDescription, rowKey,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<SortDir>(null)
  const [page, setPage] = useState(0)

  const sorted = useMemo(() => {
    if (!sortKey || !sortDir) return data
    return [...data].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey]
      if (av === bv) return 0
      const cmp = String(av) < String(bv) ? -1 : 1
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [data, sortKey, sortDir])

  const paged = sorted.slice(page * pageSize, (page + 1) * pageSize)
  const totalPages = Math.ceil(sorted.length / pageSize)

  function toggleSort(key: string) {
    if (sortKey !== key) { setSortKey(key); setSortDir('asc') }
    else if (sortDir === 'asc') setSortDir('desc')
    else { setSortKey(null); setSortDir(null) }
  }

  if (loading) {
    return (
      <div style={{ padding: 16 }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} variant="text" height={32} style={{ marginBottom: 8 }} />
        ))}
      </div>
    )
  }

  if (!data.length) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />
  }

  return (
    <div className={wrapper}>
      <table className={table}>
        <thead className={thead}>
          <tr>
            {columns.map((col) => {
              const key = String(col.key)
              const isActive = sortKey === key
              return (
                <th
                  key={key}
                  className={col.sortable ? thSortable : th}
                  style={{ width: col.width }}
                  onClick={col.sortable ? () => toggleSort(key) : undefined}
                  aria-sort={isActive ? (sortDir === 'asc' ? 'ascending' : 'descending') : undefined}
                >
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    {col.header}
                    {col.sortable && (
                      isActive
                        ? sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />
                        : <ChevronsUpDown size={12} style={{ opacity: 0.4 }} />
                    )}
                  </span>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {paged.map((row) => (
            <tr key={rowKey(row)} className={tr}>
              {columns.map((col) => (
                <td key={String(col.key)} className={td}>
                  {col.render ? col.render(row) : String(row[String(col.key)] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {totalPages > 1 && (
        <div className={paginationRow}>
          <span>{sorted.length} registros</span>
          <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <Button variant="ghost" size="sm" onClick={() => setPage(p => p - 1)} disabled={page === 0}>‹</Button>
            <span>{page + 1} / {totalPages}</span>
            <Button variant="ghost" size="sm" onClick={() => setPage(p => p + 1)} disabled={page >= totalPages - 1}>›</Button>
          </span>
        </div>
      )}
    </div>
  )
}
