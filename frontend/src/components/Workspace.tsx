import { FilterX, HelpCircle, Plus, RefreshCw, X } from 'lucide-react'
import type { FocusGroup, Idea } from '../api'
import Canvas, { ICONS } from './Canvas'
import { STATUS, Spinner, StatusBadge, fmtNum } from './ui'
import WidgetPanel from './WidgetPanel'

type Props = {
  idea: Idea
  results: any
  titles: Record<string, string>
  widgets: string[]
  setWidgets: (w: string[]) => void
  selected: string
  setSelected: (w: string) => void
  filters: Record<string, string[]>
  setFilters: (f: Record<string, string[]>) => void
  focus: FocusGroup[]
  running: boolean
  aiOn: boolean
  onExplain: (widget: string) => Promise<any>
}

export default function Workspace(p: Props) {
  const { results } = p
  const board: any[] = results.board
  const card = board.find((b) => b.id === p.selected)
  const addFilter = (column: string, label: string) => {
    if (!column || label == null) return
    const current = p.filters[column] ?? []
    if (current.includes(label)) return
    p.setFilters({ ...p.filters, [column]: [...current, label] })
  }
  const removeFilter = (column: string, label: string) => {
    const next = { ...p.filters, [column]: (p.filters[column] ?? []).filter((l) => l !== label) }
    if (!next[column].length) delete next[column]
    p.setFilters(next)
  }
  const filtered = Object.keys(p.filters).length > 0
  const counts: Record<string, number> = {}
  board.forEach((b) => { counts[b.status] = (counts[b.status] ?? 0) + 1 })

  return (
    <div className="mx-auto max-w-[1500px] space-y-6 px-6 py-6">
      <section className="card overflow-hidden">
        <div className="bg-gradient-to-r from-brand-600 via-indigo-600 to-violet-600 px-6 py-5 text-white">
          <div className="text-xs font-semibold uppercase tracking-widest text-white/70">{p.idea.title || 'Research question'}</div>
          <div className="mt-1 text-xl font-bold leading-snug">{p.idea.question}</div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            {results.readiness.roles.outcome && <span className="rounded-full bg-white/15 px-2.5 py-1">Outcome: <b>{results.readiness.roles.outcome}</b></span>}
            {results.readiness.roles.demographics.map((d: string) => <span key={d} className="rounded-full bg-white/15 px-2.5 py-1">Group: <b>{d}</b></span>)}
            <span className="rounded-full bg-white/15 px-2.5 py-1">{results.dataset.name}</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3 px-6 py-3">
          <div className="text-sm text-ink-700">
            Analysing <b>{fmtNum(results.subset.row_count)}</b> of {fmtNum(results.subset.total_rows)} rows
          </div>
          {Object.entries(p.filters).flatMap(([c, ls]) => ls.map((l) => (
            <span key={c + l} className="chip border-brand-200 bg-brand-50 text-brand-700">{c} = {l}
              <button onClick={() => removeFilter(c, l)} aria-label={`Remove filter ${c} ${l}`}><X size={12} /></button></span>
          )))}
          {filtered && <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => p.setFilters({})}><FilterX size={14} />Clear filters</button>}
          {!filtered && <span className="text-xs text-ink-500">Tip: click bars in charts to focus on a group or class.</span>}
          {p.running && <span className="ml-auto"><Spinner label="Recomputing…" /></span>}
          <div className="ml-auto flex gap-2">
            {Object.entries(counts).map(([s, n]) => <span key={s} className="chip border-slate-200 bg-white text-slate-600"><span className="h-2 w-2 rounded-full" style={{ background: STATUS[s]?.dot }} />{n} {STATUS[s]?.label.toLowerCase()}</span>)}
          </div>
        </div>
      </section>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-lg font-bold text-ink-900"><HelpCircle size={18} className="text-brand-500" />Answers for your research question</h2>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {results.answers.map((a: any) => (
            <div key={a.question} className={`card border-l-4 p-4`} style={{ borderLeftColor: STATUS[a.status]?.dot }}>
              <div className="flex items-start justify-between gap-2">
                <div className="font-semibold text-ink-900">{a.question}</div>
                <StatusBadge status={a.status} small />
              </div>
              <p className="mt-1.5 text-sm text-ink-700">{a.answer}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_260px]">
        <div>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-lg font-bold text-ink-900">Workflow</h2>
            <span className="text-xs text-ink-500">Drag to rearrange · click a widget to open it below</span>
          </div>
          <Canvas board={board} selected={p.selected} onSelect={p.setSelected} datasetName={results.dataset.name}
            question={p.idea.title || p.idea.question} rows={`${fmtNum(results.subset.row_count)} rows`} />
        </div>
        <aside className="card p-4">
          <h3 className="mb-1 font-bold text-ink-900">Widgets</h3>
          <p className="mb-3 text-xs text-ink-500">Add or remove analysis steps.</p>
          <div className="space-y-1">
            {Object.entries(p.titles).map(([id, title]) => {
              const on = p.widgets.includes(id)
              const Icon = ICONS[id]
              const b = board.find((x) => x.id === id)
              return (
                <div key={id} className={`flex items-center gap-2 rounded-xl px-2 py-1.5 ${p.selected === id ? 'bg-brand-50' : 'hover:bg-slate-50'}`}>
                  <button className="flex min-w-0 flex-1 items-center gap-2 text-left text-sm" disabled={!on} onClick={() => p.setSelected(id)}>
                    {Icon && <Icon size={15} className={on ? 'text-brand-600' : 'text-slate-300'} />}
                    <span className={`truncate ${on ? 'font-medium text-ink-900' : 'text-slate-400'}`}>{title}</span>
                    {b && <span className="ml-auto h-2 w-2 shrink-0 rounded-full" style={{ background: STATUS[b.status]?.dot }} />}
                  </button>
                  <button className="rounded-lg p-1 text-ink-500 hover:bg-slate-200" title={on ? 'Remove' : 'Add'}
                    onClick={() => p.setWidgets(on ? p.widgets.filter((w) => w !== id) : [...p.widgets, id])}>
                    {on ? <X size={14} /> : <Plus size={14} />}
                  </button>
                </div>
              )
            })}
          </div>
          <div className="mt-4 rounded-xl bg-slate-50 p-3 text-xs text-ink-500">
            <RefreshCw size={12} className="mr-1 inline" />Every number is recomputed from your file whenever roles, filters or settings change.
          </div>
        </aside>
      </section>

      {card && (
        <WidgetPanel widget={p.selected} title={p.titles[p.selected]} results={results} card={card} focus={p.focus}
          onFilter={addFilter} onExplain={() => p.onExplain(p.selected)} aiOn={p.aiOn} />
      )}

      <section className="card p-5 text-sm text-ink-500">
        <h3 className="mb-2 font-bold text-ink-900">What this does not tell you</h3>
        <ul className="list-disc space-y-1 pl-5">{results.readiness.limitations.map((l: string) => <li key={l}>{l}</li>)}</ul>
      </section>
    </div>
  )
}
