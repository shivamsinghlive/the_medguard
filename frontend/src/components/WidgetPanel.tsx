import ReactECharts from 'echarts-for-react'
import { Bot, MousePointerClick, Sparkles, Star } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { FocusGroup } from '../api'
import { ICONS } from './Canvas'
import { Findings, Metric, Note, Spinner, StatusBadge, fmtNum, fmtPct } from './ui'

export const PALETTE = ['#3b6cf6', '#f97316', '#10b981', '#a855f7', '#ef4444', '#14b8a6', '#eab308', '#64748b']
const base = { textStyle: { fontFamily: 'Inter, Segoe UI, sans-serif' }, grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true }, tooltip: { trigger: 'axis' as const } }

function Chart({ option, height = 300, onPick }: { option: any; height?: number; onPick?: (p: any) => void }) {
  return <ReactECharts option={{ ...base, ...option }} style={{ height }} notMerge onEvents={onPick ? { click: onPick } : undefined} />
}

function ClickHint() {
  return <p className="flex items-center gap-1 text-xs text-ink-500"><MousePointerClick size={13} /> Click a bar to focus the whole workspace on it.</p>
}

type Props = {
  widget: string
  title: string
  results: any
  card: any
  focus: FocusGroup[]
  onFilter: (column: string, label: string) => void
  onExplain: () => Promise<any>
  aiOn: boolean
}

export default function WidgetPanel({ widget, title, results, card, focus, onFilter, onExplain, aiOn }: Props) {
  const [explanation, setExplanation] = useState<any>(null)
  const [explaining, setExplaining] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { setExplanation(null); setError(null) }, [widget, results])
  const r = results.readiness
  const findings = useMemo(() => {
    if (widget === 'screening') return results.screening.findings
    if (widget === 'representation') return results.representation?.findings ?? []
    const codes: Record<string, string[]> = {
      outcome: ['missing_outcome_labels', 'single_class', 'class_imbalance', 'minority_class_small'], groups: ['small_group_outcome_cells'],
      intersections: ['small_intersection_cells'], leakage: ['possible_leakage'], features: ['constant_feature', 'id_like_feature'],
      missingness: ['missingness_differs'], correlations: ['redundant_features'],
    }
    return r.findings.filter((f: any) => (codes[widget] ?? []).includes(f.code))
  }, [widget, results])
  const Icon = ICONS[widget]

  const explain = async () => {
    setExplaining(true); setError(null)
    try { setExplanation(await onExplain()) } catch (e: any) { setError(e.message) } finally { setExplaining(false) }
  }

  return (
    <section className="card p-6">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {Icon && <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-600"><Icon size={20} /></div>}
          <div>
            <h2 className="text-xl font-bold text-ink-900">{title}</h2>
            <p className="text-sm text-ink-500">{card?.headline}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {card && <StatusBadge status={card.status} />}
          <button className="btn-outline" onClick={explain} disabled={explaining}>
            {aiOn ? <Bot size={16} /> : <Sparkles size={16} />}{explaining ? 'Explaining…' : 'Explain this view'}
          </button>
        </div>
      </div>

      {explaining && <div className="mb-4"><Spinner label={aiOn ? 'Asking the local AI (can take ~15 s)…' : 'Summarising…'} /></div>}
      {error && <div className="mb-4"><Note tone="warn">{error}</Note></div>}
      {explanation && (
        <div className={`mb-5 rounded-2xl border p-4 ${explanation.source === 'ai' ? 'border-violet-200 bg-violet-50/60' : 'border-slate-200 bg-slate-50'}`}>
          <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
            {explanation.source === 'ai' ? <><Bot size={14} className="text-violet-600" /> Local AI wording · unverified, numbers below are computed</> : <><Sparkles size={14} /> Rule-based summary from computed values</>}
          </div>
          <p className="font-semibold text-ink-900">{explanation.summary}</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-ink-700">{explanation.points.map((p: string, i: number) => <li key={i}>{p}</li>)}</ul>
          <p className="mt-2 text-xs text-ink-500">{explanation.caution}</p>
          {explanation.reason && <p className="mt-1 text-xs text-review-700">{explanation.reason}</p>}
        </div>
      )}

      <Body widget={widget} results={results} focus={focus} onFilter={onFilter} />

      <div className="mt-6">
        <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-500">Flags</h3>
        <Findings findings={findings} />
      </div>
    </section>
  )
}

function Body({ widget, results, focus, onFilter }: { widget: string; results: any; focus: FocusGroup[]; onFilter: (c: string, l: string) => void }) {
  const r = results.readiness
  const outcomeCol = r.roles.outcome
  const classes: string[] = r.outcome?.classes.map((c: any) => c.label) ?? []
  const minCell = r.settings.min_cell
  const isFocus = (c: string, l: string) => focus.some((f) => f.column === c && f.label === l)

  if (widget === 'validation') {
    const v = results.validation
    return (
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-4">
          <Metric label="Rows" value={fmtNum(v.row_count)} /><Metric label="Columns" value={v.column_count} />
          <Metric label="File size" value={`${(v.byte_count / 1024).toFixed(0)} KB`} /><Metric label="Status" value={v.status} />
        </div>
        {v.warnings.map((w: any) => <Note key={w.code} tone="warn">{w.message}</Note>)}
        <ul className="list-disc pl-5 text-sm text-ink-500">{v.limitations.map((l: string) => <li key={l}>{l}</li>)}</ul>
      </div>
    )
  }

  if (widget === 'screening') {
    const s = results.screening
    return (
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Metric label="Rows scanned" value={`${fmtNum(s.coverage.rows_scanned)} / ${fmtNum(s.coverage.row_count)}`} hint={s.coverage.complete ? 'complete coverage' : 'partial coverage'} />
          <Metric label="Columns checked" value={s.coverage.column_count} />
          <Metric label="Signals" value={s.findings.length} />
        </div>
        <Note tone="warn">Heuristic screening only. It does not certify de-identification, and matched values are never shown.</Note>
      </div>
    )
  }

  if (widget === 'outcome') {
    const o = r.outcome
    if (!o) return <Note>Choose an outcome column in the plan to see class balance.</Note>
    return (
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-5">
          <Metric label="Labeled rows" value={fmtNum(o.labeled_count)} />
          <Metric label="Missing labels" value={fmtNum(o.missing_count)} />
          <Metric label="Minority share" value={fmtPct(o.minority?.proportion)} hint={o.minority ? `class '${o.minority.label}'` : undefined} />
          <Metric label="Imbalance ratio" value={o.imbalance_ratio ? `1 : ${o.imbalance_ratio}` : '—'} />
          <Metric label="Minority cases / feature" value={r.cases_per_feature ?? '—'} hint="descriptive, not a rule" />
        </div>
        <Chart height={260} onPick={(p) => onFilter(outcomeCol, p.name)} option={{
          tooltip: { trigger: 'item' },
          xAxis: { type: 'category', data: o.classes.map((c: any) => c.label), name: outcomeCol },
          yAxis: { type: 'value', name: 'rows' },
          series: [{ type: 'bar', barMaxWidth: 70, data: o.classes.map((c: any, i: number) => ({ value: c.count, itemStyle: { color: PALETTE[i % PALETTE.length], borderRadius: [8, 8, 0, 0] } })),
            label: { show: true, position: 'top', formatter: (p: any) => `${p.value} (${fmtPct(o.classes[p.dataIndex].proportion)})` } }],
        }} />
        <ClickHint />
      </div>
    )
  }

  if (widget === 'representation') {
    const rep = results.representation
    if (!rep) return <Note>Select population groups in the plan.</Note>
    return (
      <div className="space-y-6">
        {rep.attributes.map((a: any) => {
          const hasRef = a.groups.some((g: any) => g.reference_proportion != null)
          return (
            <div key={a.column}>
              <div className="mb-2 flex items-center gap-2"><b className="text-ink-900">{a.column}</b><StatusBadge status={a.status} small />
                <span className="text-xs text-ink-500">{fmtNum(a.observed_count)} observed · {fmtNum(a.missing_count)} missing</span></div>
              <Chart height={240} onPick={(p) => onFilter(a.column, p.name)} option={{
                legend: { top: 0 }, xAxis: { type: 'category', data: a.groups.map((g: any) => g.label) },
                yAxis: { type: 'value', axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` } },
                series: [{ name: 'Observed share', type: 'bar', barMaxWidth: 48, itemStyle: { color: '#3b6cf6', borderRadius: [6, 6, 0, 0] }, data: a.groups.map((g: any) => g.proportion) },
                  ...(hasRef ? [{ name: 'Your reference', type: 'bar', barMaxWidth: 48, itemStyle: { color: '#cbd5e1', borderRadius: [6, 6, 0, 0] }, data: a.groups.map((g: any) => g.reference_proportion) }] : [])],
              }} />
            </div>
          )
        })}
        <ClickHint />
      </div>
    )
  }

  if (widget === 'groups') {
    if (!r.group_balance.length) return <Note>Needs an outcome and at least one population group.</Note>
    return (
      <div className="space-y-8">
        {r.group_balance.map((g: any) => (
          <div key={g.column}>
            <div className="mb-1 font-bold text-ink-900">{g.column} × {outcomeCol}</div>
            <Chart height={Math.max(180, g.groups.length * 42 + 60)} onPick={(p) => onFilter(g.column, p.name)} option={{
              legend: { top: 0 }, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
              xAxis: { type: 'value', name: 'rows' }, yAxis: { type: 'category', inverse: true, data: g.groups.map((x: any) => x.label) },
              series: classes.map((c, i) => ({ name: `${outcomeCol} = ${c}`, type: 'bar', stack: 'all', barMaxWidth: 28,
                itemStyle: { color: PALETTE[i % PALETTE.length] }, data: g.groups.map((x: any) => x.classes[c]),
                label: { show: true, formatter: (p: any) => (p.value ? p.value : '') } })),
            }} />
            <div className="overflow-auto rounded-xl border border-slate-200">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-ink-500">
                  <tr><th className="px-3 py-2">Group</th><th className="px-3 py-2">Rows</th>{classes.map((c) => <th key={c} className="px-3 py-2">{outcomeCol} = {c}</th>)}<th className="px-3 py-2">No label</th></tr>
                </thead>
                <tbody>
                  {g.groups.map((x: any) => (
                    <tr key={x.label} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-semibold text-ink-900">{isFocus(g.column, x.label) && <Star size={13} className="mr-1 inline fill-violet-500 text-violet-500" />}{x.label}</td>
                      <td className="px-3 py-2">{fmtNum(x.count)}</td>
                      {classes.map((c) => <td key={c} className={`px-3 py-2 ${x.classes[c] < minCell ? 'bg-review-50 font-bold text-review-700' : ''}`}>{fmtNum(x.classes[c])} <span className="text-xs text-ink-500">({fmtPct(x.rates[c])})</span></td>)}
                      <td className="px-3 py-2 text-ink-500">{fmtNum(x.missing_outcome)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
        <p className="text-xs text-ink-500">Orange cells have fewer than {minCell} cases (your setting). <Star size={11} className="inline fill-violet-500 text-violet-500" /> marks focus groups from your research idea.</p>
        <ClickHint />
      </div>
    )
  }

  if (widget === 'intersections') {
    if (!r.intersections.length) return <Note>Select at least two population groups to see combinations.</Note>
    return (
      <div className="space-y-6">
        {r.intersections.map((it: any) => (
          <div key={it.columns.join()}>
            <div className="mb-2 font-bold text-ink-900">{it.columns.join(' × ')} <span className="text-sm font-normal text-ink-500">· {it.small_cells} of {it.cells.length} combinations below {minCell}</span></div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {it.cells.map((c: any) => (
                <div key={c.labels.join()} className={`rounded-xl border p-3 ${c.small ? 'border-orange-200 bg-review-50' : 'border-slate-200 bg-white'}`}>
                  <div className="text-sm font-semibold text-ink-900">{c.labels.join(' · ')}</div>
                  <div className="text-xs text-ink-500">{fmtNum(c.count)} labeled rows</div>
                  <div className="mt-1 flex flex-wrap gap-1">{classes.map((k, i) => <span key={k} className="chip !py-0 text-[11px]" style={{ borderColor: PALETTE[i % 8] + '55', color: PALETTE[i % 8] }}>{k}: {c.classes[k]}</span>)}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (widget === 'leakage') {
    if (!r.rank.length) return <Note>Choose an outcome with at least two classes to rank features.</Note>
    const top = r.rank.slice(0, 15)
    const flagged = (x: any) => (x.metric === 'auc' ? x.value >= r.settings.leakage_auc : x.value >= r.settings.leakage_nmi)
    return (
      <div className="space-y-3">
        <p className="text-sm text-ink-500">How strongly each feature alone separates <b>{outcomeCol}</b>. AUC (numeric features): 0.5 = no signal, 1.0 = perfect. NMI (categorical): share of outcome uncertainty explained. A near-perfect score often means the feature was recorded after, or because of, the outcome.</p>
        <Chart height={Math.max(200, top.length * 30 + 50)} option={{
          tooltip: { trigger: 'item', formatter: (p: any) => `${top[p.dataIndex].column}: ${top[p.dataIndex].metric.toUpperCase()} ${p.value} (${top[p.dataIndex].rows} rows)` },
          xAxis: { type: 'value', min: 0, max: 1 }, yAxis: { type: 'category', inverse: true, data: top.map((x: any) => `${x.column} · ${x.metric.toUpperCase()}`) },
          series: [{ type: 'bar', barMaxWidth: 20, data: top.map((x: any) => ({ value: x.value, itemStyle: { color: flagged(x) ? '#ef4444' : '#3b6cf6', borderRadius: [0, 6, 6, 0] } })),
            label: { show: true, position: 'right', formatter: (p: any) => p.value.toFixed(2) } }],
        }} />
      </div>
    )
  }

  if (widget === 'features') {
    return (
      <div className="max-h-[480px] overflow-auto rounded-xl border border-slate-200">
        <table className="min-w-full text-sm">
          <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase text-ink-500">
            <tr>{['Column', 'Role', 'Kind', 'Missing', 'Distinct', 'Summary', 'Signal'].map((h) => <th key={h} className="px-3 py-2">{h}</th>)}</tr>
          </thead>
          <tbody>
            {r.features.map((f: any) => (
              <tr key={f.column} className="border-t border-slate-100">
                <td className="px-3 py-2 font-semibold text-ink-900">{f.column}
                  {f.constant && <span className="chip ml-1 !py-0 border-slate-200 text-[10px]">constant</span>}
                  {f.id_like && <span className="chip ml-1 !py-0 border-orange-200 text-[10px] text-review-700">ID-like</span>}</td>
                <td className="px-3 py-2 text-ink-500">{f.role}</td>
                <td className="px-3 py-2 text-ink-500">{f.kind}</td>
                <td className="px-3 py-2"><div className="flex items-center gap-2"><div className="h-1.5 w-16 rounded bg-slate-100"><div className="h-1.5 rounded bg-orange-400" style={{ width: `${(f.missing_rate ?? 0) * 100}%` }} /></div>{fmtPct(f.missing_rate)}</div></td>
                <td className="px-3 py-2">{fmtNum(f.distinct)}</td>
                <td className="px-3 py-2 text-xs text-ink-500">{f.stats ? `min ${f.stats.min} · median ${f.stats.median} · max ${f.stats.max}` : f.top?.slice(0, 3).map((t: any) => `${t.label} (${t.count})`).join(', ')}</td>
                <td className="px-3 py-2 text-xs">{f.association ? `${f.association.metric.toUpperCase()} ${f.association.value.toFixed(2)}` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (widget === 'missingness') {
    if (!r.missingness.length) return <Note>No missing values in the current rows.</Note>
    const cols: { key: string; get: (m: any) => number | null }[] = [{ key: 'overall', get: (m) => m.overall_rate }]
    classes.forEach((c) => cols.push({ key: `${outcomeCol}=${c}`, get: (m) => m.by_outcome[c] }))
    r.roles.demographics.forEach((g: string) => {
      const labels = new Set<string>(); r.missingness.forEach((m: any) => Object.keys(m.by_group[g] ?? {}).forEach((l) => labels.add(l)))
      labels.forEach((l) => cols.push({ key: `${g}=${l}`, get: (m) => m.by_group[g]?.[l] ?? null }))
    })
    const data: any[] = []
    r.missingness.forEach((m: any, y: number) => cols.forEach((c, x) => { const v = c.get(m); data.push([x, y, v == null ? '-' : +(v * 100).toFixed(1)]) }))
    return (
      <Chart height={Math.max(220, r.missingness.length * 34 + 110)} option={{
        tooltip: { position: 'top', formatter: (p: any) => `${r.missingness[p.value[1]].column} · ${cols[p.value[0]].key}: ${p.value[2]}% missing` },
        grid: { left: 8, right: 16, top: 10, bottom: 70, containLabel: true },
        xAxis: { type: 'category', data: cols.map((c) => c.key), axisLabel: { rotate: 35 } }, yAxis: { type: 'category', data: r.missingness.map((m: any) => m.column) },
        visualMap: { min: 0, max: 100, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#f0f9ff', '#fdba74', '#c2410c'] } },
        series: [{ type: 'heatmap', data, label: { show: true, formatter: (p: any) => p.value[2] } }],
      }} />
    )
  }

  if (widget === 'correlations') {
    const c = r.correlations
    if (c.columns.length < 2) return <Note>Needs at least two numeric features.</Note>
    const data: any[] = []
    c.matrix.forEach((row: any[], i: number) => row.forEach((v, j) => data.push([j, i, v ?? '-'])))
    return (
      <Chart height={Math.max(300, c.columns.length * 36 + 100)} option={{
        tooltip: { formatter: (p: any) => `${c.columns[p.value[1]]} ~ ${c.columns[p.value[0]]}: r = ${p.value[2]}` },
        grid: { left: 8, right: 16, top: 10, bottom: 70, containLabel: true },
        xAxis: { type: 'category', data: c.columns, axisLabel: { rotate: 35 } }, yAxis: { type: 'category', data: c.columns },
        visualMap: { min: -1, max: 1, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#2645b0', '#f8fafc', '#c2410c'] } },
        series: [{ type: 'heatmap', data, label: { show: c.columns.length <= 12, formatter: (p: any) => (typeof p.value[2] === 'number' ? p.value[2].toFixed(2) : '') } }],
      }} />
    )
  }

  if (widget === 'distributions') return <Distributions r={r} classes={classes} onFilter={onFilter} />

  if (widget === 'projection') {
    const p = r.projection
    if (!p.points.length) return <Note>{p.reason}</Note>
    const seen = new Set(p.points.map((x: any) => x.label) as string[])
    const keys = [...classes.filter((c) => seen.has(c)), ...[...seen].filter((k) => !classes.includes(k))]
    return (
      <div className="space-y-2">
        <p className="text-sm text-ink-500">Each dot is a row, placed by PCA of {p.features.length} numeric features ({p.features.join(', ')}), coloured by {outcomeCol ?? 'nothing'}. Overlapping colours mean these features alone separate the classes poorly. {p.sampled < p.total && `Showing ${p.sampled} of ${p.total} rows.`}</p>
        <Chart height={420} option={{
          tooltip: { trigger: 'item', formatter: (q: any) => `row ${q.data[2]} · ${q.seriesName}` }, legend: { top: 0, right: 0 },
          grid: { left: 40, right: 16, top: 40, bottom: 36, containLabel: true },
          xAxis: { type: 'value', name: `PC1 (${(p.explained_variance[0] * 100).toFixed(0)}% of variance)`, nameLocation: 'middle', nameGap: 28, scale: true },
          yAxis: { type: 'value', name: `PC2 (${(p.explained_variance[1] * 100).toFixed(0)}%)`, nameLocation: 'middle', nameGap: 36, scale: true },
          series: keys.map((k, i) => ({ name: outcomeCol ? `${outcomeCol} = ${k}` : k, type: 'scatter', symbolSize: 6, itemStyle: { color: PALETTE[i % 8], opacity: 0.65 },
            data: p.points.filter((x: any) => x.label === k).map((x: any) => [x.x, x.y, x.row]) })),
        }} />
        <p className="text-xs text-ink-500">{p.note}</p>
      </div>
    )
  }
  return null
}

function Distributions({ r, classes, onFilter }: { r: any; classes: string[]; onFilter: (c: string, l: string) => void }) {
  const names = Object.keys(r.distributions)
  const [col, setCol] = useState(names[0])
  useEffect(() => { if (!names.includes(col)) setCol(names[0]) }, [names.join()])
  const d = r.distributions[col]
  if (!d) return <Note>No distributions available.</Note>
  const keys = Object.keys(d.series)
  const cats = d.kind === 'numeric' ? d.edges.slice(0, -1).map((e: number, i: number) => `${e}–${d.edges[i + 1]}`) : d.labels
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {names.map((n) => <button key={n} onClick={() => setCol(n)} className={`chip ${n === col ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-slate-200 bg-white text-slate-600'}`}>{n}</button>)}
      </div>
      <Chart height={320} onPick={d.kind === 'categorical' ? (p) => p.name !== 'Other' && onFilter(col, p.name) : undefined} option={{
        legend: { top: 0 }, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        xAxis: { type: 'category', data: cats, axisLabel: { rotate: d.kind === 'numeric' ? 30 : 0 } }, yAxis: { type: 'value', name: 'rows' },
        series: keys.map((k, i) => ({ name: classes.length ? `${r.roles.outcome} = ${k}` : k, type: 'bar', stack: d.kind === 'numeric' ? 'all' : undefined,
          barMaxWidth: 40, itemStyle: { color: PALETTE[i % 8] }, data: d.series[k] })),
      }} />
      {d.kind === 'categorical' && <ClickHint />}
    </div>
  )
}
