import { ArrowRight, Database, FileUp, Lightbulb, Sparkles, Table2 } from 'lucide-react'
import { useState } from 'react'
import type { Idea } from '../api'
import { Note, Spinner, fmtNum } from './ui'

const KIND_STYLE: Record<string, string> = {
  numeric: 'border-brand-200 bg-brand-50 text-brand-700',
  categorical: 'border-teal-500/40 bg-teal-50 text-teal-700',
  text: 'border-slate-300 bg-slate-50 text-slate-700',
  datetime: 'border-dashed border-slate-300 bg-card text-slate-700',
}

type Props = {
  idea: Idea
  setIdea: (i: Idea) => void
  demos: { name: string; bytes: number }[]
  dataset: any
  loading: string | null
  onDemo: (name: string) => void
  onUpload: (file: File) => void
  onPlan: () => void
  rejected: any
}

const pretty = (name: string) => name.replace(/\.csv$/, '').replace(/^dataset\d_/, '').replace(/_/g, ' ')

export default function StartScreen({ idea, setIdea, demos, dataset, loading, onDemo, onUpload, onPlan, rejected }: Props) {
  const [dragging, setDragging] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const set = (k: keyof Idea) => (e: any) => setIdea({ ...idea, [k]: e.target.value })
  const ready = idea.question.trim().length > 5 && dataset?.accepted

  return (
    <div className="mx-auto max-w-[1500px] px-6 py-8">
      <div className="mb-8 max-w-3xl">
        <h1 className="text-3xl font-bold tracking-tight text-ink-900">Start with your research idea.</h1>
        <p className="mt-2 text-ink-500">
          Describe what you want to study, load a dataset, and MedGuard builds an analysis around your question:
          class balance, coverage of the groups you care about, leakage, missingness and identifier signals —
          all computed from your file.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
        <section className="card p-6">
          <div className="mb-4 flex items-center gap-2">
            <Lightbulb className="text-brand-500" size={20} />
            <h2 className="text-lg font-bold text-ink-900">1 · Research idea</h2>
          </div>
          <div className="space-y-4">
            <div>
              <label className="label" htmlFor="title">Project title</label>
              <input id="title" className="field" placeholder="e.g. Heart disease risk model for under-served groups"
                value={idea.title} onChange={set('title')} />
            </div>
            <div>
              <label className="label" htmlFor="q">Research question *</label>
              <textarea id="q" rows={3} className="field resize-none"
                placeholder="What do you want to predict or understand, and for whom?"
                value={idea.question} onChange={set('question')} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="label" htmlFor="o">Outcome of interest</label>
                <input id="o" className="field" placeholder="e.g. heart disease, diabetes, readmission"
                  value={idea.outcome} onChange={set('outcome')} />
              </div>
              <div>
                <label className="label" htmlFor="p">Intended population</label>
                <input id="p" className="field" placeholder="e.g. adults in US primary care"
                  value={idea.population} onChange={set('population')} />
              </div>
            </div>
            <div>
              <label className="label" htmlFor="g">Groups you are concerned about</label>
              <input id="g" className="field" placeholder="e.g. women, Black patients, Indigenous patients, older adults"
                value={idea.groups} onChange={set('groups')} />
              <p className="mt-1 text-xs text-ink-500">Used to find matching columns and values in your data, and to flag groups that are missing.</p>
            </div>
          </div>
        </section>

        <section className="card p-6">
          <div className="mb-4 flex items-center gap-2">
            <Database className="text-brand-500" size={20} />
            <h2 className="text-lg font-bold text-ink-900">2 · Dataset</h2>
          </div>

          <label
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files?.[0]; if (f) onUpload(f) }}
            className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-4 py-7 text-center transition ${dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 hover:border-brand-500 hover:bg-slate-50'}`}>
            <FileUp className="text-brand-500" />
            <span className="text-sm font-semibold text-ink-900">Drop a CSV here or click to choose</span>
            <span className="text-xs text-ink-500">UTF-8 CSV · up to 25 MB · stays on this computer</span>
            <input type="file" accept=".csv,text/csv" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); e.target.value = '' }} />
          </label>

          <div className="mt-4">
            <div className="label">Or try a bundled synthetic dataset</div>
            <div className="grid gap-2 sm:grid-cols-2">
              {demos.map((d) => (
                <button key={d.name} onClick={() => onDemo(d.name)}
                  className={`rounded-xl border px-3 py-2 text-left text-sm transition hover:border-brand-500 ${dataset?.name === d.name ? 'border-brand-500 bg-brand-50' : 'border-slate-200 bg-card'}`}>
                  <div className="font-semibold capitalize text-ink-900">{pretty(d.name)}</div>
                  <div className="text-xs text-ink-500">{(d.bytes / 1024).toFixed(0)} KB · synthetic</div>
                </button>
              ))}
            </div>
          </div>

          {loading && <div className="mt-4"><Spinner label={loading} /></div>}
          {rejected && (
            <div className="mt-4">
              <Note tone="warn">
                <b>{rejected.name} was rejected before analysis.</b>
                <ul className="mt-1 list-disc pl-4">{rejected.validation.errors.map((e: any) => <li key={e.code}>{e.message}</li>)}</ul>
              </Note>
            </div>
          )}

          {dataset?.accepted && (
            <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-semibold text-ink-900">{dataset.name}</div>
                  <div className="text-xs text-ink-500">
                    {fmtNum(dataset.validation.row_count)} rows · {dataset.validation.column_count} columns · fingerprint {dataset.fingerprint.slice(0, 10)}…
                  </div>
                </div>
                <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => setShowPreview(!showPreview)}>
                  <Table2 size={14} />{showPreview ? 'Hide rows' : 'Preview rows'}
                </button>
              </div>
              {dataset.validation.warnings.map((w: any) => <div key={w.code} className="mt-2"><Note tone="warn">{w.message}</Note></div>)}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {dataset.columns.map((c: any) => (
                  <span key={c.name} className={`chip ${KIND_STYLE[c.kind] ?? 'border-slate-200 bg-card text-slate-600'}`} title={`${c.kind} · ${c.distinct} distinct · ${c.missing_count} missing`}>
                    {c.name}
                    {c.missing_count > 0 && <span className="text-[10px] opacity-70">· {c.missing_count} missing</span>}
                  </span>
                ))}
              </div>
              {showPreview && (
                <div className="mt-3 max-h-64 overflow-auto rounded-xl border border-slate-200 bg-card">
                  <table className="min-w-full text-xs">
                    <thead className="sticky top-0 bg-slate-100">
                      <tr>{dataset.columns.map((c: any) => <th key={c.name} className="whitespace-nowrap px-2 py-1.5 text-left font-semibold text-ink-700">{c.name}</th>)}</tr>
                    </thead>
                    <tbody>
                      {dataset.preview.map((row: any, i: number) => (
                        <tr key={i} className="odd:bg-slate-50/60">
                          {dataset.columns.map((c: any) => <td key={c.name} className="whitespace-nowrap px-2 py-1 text-ink-700">{row[c.name] == null ? <span className="text-slate-300">—</span> : String(row[c.name])}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-end gap-3">
        {!ready && <span className="text-sm text-ink-500">Add a research question and load a dataset to continue.</span>}
        <button className="btn-primary !px-6 !py-3 text-base" disabled={!ready || !!loading} onClick={onPlan}>
          <Sparkles size={18} /> Plan my analysis <ArrowRight size={18} />
        </button>
      </div>
    </div>
  )
}
