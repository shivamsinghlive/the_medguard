import { ChevronDown, HelpCircle, Maximize2, Plus, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { Filters, FocusGroup, Idea, Roles } from '../api'
import Canvas, { ICONS, type Spark } from './Canvas'
import ChangePreview from './ChangePreview'
import StatusStrip from './evidence/StatusStrip'
import FilterBar from './FilterBar'
import { STATUS, StatusBadge, dotColor } from './ui'

type Props = {
  idea: Idea
  dataset: any
  roles: Roles
  results: any
  titles: Record<string, string>
  widgets: string[]
  setWidgets: (w: string[]) => void
  selected: string
  setSelected: (w: string) => void
  onOpen: (w: string) => void
  filters: Filters
  setFilters: (f: Filters) => void
  history: { canUndo: boolean; canRedo: boolean; undo: () => void; redo: () => void }
  focus: FocusGroup[]
  running: boolean
}

const STATUS_ORDER = ['review_needed', 'insufficient_evidence', 'descriptive_only', 'no_patterns_found', 'not_available']
const TILE_WIDGET: Record<string, string> = { Structure: 'validation', Identifiers: 'screening', Quality: 'rows', Representation: 'representation' }

function sparks(results: any): Record<string, Spark> {
  const r = results.readiness, ev = results.evidence
  const funnel = ev.mosaic.funnel
  const top = r.rank?.[0]
  const maxMissing = Math.max(0, ...r.missingness.map((m: any) => m.overall_rate ?? 0))
  return {
    rows: { kind: 'share', value: funnel[funnel.length - 1].rows / Math.max(funnel[0].rows, 1), review: funnel[funnel.length - 1].rows < funnel[0].rows },
    screening: { kind: 'share', value: ev.coverage.percent / 100 },
    outcome: r.outcome ? { kind: 'shares', values: r.outcome.classes.map((c: any) => c.count) } : null,
    representation: ev.cohort.length ? { kind: 'shares', values: ev.cohort[0].groups.map((g: any) => g.count) } : null,
    missingness: r.missingness.length ? { kind: 'share', value: maxMissing, review: true } : null,
    leakage: top ? { kind: 'share', value: top.value, review: top.metric === 'auc' ? top.value >= r.settings.leakage_auc : top.value >= r.settings.leakage_nmi } : null,
    projection: r.projection.points.length ? { kind: 'share', value: r.projection.explained_variance.reduce((a: number, b: number) => a + b, 0) } : null,
  }
}

export default function Workspace(p: Props) {
  const { results } = p
  const board: any[] = results.board
  const [allAnswers, setAllAnswers] = useState(false)
  const answers = useMemo(() => [...results.answers].sort((a: any, b: any) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status)), [results.answers])
  const shownAnswers = allAnswers ? answers : answers.slice(0, 3)
  const cardSparks = useMemo(() => sparks(results), [results])

  return (
    <div className="mx-auto max-w-[1500px] space-y-6 px-4 py-6 sm:px-6">
      <section data-tour="question" className="relative overflow-hidden rounded-3xl bg-[linear-gradient(135deg,#0B1430_0%,#13204A_55%,#24357A_100%)] p-6 text-white shadow-lift sm:p-8">
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-[#2F5BFF]/30 blur-3xl" aria-hidden />
        <div className="pointer-events-none absolute -bottom-28 right-40 h-64 w-64 rounded-full bg-[#13B5A6]/20 blur-3xl" aria-hidden />
        <div className="relative">
          <div className="text-xs font-bold uppercase tracking-[0.14em] text-white/60">{p.idea.title || 'Research question'}</div>
          <h1 className="mt-2 max-w-4xl font-display text-2xl font-bold leading-tight tracking-tight sm:text-3xl">{p.idea.question}</h1>
          <div className="mt-4 flex flex-wrap gap-2 text-xs">
            {results.readiness.roles.outcome && <span className="rounded-full border border-white/20 bg-white/10 px-2.5 py-1">Outcome <b>{results.readiness.roles.outcome}</b></span>}
            {results.readiness.roles.demographics.map((d: string) => <span key={d} className="rounded-full border border-white/20 bg-white/10 px-2.5 py-1">Group <b>{d}</b></span>)}
            <span className="rounded-full border border-white/20 bg-white/10 px-2.5 py-1">{results.dataset.name}</span>
          </div>
        </div>
      </section>

      <div className="sticky top-[61px] z-20 rounded-2xl border border-slate-200 bg-card/95 px-4 py-3 shadow-card backdrop-blur">
        <FilterBar filters={p.filters} onChange={p.setFilters} rowCount={results.subset.row_count} totalRows={results.subset.total_rows}
          running={p.running} canUndo={p.history.canUndo} canRedo={p.history.canRedo} onUndo={p.history.undo} onRedo={p.history.redo} />
      </div>

      <div data-tour="status"><StatusStrip tiles={results.evidence.status_tiles} onOpen={(label) => p.onOpen(TILE_WIDGET[label])} /></div>

      <section aria-labelledby="answers-title">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 id="answers-title" className="flex items-center gap-2 font-display text-lg font-bold text-ink-900"><HelpCircle size={18} className="text-brand-500" />Answers for your research question</h2>
          {answers.length > 3 && <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => setAllAnswers(!allAnswers)}>
            {allAnswers ? 'Show top 3' : `Show all ${answers.length}`}<ChevronDown size={14} className={allAnswers ? 'rotate-180' : ''} /></button>}
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {shownAnswers.map((a: any) => (
            <div key={a.question} className={`card p-4 animate-rise ${a.status === 'review_needed' ? 'border-l-4 border-l-review-500' : ''}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="font-semibold text-ink-900">{a.question}</div>
                <StatusBadge status={a.status} small />
              </div>
              <p className="mt-1.5 text-sm text-ink-700">{a.answer}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_270px]">
        <div>
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-display text-lg font-bold text-ink-900">Workflow</h2>
            <span className="text-xs text-ink-500">Scroll to zoom · drag to pan or rearrange · double-click a card to open it</span>
          </div>
          <Canvas board={board} sparks={cardSparks} selected={p.selected} onSelect={p.setSelected} onOpen={p.onOpen} datasetName={results.dataset.name}
            question={p.idea.title || p.idea.question} rows={`${results.subset.row_count.toLocaleString('en-US')} rows`} />
        </div>
        <aside className="card p-4" data-tour="widgets">
          <h3 className="font-bold text-ink-900">Widgets</h3>
          <p className="mb-3 text-xs text-ink-500">Open, add or remove analysis steps.</p>
          <ul className="space-y-0.5">
            {Object.entries(p.titles).map(([id, title]) => {
              const on = p.widgets.includes(id)
              const Icon = ICONS[id]
              const b = board.find((x) => x.id === id)
              return (
                <li key={id} className={`group flex items-center gap-2 rounded-xl px-2 py-1.5 ${p.selected === id ? 'bg-brand-50' : 'hover:bg-slate-50'}`}>
                  <button className="flex min-w-0 flex-1 items-center gap-2 text-left text-sm" disabled={!on} onClick={() => p.setSelected(id)} onDoubleClick={() => on && p.onOpen(id)}>
                    {Icon && <Icon size={15} className={on ? 'text-ink-700' : 'text-ink-300'} />}
                    <span className={`truncate ${on ? 'font-medium text-ink-900' : 'text-ink-300'}`}>{title}</span>
                    {b && <span className="ml-auto h-2 w-2 shrink-0 rounded-full" style={{ background: dotColor(b.status) }} title={STATUS[b.status]?.label} />}
                  </button>
                  {on && <button className="rounded-lg p-1 text-ink-500 opacity-0 transition hover:bg-slate-200 focus:opacity-100 group-hover:opacity-100" title="Open full screen" aria-label={`Open ${title}`} onClick={() => p.onOpen(id)}><Maximize2 size={13} /></button>}
                  <button className="rounded-lg p-1 text-ink-500 hover:bg-slate-200" title={on ? 'Remove' : 'Add'} aria-label={`${on ? 'Remove' : 'Add'} ${title}`}
                    onClick={() => p.setWidgets(on ? p.widgets.filter((w) => w !== id) : [...p.widgets, id])}>
                    {on ? <X size={14} /> : <Plus size={14} />}
                  </button>
                </li>
              )
            })}
          </ul>
        </aside>
      </section>

      <ChangePreview dataset={p.dataset} roles={p.roles} />

      <details className="card p-5 text-sm text-ink-700">
        <summary className="cursor-pointer font-bold text-ink-900">What this does not tell you ({results.readiness.limitations.length})</summary>
        <ul className="mt-3 list-disc space-y-1 pl-5">{results.readiness.limitations.map((l: string) => <li key={l}>{l}</li>)}</ul>
      </details>
    </div>
  )
}
