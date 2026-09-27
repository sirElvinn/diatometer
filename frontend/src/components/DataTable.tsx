import { useEffect, useMemo, useState } from 'react'
import { fmt, type Row } from '../api'

interface Props {
  rows: Row[]
  columns: { key: string; label: string }[]
  pageSize?: number
  empty?: string
  /** makes rows clickable: rowKey picks the id passed to onRowClick / matched by selected */
  rowKey?: string
  selected?: string | number | null
  onRowClick?: (key: string | number) => void
}

export default function DataTable({
  rows,
  columns,
  pageSize = 25,
  empty = 'Nothing here.',
  rowKey,
  selected,
  onRowClick,
}: Props) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null)
  const [page, setPage] = useState(0)

  const sorted = useMemo(() => {
    if (!sort) return rows
    return [...rows].sort((a, b) => {
      const x = a[sort.key]
      const y = b[sort.key]
      if (x === y) return 0
      if (x === null || x === undefined) return 1
      if (y === null || y === undefined) return -1
      return (x < y ? -1 : 1) * sort.dir
    })
  }, [rows, sort])

  // jump to the page that holds the selected row (e.g. after clicking it on the image)
  useEffect(() => {
    if (!rowKey || selected == null) return
    const i = sorted.findIndex((r) => r[rowKey] === selected)
    if (i >= 0) setPage(Math.floor(i / pageSize))
  }, [selected, sorted, rowKey, pageSize])

  // a filtered row list can be shorter than the current page
  useEffect(() => {
    setPage((p) => Math.min(p, Math.max(0, Math.ceil(rows.length / pageSize) - 1)))
  }, [rows.length, pageSize])

  const pages = Math.max(1, Math.ceil(sorted.length / pageSize))
  const shown = sorted.slice(page * pageSize, (page + 1) * pageSize)

  if (!rows.length) return <p className="muted">{empty}</p>

  return (
    <div className="table-wrap">
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th
                  key={c.key}
                  onClick={() => {
                    setPage(0)
                    setSort((s) => (s?.key === c.key ? { key: c.key, dir: s.dir === 1 ? -1 : 1 } : { key: c.key, dir: 1 }))
                  }}
                  className={sort?.key === c.key ? 'sorted' : ''}
                >
                  {c.label}
                  {sort?.key === c.key ? (sort.dir === 1 ? ' ▲' : ' ▼') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => {
              const key = rowKey ? (r[rowKey] as string | number) : null
              const isSel = key != null && key === selected
              return (
              <tr
                key={i}
                className={`${onRowClick ? 'clickable' : ''} ${isSel ? 'selected' : ''}`}
                onClick={onRowClick && key != null ? () => onRowClick(key) : undefined}
              >
                {columns.map((c) => (
                  <td key={c.key} className={c.key === 'damage' ? `dmg dmg-${String(r[c.key]).split(' ')[0]}` : ''}>
                    {fmt(r[c.key], 3)}
                  </td>
                ))}
              </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="pager">
          <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            ‹ Prev
          </button>
          <span className="muted small">
            {page * pageSize + 1}–{Math.min((page + 1) * pageSize, sorted.length)} of {sorted.length.toLocaleString()}
          </span>
          <button disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)}>
            Next ›
          </button>
        </div>
      )}
    </div>
  )
}
