import { Bot, Compass, Download, FolderOpen, Save, ShieldCheck } from 'lucide-react'
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
  onTour?: () => void
}

export default function Header({ step, onStep, maxStep, ai, useAi, onToggleAi, onSave, onLoad, onExport, onTour }: Props) {
  const fileRef = useRef<HTMLInputElement>(null)
  const aiReady = ai?.available
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-card/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1500px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-2.5">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-[linear-gradient(135deg,#0B1430,#2F5BFF)] text-white shadow">
            <ShieldCheck size={20} />
          </div>
          <div>
            <div className="font-display text-[16px] font-bold leading-tight text-ink-900">MedGuard Explorer</div>
            <div className="text-[11px] text-ink-500">Dataset readiness, research-first</div>
          </div>
        </div>

        <nav className="mx-auto flex items-center gap-1 rounded-2xl bg-slate-100 p-1" aria-label="Steps">
          {STEPS.map((label, i) => (
            <button key={label} disabled={i > maxStep} onClick={() => onStep(i)} aria-label={label}
              aria-current={i === step ? 'step' : undefined}
              className={`flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-semibold transition ${i === step ? 'bg-card text-ink-900 shadow-sm' : 'text-ink-500 hover:text-ink-900 disabled:opacity-40'}`}>
              <span className={`grid h-5 w-5 place-items-center rounded-full text-[11px] ${i === step ? 'bg-brand-600 text-white' : i <= maxStep ? 'bg-brand-100 text-brand-700' : 'bg-slate-200 text-ink-500'}`}>{i + 1}</span>
              <span className="hidden sm:inline">{label}</span>
            </button>
          ))}
        </nav>

        <div className="flex flex-wrap items-center gap-1 sm:gap-2">
          <button onClick={onToggleAi} disabled={!aiReady}
            title={aiReady ? 'Use the local model for planning and explanations' : ai?.reason ?? 'Checking local AI'}
            className={`chip !py-1.5 ${aiReady && useAi ? 'border-brand-200 bg-brand-50 text-brand-700' : 'border-slate-200 bg-slate-50 text-ink-500'}`}>
            <Bot size={14} />
            <span className="hidden sm:inline">{aiReady ? (useAi ? `Local AI on · ${ai.model}` : 'Local AI off') : 'AI unavailable · rule-based mode'}</span>
          </button>
          {onTour && <button className="btn-ghost" onClick={onTour} title="Take the guided tour" aria-label="Tour"><Compass size={16} /><span className="hidden sm:inline">Tour</span></button>}
          <input ref={fileRef} type="file" accept="application/json" hidden
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onLoad(f); e.target.value = '' }} />
          <button className="btn-ghost" onClick={() => fileRef.current?.click()} title="Open a saved workflow" aria-label="Open"><FolderOpen size={16} /><span className="hidden sm:inline">Open</span></button>
          <button className="btn-ghost" onClick={onSave} disabled={!onSave} title="Save this workflow as JSON" aria-label="Save"><Save size={16} /><span className="hidden sm:inline">Save</span></button>
          <button className="btn-outline" onClick={onExport} disabled={!onExport} data-tour="export" aria-label="Report" title="Download the readiness report (JSON)"><Download size={16} /><span className="hidden sm:inline">Report</span></button>
        </div>
      </div>
    </header>
  )
}
