import { useEffect, useState } from 'react'
import { prefersReducedMotion } from '../../charts/theme'
import { StatusBadge, fmtNum } from '../ui'

/** Coverage is the hero here, not matches: how much of the table the screen actually checked. */
export default function CoverageRing({ coverage: c }: { coverage: any }) {
  const reduced = prefersReducedMotion()
  const [pct, setPct] = useState(reduced ? c.percent : 0)
  const [ticked, setTicked] = useState(reduced ? c.columnCount : 0)
  useEffect(() => {
    if (reduced) { setPct(c.percent); setTicked(c.columnCount); return }
    setPct(0); setTicked(0)
    const start = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / 1100)
      setPct(Math.round(c.percent * (1 - Math.pow(1 - p, 3)) * 10) / 10)
      setTicked(Math.round(c.columnCount * p))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [c, reduced])

  const shown = Math.min(c.columnCount, 30)
  const R = 66, C = 2 * Math.PI * R
  return (
    <div className="grid items-center gap-6 sm:grid-cols-[170px_minmax(0,1fr)]">
      <svg viewBox="0 0 160 160" className="mx-auto w-40" role="img" aria-label={`${c.percent}% of cells value-checked`}>
        <circle cx={80} cy={80} r={R} fill="none" stroke="rgb(var(--slate-100))" strokeWidth={14} />
        <circle cx={80} cy={80} r={R} fill="none" stroke="rgb(var(--brand-300))" strokeWidth={14} strokeLinecap="round"
          strokeDasharray={`${(pct / 100) * C} ${C}`} transform="rotate(-90 80 80)" />
        <text x={80} y={80} textAnchor="middle" className="font-display" fontSize={28} fontWeight={700} fill="rgb(var(--ink-900))">{pct}%</text>
        <text x={80} y={100} textAnchor="middle" fontSize={11} fill="rgb(var(--ink-500))">cells scanned</text>
      </svg>
      <div className="min-w-0 space-y-3">
        <div>
          <div className="eyebrow">Identifier screening coverage</div>
          <div className="display mt-1 text-xl">{fmtNum(c.columnCount)} of {fmtNum(c.columnCount)} columns scanned · {fmtNum(c.matches)} matched</div>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-500">
            {fmtNum(c.rowsScanned)} of {fmtNum(c.rowCount)} rows value-checked with {fmtNum(c.checkCount)} checks. Every column also gets a name check.
            <StatusBadge status={c.status} small />
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5" aria-hidden>
          {Array.from({ length: shown }, (_, i) => (
            <span key={i} className={`rounded-full px-2 py-0.5 text-[11px] transition-colors ${i < ticked ? 'bg-brand-100 text-brand-700' : 'bg-slate-100 text-ink-300'}`}>
              column {i + 1}{i < ticked ? ' · scanned' : ''}
            </span>
          ))}
          {c.columnCount > shown && <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[11px] text-brand-700">+{fmtNum(c.columnCount - shown)} more scanned</span>}
        </div>
        <div className="rounded-r-xl border-l-[3px] border-ink-900 bg-slate-100 px-3 py-2 text-sm text-ink-900">
          <strong>This is screening, not clearance.</strong> No matched patterns does not establish HIPAA de-identification.
        </div>
      </div>
    </div>
  )
}
