import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { FocusGroup } from '../api'
import { ICONS } from './Canvas'
import { Findings, StatusBadge, fmtNum, fmtPct } from './ui'
import { ExplainBox, WidgetBody, widgetFindings, type FilterHandlers } from './WidgetPanel'

type Tab = 'chart' | 'table' | 'evidence' | 'limits'
const TABS: { id: Tab; label: string }[] = [
  { id: 'chart', label: 'Chart' }, { id: 'table', label: 'Table' }, { id: 'evidence', label: 'Evidence' }, { id: 'limits', label: 'Limits' },
]

type Props = {
  widget: string
  order: string[]
  titles: Record<string, string>
  results: any
  focus: FocusGroup[]
  handlers: FilterHandlers
  aiOn: boolean
  onExplain: (widget: string) => Promise<any>
  onNavigate: (widget: string) => void
  onClose: () => void
}

/** Plain table behind each chart, so every visual has a text alternative. */
function widgetTable(widget: string, results: any): { columns: string[]; rows: (string | number)[][] } | null {
  const r = results.readiness, ev = results.evidence
  if (widget === 'rows') return { columns: ['Check', 'Rows remaining', 'Rows leaving here', 'Share of rows'], rows: ev.mosaic.funnel.map((f: any) => [f.label, fmtNum(f.rows), fmtNum(f.dropped), `${f.share}%`]) }
  if (widget === 'outcome' && r.outcome) return { columns: ['Class', 'Rows', 'Share'], rows: r.outcome.classes.map((c: any) => [c.label, fmtNum(c.count), fmtPct(c.proportion)]) }
  if (widget === 'representation' && ev.cohort.length) return {
    columns: ['Group', 'Rows', 'Observed share', 'Reference', 'Gap'],
    rows: ev.cohort.flatMap((c: any) => c.groups.map((g: any) => [g.label, fmtNum(g.count), g.observed == null ? '—' : `${g.observed}%`, g.reference == null ? 'not supplied' : `${g.reference}%`, g.gapText ?? '—'])),
  }
  if (widget === 'screening') return { columns: ['Measure', 'Value'], rows: [['Rows value-checked', `${fmtNum(ev.coverage.rowsScanned)} of ${fmtNum(ev.coverage.rowCount)}`], ['Columns name-checked', fmtNum(ev.coverage.columnCount)], ['Checks applied', fmtNum(ev.coverage.checkCount)], ['Matched signals', fmtNum(ev.coverage.matches)]] }
  if (widget === 'missingness' && r.missingness.length) return { columns: ['Column', 'Missing share', 'Largest gap'], rows: r.missingness.map((m: any) => [m.column, fmtPct(m.overall_rate), m.max_gap_pp == null ? '—' : `${m.max_gap_pp.toFixed(1)} pp`]) }
  if (widget === 'leakage' && r.rank.length) return { columns: ['Feature', 'Metric', 'Value', 'Rows'], rows: r.rank.map((x: any) => [x.column, x.metric.toUpperCase(), x.value.toFixed(3), fmtNum(x.rows)]) }
  if (widget === 'correlations' && r.correlations.redundant_pairs.length) return { columns: ['Feature A', 'Feature B', 'r'], rows: r.correlations.redundant_pairs.map((p: any) => [p.a, p.b, p.r.toFixed(3)]) }
  if (widget === 'validation') return { columns: ['Measure', 'Value'], rows: [['Rows', fmtNum(results.validation.row_count)], ['Columns', fmtNum(results.validation.column_count)], ['Bytes', fmtNum(results.validation.byte_count)], ['Status', results.validation.status]] }
  return null
}

function widgetLimits(widget: string, results: any): string[] {
  if (widget === 'screening') return results.screening.limitations
  if (widget === 'representation') return results.representation?.limitations ?? []
  if (widget === 'validation') return results.validation.limitations
  if (widget === 'rows') return ['The funnel counts rows passing each check in sequence; it is a description, not a cleaning recommendation.', 'Duplicates are exact matches across every column; near-duplicates are not detected.', ...results.readiness.limitations.slice(0, 1)]
  return results.readiness.limitations
}

export default function DrillDown({ widget, order, titles, results, focus, handlers, aiOn, onExplain, onNavigate, onClose }: Props) {
  const [tab, setTab] = useState<Tab>('chart')
  const dialog = useRef<HTMLDivElement>(null)
  const card = results.board.find((b: any) => b.id === widget)
  const index = order.indexOf(widget)
  const prev = order[(index - 1 + order.length) % order.length]
  const next = order[(index + 1) % order.length]
  const Icon = ICONS[widget]
  const table = widgetTable(widget, results)
  const findings = widgetFindings(widget, results)

  useEffect(() => { setTab('chart') }, [widget])

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    dialog.current?.focus()
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prevOverflow; opener?.focus?.() }
  }, [])

  // Esc closes even when focus fell back to the page (for example after a filter re-render).
  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return
      if (dialog.current && !dialog.current.contains(document.activeElement)) { onClose(); return }
    }
    addEventListener('keydown', onEsc)
    return () => removeEventListener('keydown', onEsc)
  }, [onClose])

  const onKey = (e: React.KeyboardEvent) => {
    const typing = (e.target as HTMLElement).closest('input, textarea, select, canvas')
    if (e.key === 'Escape') { e.stopPropagation(); onClose(); return }
    if (!typing && e.key === 'ArrowRight' && e.altKey) { onNavigate(next); return }
    if (!typing && e.key === 'ArrowLeft' && e.altKey) { onNavigate(prev); return }
    if (e.key !== 'Tab') return
    const focusable = dialog.current!.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, canvas, [tabindex]:not([tabindex="-1"])')
    const first = focusable[0], last = focusable[focusable.length - 1]
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-stretch justify-center bg-ink-900/40 p-0 backdrop-blur-sm sm:p-6" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby="drill-title" tabIndex={-1} onKeyDown={onKey}
        className="flex w-full max-w-[1280px] flex-col overflow-hidden bg-paper shadow-lift outline-none animate-rise sm:rounded-3xl">
        <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-card px-5 py-3">
          {Icon && <div className="grid h-10 w-10 place-items-center rounded-xl bg-slate-100 text-ink-700"><Icon size={20} /></div>}
          <div className="min-w-0 flex-1">
            <h2 id="drill-title" className="display truncate text-xl">{titles[widget]}</h2>
            <p className="truncate text-sm text-ink-500">{card?.headline}</p>
          </div>
          {card && <StatusBadge status={card.status} />}
          <div className="flex items-center gap-1">
            <button className="btn-ghost !p-2" onClick={() => onNavigate(prev)} title={`Previous: ${titles[prev]} (Alt ←)`} aria-label={`Previous widget: ${titles[prev]}`}><ChevronLeft size={18} /></button>
            <span className="text-xs tabular-nums text-ink-500">{index + 1} / {order.length}</span>
            <button className="btn-ghost !p-2" onClick={() => onNavigate(next)} title={`Next: ${titles[next]} (Alt →)`} aria-label={`Next widget: ${titles[next]}`}><ChevronRight size={18} /></button>
            <button className="btn-ghost !p-2" onClick={onClose} aria-label="Close (Esc)"><X size={18} /></button>
          </div>
          <nav className="flex w-full gap-1" role="tablist" aria-label="Widget views">
            {TABS.map((t) => (
              <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
                className={`rounded-xl px-3 py-1.5 text-sm font-semibold transition ${tab === t.id ? 'bg-ink-900 text-card' : 'text-ink-500 hover:bg-slate-100 hover:text-ink-900'}`}>
                {t.label}{t.id === 'evidence' && findings.length > 0 && <span className="ml-1.5 rounded-full bg-review-100 px-1.5 text-[10px] font-bold text-review-700">{findings.length}</span>}
              </button>
            ))}
          </nav>
        </header>
        <div className="flex-1 overflow-y-auto p-5" role="tabpanel">
          {tab === 'chart' && (
            <div className="space-y-6">
              <div className="card p-5"><WidgetBody widget={widget} results={results} focus={focus} {...handlers} /></div>
              <ExplainBox widget={widget} results={results} onExplain={() => onExplain(widget)} aiOn={aiOn} />
            </div>
          )}
          {tab === 'table' && (table ? (
            <div className="card overflow-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-ink-500"><tr>{table.columns.map((c) => <th key={c} className="px-4 py-2">{c}</th>)}</tr></thead>
                <tbody>{table.rows.map((row, i) => <tr key={i} className="border-t border-slate-100">{row.map((v, j) => <td key={j} className={`px-4 py-2 ${j === 0 ? 'font-semibold text-ink-900' : 'text-ink-700'}`}>{v}</td>)}</tr>)}</tbody>
              </table>
            </div>
          ) : <p className="text-sm text-ink-500">This view is already a table, or has no separate table. Use the Chart tab.</p>)}
          {tab === 'evidence' && (
            <div className="space-y-4">
              <Findings findings={findings} />
              {findings.length > 0 && (
                <details className="card p-4">
                  <summary className="cursor-pointer text-sm font-semibold text-ink-900">Measured evidence (JSON)</summary>
                  <pre className="mt-3 overflow-auto rounded-xl bg-slate-50 p-3 text-xs text-ink-700">{JSON.stringify(findings.map((f: any) => ({ code: f.code, column: f.column, evidence: f.evidence })), null, 2)}</pre>
                </details>
              )}
            </div>
          )}
          {tab === 'limits' && (
            <ul className="card list-disc space-y-2 p-5 pl-10 text-sm text-ink-700">{widgetLimits(widget, results).map((l) => <li key={l}>{l}</li>)}</ul>
          )}
        </div>
      </div>
    </div>
  )
}
