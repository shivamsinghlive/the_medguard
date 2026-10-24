import { AlertTriangle, CircleDashed, Info, Loader2, Minus } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Status } from '../api'

// Contract status words as plain-language chips. Tangerine is reserved for review;
// no status is ever shown as a green pass, and "no patterns found" is not clearance.
export const STATUS: Record<string, { label: string; tone: string; dot: string; icon: any; hint?: string }> = {
  review_needed: { label: 'Review needed', tone: 'border-review-200 bg-review-50 text-review-700', dot: 'review-500', icon: AlertTriangle },
  descriptive_only: { label: 'Descriptive only', tone: 'border-slate-200 bg-slate-100 text-ink-700', dot: 'ink-300', icon: Minus },
  no_patterns_found: { label: 'No patterns found', tone: 'border-slate-200 bg-slate-100 text-ink-900', dot: 'ink-300', icon: Minus,
    hint: 'No listed identifier pattern matched. This is not de-identification or privacy clearance.' },
  insufficient_evidence: { label: 'Not enough evidence', tone: 'border-dashed border-slate-400 bg-card text-ink-700', dot: 'slate-400', icon: CircleDashed },
  not_available: { label: 'Not available', tone: 'border-dashed border-slate-300 bg-card text-ink-500', dot: 'slate-300', icon: CircleDashed },
}

export const dotColor = (status: string) => `rgb(var(--${(STATUS[status] ?? STATUS.not_available).dot}))`

export function StatusBadge({ status, small }: { status: Status | string; small?: boolean }) {
  const meta = STATUS[status] ?? STATUS.not_available
  const Icon = meta.icon
  return (
    <span className={`chip ${meta.tone} ${small ? '!px-2 !py-0.5 text-[11px]' : ''}`} title={meta.hint}>
      <Icon size={small ? 11 : 13} aria-hidden /> {meta.label}
    </span>
  )
}

export function Metric({ label, value, hint, review }: { label: string; value: ReactNode; hint?: string; review?: boolean }) {
  return (
    <div className={`rounded-xl border bg-slate-50 px-4 py-3 ${review ? 'border-l-4 border-slate-200 border-l-review-500' : 'border-slate-200'}`}>
      <div className="eyebrow">{label}</div>
      <div className="mt-1 font-display text-2xl font-bold text-ink-900">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-500">{hint}</div>}
    </div>
  )
}

export function Note({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warn' }) {
  const cls = tone === 'warn' ? 'border-review-200 bg-review-50 text-review-700' : 'border-brand-100 bg-brand-50 text-brand-700'
  return (
    <div className={`flex gap-2 rounded-xl border px-3 py-2 text-sm ${cls}`}>
      {tone === 'warn' ? <AlertTriangle size={16} className="mt-0.5 shrink-0" /> : <Info size={16} className="mt-0.5 shrink-0" />}
      <div>{children}</div>
    </div>
  )
}

export function Spinner({ label }: { label: string }) {
  return <span className="inline-flex items-center gap-2 text-sm text-ink-500" role="status"><Loader2 size={16} className="animate-spin" />{label}</span>
}

export function Findings({ findings }: { findings: any[] }) {
  if (!findings?.length) return <p className="text-sm text-ink-500">No review flags for this view.</p>
  return (
    <ul className="space-y-2">
      {findings.map((f) => (
        <li key={f.id} className="rounded-xl border border-slate-200 bg-card px-3 py-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`chip ${f.priority === 'high' ? 'border-review-200 bg-review-50 text-review-700' : f.priority === 'medium' ? 'border-review-200 bg-card text-review-700' : 'border-slate-200 bg-slate-50 text-ink-700'}`}>
              {f.priority}
            </span>
            <span className="text-sm font-semibold text-ink-900">{f.title}</span>
            <span className="text-xs text-ink-500">{f.column}</span>
          </div>
          <div className="mt-1 text-xs text-ink-500">{f.suggested_action}</div>
        </li>
      ))}
    </ul>
  )
}

export const fmtPct = (v: number | null | undefined, d = 1) => (v == null ? '—' : `${(v * 100).toFixed(d)}%`)
export const fmtNum = (v: number | null | undefined) => (v == null ? '—' : v.toLocaleString('en-US'))
