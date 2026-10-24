import { AlertTriangle, CheckCircle2, CircleDashed, Info, Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Status } from '../api'

export const STATUS: Record<string, { label: string; tone: string; dot: string; icon: any }> = {
  review_needed: { label: 'Review needed', tone: 'bg-review-50 text-review-700 border-orange-200', dot: '#f97316', icon: AlertTriangle },
  descriptive_only: { label: 'Descriptive', tone: 'bg-okay-50 text-okay-700 border-emerald-200', dot: '#10b981', icon: CheckCircle2 },
  no_patterns_found: { label: 'No patterns found', tone: 'bg-okay-50 text-okay-700 border-emerald-200', dot: '#10b981', icon: CheckCircle2 },
  insufficient_evidence: { label: 'Not enough evidence', tone: 'bg-slate-100 text-slate-600 border-slate-200', dot: '#94a3b8', icon: CircleDashed },
  not_available: { label: 'Not available', tone: 'bg-slate-100 text-slate-500 border-slate-200', dot: '#cbd5e1', icon: CircleDashed },
}

export function StatusBadge({ status, small }: { status: Status | string; small?: boolean }) {
  const meta = STATUS[status] ?? STATUS.not_available
  const Icon = meta.icon
  return (
    <span className={`chip ${meta.tone} ${small ? '!px-2 !py-0.5 text-[11px]' : ''}`}>
      <Icon size={small ? 11 : 13} /> {meta.label}
    </span>
  )
}

export function Metric({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">{label}</div>
      <div className="mt-1 text-xl font-bold text-ink-900">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-500">{hint}</div>}
    </div>
  )
}

export function Note({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warn' }) {
  const cls = tone === 'warn' ? 'border-orange-200 bg-review-50 text-review-700' : 'border-brand-100 bg-brand-50 text-brand-700'
  return (
    <div className={`flex gap-2 rounded-xl border px-3 py-2 text-sm ${cls}`}>
      {tone === 'warn' ? <AlertTriangle size={16} className="mt-0.5 shrink-0" /> : <Info size={16} className="mt-0.5 shrink-0" />}
      <div>{children}</div>
    </div>
  )
}

export function Spinner({ label }: { label: string }) {
  return <span className="inline-flex items-center gap-2 text-sm text-ink-500"><Loader2 size={16} className="animate-spin" />{label}</span>
}

export function Findings({ findings }: { findings: any[] }) {
  if (!findings?.length) return <p className="text-sm text-ink-500">No review flags for this view.</p>
  return (
    <ul className="space-y-2">
      {findings.map((f) => (
        <li key={f.id} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`chip ${f.priority === 'high' ? 'border-orange-200 bg-review-50 text-review-700' : f.priority === 'medium' ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>
              {f.priority}
            </span>
            <span className="text-sm font-semibold text-ink-900">{f.title}</span>
            <span className="text-xs text-ink-500">{f.column}</span>
          </div>
          <div className="mt-1 text-xs text-ink-500">{f.suggested_action}</div>
          <div className="mt-1 font-mono text-[11px] text-ink-500 break-all">{JSON.stringify(f.evidence)}</div>
        </li>
      ))}
    </ul>
  )
}

export const fmtPct = (v: number | null | undefined, d = 1) => (v == null ? '—' : `${(v * 100).toFixed(d)}%`)
export const fmtNum = (v: number | null | undefined) => (v == null ? '—' : v.toLocaleString())
