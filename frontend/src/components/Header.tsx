import { Bot, Download, FolderOpen, Save, ShieldCheck } from 'lucide-react'
import { useRef } from 'react'

const STEPS = ['Research & data', 'Confirm plan', 'Explore']

type Props = {
  step: number
  onStep: (n: number) => void
  maxStep: number
  ai: any
  useAi: boolean
  onToggleAi: () => void
  onSave?: () => void
  onLoad: (file: File) => void
  onExport?: () => void
}

export default function Header({ step, onStep, maxStep, ai, useAi, onToggleAi, onSave, onLoad, onExport }: Props) {
  const fileRef = useRef<HTMLInputElement>(null)
  const aiReady = ai?.available
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1500px] flex-wrap items-center gap-4 px-6 py-3">
        <div className="flex items-center gap-2.5">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-indigo-600 text-white shadow">
            <ShieldCheck size={20} />
          </div>
          <div>
            <div className="text-[15px] font-bold leading-tight text-ink-900">MedGuard Explorer</div>
            <div className="text-[11px] text-ink-500">Dataset readiness, research-first</div>
          </div>
        </div>

        <nav className="mx-auto flex items-center gap-1 rounded-2xl bg-slate-100 p-1" aria-label="Steps">
          {STEPS.map((label, i) => (
            <button key={label} disabled={i > maxStep} onClick={() => onStep(i)}
              className={`flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-semibold transition ${i === step ? 'bg-white text-brand-700 shadow-sm' : 'text-ink-500 hover:text-ink-900 disabled:opacity-40'}`}>
              <span className={`grid h-5 w-5 place-items-center rounded-full text-[11px] ${i === step ? 'bg-brand-600 text-white' : 'bg-slate-300 text-white'}`}>{i + 1}</span>
              {label}
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <button onClick={onToggleAi} disabled={!aiReady}
            title={aiReady ? 'Use the local model for planning and explanations' : ai?.reason ?? 'Checking local AI'}
            className={`chip !py-1.5 ${aiReady && useAi ? 'border-violet-200 bg-violet-50 text-violet-700' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>
            <Bot size={14} />
            {aiReady ? (useAi ? `Local AI on · ${ai.model}` : 'Local AI off') : 'AI unavailable · rule-based mode'}
          </button>
          <input ref={fileRef} type="file" accept="application/json" hidden
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onLoad(f); e.target.value = '' }} />
          <button className="btn-ghost" onClick={() => fileRef.current?.click()} title="Open a saved workflow"><FolderOpen size={16} />Open</button>
          <button className="btn-ghost" onClick={onSave} disabled={!onSave} title="Save this workflow as JSON"><Save size={16} />Save</button>
          <button className="btn-outline" onClick={onExport} disabled={!onExport}><Download size={16} />Report</button>
        </div>
      </div>
    </header>
  )
}
