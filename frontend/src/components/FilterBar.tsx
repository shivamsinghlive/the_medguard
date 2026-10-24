import { FilterX, Redo2, Undo2, X } from 'lucide-react'
import { hasFilters, type Filters } from '../api'
import { fmtNum } from './ui'

type Props = {
  filters: Filters
  rowCount: number
  totalRows: number
  running: boolean
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  onChange: (next: Filters) => void
}

export default function FilterBar({ filters, rowCount, totalRows, running, canUndo, canRedo, onUndo, onRedo, onChange }: Props) {
  const removeLabel = (column: string, label: string) => {
    const labels = { ...filters.labels, [column]: filters.labels[column].filter((l) => l !== label) }
    if (!labels[column].length) delete labels[column]
    onChange({ ...filters, labels })
  }
  const removeRange = (column: string) => {
    const ranges = { ...filters.ranges }
    delete ranges[column]
    onChange({ ...filters, ranges })
  }
  const share = totalRows ? rowCount / totalRows : 1
  const chip = 'chip border-brand-200 bg-brand-50 text-brand-700'
  return (
    <div className="flex flex-wrap items-center gap-2" data-tour="filters" aria-live="polite">
      <div className="flex min-w-[220px] items-center gap-3">
        <div className="text-sm text-ink-700">Analysing <b className="text-ink-900">{fmtNum(rowCount)}</b> of {fmtNum(totalRows)} rows</div>
        <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-200" aria-hidden>
          <div className={`h-1.5 rounded-full bg-brand-500 transition-[width] duration-500 ${running ? 'animate-pulse' : ''}`} style={{ width: `${share * 100}%` }} />
        </div>
      </div>
      {Object.entries(filters.labels).flatMap(([c, ls]) => ls.map((l) => (
        <span key={`${c}=${l}`} className={chip}>{c} = {l}
          <button onClick={() => removeLabel(c, l)} aria-label={`Remove filter ${c} = ${l}`} className="rounded-full hover:bg-brand-100"><X size={12} /></button></span>
      )))}
      {Object.entries(filters.ranges).map(([c, [lo, hi]]) => (
        <span key={`range-${c}`} className={chip}>{c} {lo}–{hi}
          <button onClick={() => removeRange(c)} aria-label={`Remove range filter on ${c}`} className="rounded-full hover:bg-brand-100"><X size={12} /></button></span>
      ))}
      {filters.rows && (
        <span className={chip}>{filters.rows.source}
          <button onClick={() => onChange({ ...filters, rows: null })} aria-label="Remove row selection" className="rounded-full hover:bg-brand-100"><X size={12} /></button></span>
      )}
      {!hasFilters(filters) && <span className="text-xs text-ink-500">Click bars, drag across a histogram, or select rows on the map to focus everything on a subset.</span>}
      <div className="ml-auto flex items-center gap-1">
        {running && <span className="mr-2 h-2 w-16 rounded-full bg-[linear-gradient(90deg,rgb(var(--slate-200)),rgb(var(--brand-200)),rgb(var(--slate-200)))] bg-[length:400px_100%] animate-shimmer" role="status" aria-label="Recomputing" />}
        <button className="btn-ghost !px-2 !py-1 text-xs" onClick={onUndo} disabled={!canUndo} title="Undo filter change"><Undo2 size={14} />Undo</button>
        <button className="btn-ghost !px-2 !py-1 text-xs" onClick={onRedo} disabled={!canRedo} title="Redo filter change"><Redo2 size={14} />Redo</button>
        {hasFilters(filters) && <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => onChange({ labels: {}, ranges: {}, rows: null })}><FilterX size={14} />Clear all</button>}
      </div>
    </div>
  )
}
