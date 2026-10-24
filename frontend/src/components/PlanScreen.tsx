import { ArrowRight, Bot, ChevronDown, Fingerprint, Play, Settings2, Target, Users, X } from 'lucide-react'
import { useState } from 'react'
import type { FocusGroup, Roles } from '../api'
import { Note } from './ui'

const SETTING_INFO: Record<string, { label: string; help: string; step: number; pct?: boolean }> = {
  min_cell: { label: 'Smallest acceptable cell', help: 'Flag group x outcome cells with fewer cases than this.', step: 1 },
  imbalance_share: { label: 'Minority-class review share', help: 'Flag when the smallest class is below this share.', step: 0.01, pct: true },
  leakage_auc: { label: 'Leakage AUC', help: 'Flag numeric features whose single-feature AUC reaches this.', step: 0.01 },
  leakage_nmi: { label: 'Leakage NMI', help: 'Flag categorical features explaining this share of the outcome.', step: 0.01 },
  weak_signal_auc: { label: 'Weak-signal AUC', help: 'Note when no single numeric feature reaches this AUC (0.5 = chance).', step: 0.01 },
  missing_gap_pp: { label: 'Missingness gap (pp)', help: 'Flag columns whose missing rate differs by this many points.', step: 1 },
  redundancy_r: { label: 'Redundancy |r|', help: 'Flag numeric pairs correlated at least this strongly.', step: 0.01 },
}

type Props = {
  dataset: any
  plan: any
  titles: Record<string, string>
  roles: Roles
  setRoles: (r: Roles) => void
  focus: FocusGroup[]
  setFocus: (f: FocusGroup[]) => void
  reference: Record<string, Record<string, number>>
  setReference: (r: Record<string, Record<string, number>>) => void
  settings: Record<string, number>
  setSettings: (s: Record<string, number>) => void
  widgets: string[]
  setWidgets: (w: string[]) => void
  onRun: () => void
  running: boolean
}

function SourceTag({ source }: { source?: string }) {
  if (!source) return null
  const ai = source.startsWith('ai')
  return <span className={`chip !py-0 text-[10px] ${ai ? 'border-violet-200 bg-violet-50 text-violet-700' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>{ai ? 'AI' : 'rules'}{source === 'ai+rules' ? ' + rules' : ''}</span>
}

export default function PlanScreen(p: Props) {
  const [advanced, setAdvanced] = useState(false)
  const cols: any[] = p.dataset.columns
  const reasonFor = (list: any[], name: string) => list.find((x) => x.column === name)
  const toggle = (key: 'demographics' | 'identifiers', name: string) => {
    const on = p.roles[key].includes(name)
    const next = { ...p.roles, [key]: on ? p.roles[key].filter((c) => c !== name) : [...p.roles[key], name] }
    if (!on && next.outcome === name) next.outcome = null
    const other = key === 'demographics' ? 'identifiers' : 'demographics'
    next[other] = next[other].filter((c) => c !== name)
    p.setRoles(next)
    if (key === 'demographics' && on) p.setFocus(p.focus.filter((f) => f.column !== name))
  }
  const labelsOf = (name: string): string[] => (cols.find((c) => c.name === name)?.top ?? []).map((t: any) => t.label)

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-ink-900">Here is how we'll analyse your idea.</h1>
          <p className="mt-1 text-ink-500">Every suggestion shows why it was made. Change anything before running.</p>
        </div>
        <span className={`chip !py-1.5 ${p.plan.source === 'ai' ? 'border-violet-200 bg-violet-50 text-violet-700' : 'border-slate-200 bg-white text-slate-600'}`}>
          <Bot size={14} /> {p.plan.source === 'ai' ? `Planned with local AI (${p.plan.ai.model}) + rules` : 'Planned with transparent rules'}
        </span>
      </div>
      <div className="mb-6 space-y-2">
        {p.plan.ai.error && <Note tone="warn">Local AI: {p.plan.ai.error} Rule-based suggestions are shown.</Note>}
        {p.plan.ai.used && <Note>{p.plan.ai.privacy}</Note>}
        {p.plan.notes.map((n: string) => <Note key={n}>{n}</Note>)}
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <section className="card p-5">
          <div className="mb-3 flex items-center gap-2"><Target size={18} className="text-rose-500" /><h2 className="font-bold text-ink-900">Outcome to predict</h2></div>
          <select className="field" value={p.roles.outcome ?? ''} onChange={(e) => {
            const v = e.target.value || null
            p.setRoles({ ...p.roles, outcome: v, demographics: p.roles.demographics.filter((c) => c !== v), identifiers: p.roles.identifiers.filter((c) => c !== v) })
          }}>
            <option value="">— none (skip class balance & leakage) —</option>
            {cols.map((c) => <option key={c.name} value={c.name}>{c.name} · {c.kind} · {c.distinct} values</option>)}
          </select>
          {p.plan.outcome.column && p.roles.outcome === p.plan.outcome.column && (
            <p className="mt-2 flex items-start gap-2 text-sm text-ink-500"><SourceTag source={p.plan.outcome.source} /> {p.plan.outcome.reason}</p>
          )}
          {!p.plan.outcome.column && <p className="mt-2 text-sm text-ink-500">No column clearly matched your outcome; choose one.</p>}
        </section>

        <section className="card p-5">
          <div className="mb-3 flex items-center gap-2"><Fingerprint size={18} className="text-slate-500" /><h2 className="font-bold text-ink-900">Identifier columns</h2></div>
          <div className="flex flex-wrap gap-1.5">
            {cols.filter((c) => c.name !== p.roles.outcome).map((c) => {
              const on = p.roles.identifiers.includes(c.name)
              return <button key={c.name} onClick={() => toggle('identifiers', c.name)}
                className={`chip ${on ? 'border-slate-700 bg-slate-800 text-white' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-400'}`}>{c.name}</button>
            })}
          </div>
          <ul className="mt-3 space-y-1 text-sm text-ink-500">
            {p.roles.identifiers.map((c) => { const r = reasonFor(p.plan.identifiers, c); return r && <li key={c} className="flex gap-2"><SourceTag source={r.source} /><b className="text-ink-700">{c}</b> {r.reason}</li> })}
          </ul>
        </section>

        <section className="card p-5 md:col-span-2">
          <div className="mb-3 flex items-center gap-2"><Users size={18} className="text-violet-500" /><h2 className="font-bold text-ink-900">Population groups</h2></div>
          <div className="flex flex-wrap gap-1.5">
            {cols.filter((c) => c.name !== p.roles.outcome && c.kind === 'categorical' && !p.roles.identifiers.includes(c.name) && !c.id_like).map((c) => {
              const on = p.roles.demographics.includes(c.name)
              return <button key={c.name} onClick={() => toggle('demographics', c.name)}
                className={`chip ${on ? 'border-violet-500 bg-violet-600 text-white' : 'border-slate-200 bg-white text-slate-600 hover:border-violet-400'}`}>{c.name}</button>
            })}
          </div>
          <ul className="mt-3 space-y-1 text-sm text-ink-500">
            {p.roles.demographics.map((c) => { const r = reasonFor(p.plan.demographics, c); return <li key={c} className="flex gap-2">{r ? <><SourceTag source={r.source} /><b className="text-ink-700">{c}</b> {r.reason}</> : <><span className="chip !py-0 text-[10px] border-slate-200">you</span><b className="text-ink-700">{c}</b> added by you</>}</li> })}
          </ul>

          <div className="mt-5 border-t border-slate-100 pt-4">
            <div className="label">Focus groups from your research idea</div>
            {p.focus.length === 0 && <p className="text-sm text-ink-500">None matched. Add one below to get a dedicated answer about it.</p>}
            <div className="flex flex-wrap gap-2">
              {p.focus.map((f, i) => (
                <span key={i} className={`chip !py-1 ${f.missing ? 'border-orange-200 bg-review-50 text-review-700' : 'border-violet-200 bg-violet-50 text-violet-700'}`} title={f.reason}>
                  {f.missing ? `"${f.concept}" not in ${f.column}` : `${f.label} · ${f.column}`}
                  <button onClick={() => p.setFocus(p.focus.filter((_, j) => j !== i))} aria-label="Remove"><X size={12} /></button>
                </span>
              ))}
            </div>
            {p.focus.some((f) => f.missing) && <div className="mt-2"><Note tone="warn">Some groups in your idea have no rows in this dataset. The analysis will say so.</Note></div>}
            {p.roles.demographics.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="text-xs text-ink-500">Add focus:</span>
                {p.roles.demographics.flatMap((c) => labelsOf(c).map((l) => ({ c, l }))).filter(({ c, l }) => !p.focus.some((f) => f.column === c && f.label === l)).slice(0, 16).map(({ c, l }) => (
                  <button key={c + l} className="chip border-dashed border-slate-300 text-slate-600 hover:border-violet-400"
                    onClick={() => p.setFocus([...p.focus, { column: c, label: l, concept: l, missing: false, reason: 'added by you' }])}>+ {l} <span className="opacity-60">({c})</span></button>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>

      <button className="mt-6 flex items-center gap-2 text-sm font-semibold text-ink-700" onClick={() => setAdvanced(!advanced)}>
        <Settings2 size={16} /> Advanced: reference population, review settings, widgets <ChevronDown size={16} className={advanced ? 'rotate-180' : ''} />
      </button>
      {advanced && (
        <div className="mt-3 grid gap-5 md:grid-cols-2">
          <section className="card p-5">
            <h3 className="font-bold text-ink-900">Reference population (optional)</h3>
            <p className="mb-3 text-xs text-ink-500">Enter the shares you expect, for example from census data. Leave blank to report proportions only. Each column must total 100%.</p>
            {p.roles.demographics.map((c) => {
              const ref = p.reference[c] ?? {}
              const total = Object.values(ref).reduce((a, b) => a + b, 0)
              return (
                <div key={c} className="mb-3">
                  <div className="mb-1 flex items-center justify-between text-sm font-semibold text-ink-700">{c}
                    {Object.keys(ref).length > 0 && <span className={`text-xs ${Math.abs(total - 1) < 1e-6 ? 'text-okay-700' : 'text-review-700'}`}>total {(total * 100).toFixed(1)}%</span>}</div>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {labelsOf(c).map((l) => (
                      <label key={l} className="flex items-center gap-1 text-xs text-ink-700">
                        <span className="w-20 truncate" title={l}>{l}</span>
                        <input type="number" min={0} max={100} className="field !px-2 !py-1" placeholder="%"
                          value={ref[l] != null ? +(ref[l] * 100).toFixed(2) : ''}
                          onChange={(e) => {
                            const next = { ...ref }
                            if (e.target.value === '') delete next[l]; else next[l] = Number(e.target.value) / 100
                            const all = { ...p.reference, [c]: next }
                            if (!Object.keys(next).length) delete all[c]
                            p.setReference(all)
                          }} />
                      </label>
                    ))}
                  </div>
                </div>
              )
            })}
            {!p.roles.demographics.length && <p className="text-sm text-ink-500">Select population groups first.</p>}
          </section>
          <section className="card p-5">
            <h3 className="font-bold text-ink-900">Review settings</h3>
            <p className="mb-3 text-xs text-ink-500">These decide when a flag appears. They are adjustable prototype settings, not clinical standards.</p>
            <div className="space-y-3">
              {Object.entries(SETTING_INFO).map(([k, info]) => (
                <label key={k} className="block">
                  <div className="flex justify-between text-sm"><span className="font-semibold text-ink-700">{info.label}</span>
                    <span className="font-mono text-ink-500">{info.pct ? `${(p.settings[k] * 100).toFixed(0)}%` : p.settings[k]}</span></div>
                  <input type="range" className="w-full accent-brand-600" step={info.step}
                    min={0} max={k === 'min_cell' ? 100 : k === 'missing_gap_pp' ? 50 : 1}
                    value={p.settings[k]} onChange={(e) => p.setSettings({ ...p.settings, [k]: Number(e.target.value) })} />
                  <div className="text-xs text-ink-500">{info.help}</div>
                </label>
              ))}
            </div>
          </section>
          <section className="card p-5 md:col-span-2">
            <h3 className="mb-3 font-bold text-ink-900">Widgets in your workflow</h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries(p.titles).map(([id, title]) => {
                const on = p.widgets.includes(id)
                return <button key={id} onClick={() => p.setWidgets(on ? p.widgets.filter((w) => w !== id) : [...p.widgets, id])}
                  className={`chip !py-1.5 ${on ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-slate-200 bg-white text-slate-500'}`}>{title}</button>
              })}
            </div>
          </section>
        </div>
      )}

      <div className="mt-8 flex justify-end">
        <button className="btn-primary !px-6 !py-3 text-base" onClick={p.onRun} disabled={p.running}>
          <Play size={18} /> {p.running ? 'Running…' : 'Run analysis'} <ArrowRight size={18} />
        </button>
      </div>
    </div>
  )
}
