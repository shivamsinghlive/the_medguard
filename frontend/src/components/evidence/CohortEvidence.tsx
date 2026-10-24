import { useEffect, useState } from 'react'
import { prefersReducedMotion } from '../../charts/theme'
import { StatusBadge, fmtNum } from '../ui'

const GROUP_VARS = ['--brand-500', '--teal-500', '--brand-300', '--ink-700']
const gv = (i: number) => `rgb(var(${GROUP_VARS[i % 4]}))`

/** Dumbbell (observed dot, reference ring, gap in pp; no threshold line) plus a 100-square waffle. */
export default function CohortEvidence({ cohort, onPick }: { cohort: any; onPick?: (label: string) => void }) {
  const groups = cohort.groups
  const [settled, setSettled] = useState(prefersReducedMotion())
  useEffect(() => {
    if (prefersReducedMotion()) return
    setSettled(false)
    const id = requestAnimationFrame(() => requestAnimationFrame(() => setSettled(true)))
    return () => cancelAnimationFrame(id)
  }, [cohort])

  const W = 600, left = 170, right = 520, rowH = 58, top = 18
  const H = top + groups.length * rowH + 42
  const x = (pct: number | null) => left + (right - left) * (Math.max(0, Math.min(100, pct ?? 0)) / 100)
  const short = (s: string) => (s.length > 24 ? `${s.slice(0, 23)}…` : s)
  const rawLabel = (label: string) => label.slice(cohort.column.length + 3)
  const total = cohort.observedCount + cohort.missingCount
  const svgLabel = `Observed share by recorded group for ${cohort.column}: ` + groups.map((g: any) =>
    `${g.label} ${g.observed}%${g.reference != null ? `, reference ${g.reference}%, gap ${g.gapText}` : ''}`).join('; ')

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div><div className="eyebrow">Cohort evidence</div><div className="display text-xl">{cohort.column}</div></div>
        <StatusBadge status={cohort.status} small />
      </div>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(220px,.9fr)]">
        <div>
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={svgLabel}>
            {groups.map((g: any, i: number) => {
              const y = top + i * rowH + rowH / 2, ox = x(g.observed), hasRef = g.reference != null, rx = hasRef ? x(g.reference) : ox
              return (
                <g key={g.label} className={onPick ? 'cursor-pointer' : undefined} onClick={() => onPick?.(rawLabel(g.label))}>
                  <title>{`${g.label}: ${g.observed ?? 'n/a'}% observed${hasRef ? `, reference ${g.reference}%, gap ${g.gapText}` : ''}${onPick ? '. Click to filter.' : ''}`}</title>
                  <text x={0} y={y + 4} fontSize={13} fill="rgb(var(--ink-900))">{short(g.label)}</text>
                  <line x1={left} x2={right} y1={y} y2={y} stroke="rgb(var(--slate-100))" strokeWidth={2} />
                  {hasRef && <line x1={Math.min(ox, rx)} x2={Math.max(ox, rx)} y1={y} y2={y} stroke="rgb(var(--slate-200))" strokeWidth={6} strokeLinecap="round"
                    style={{ opacity: settled ? 1 : 0, transition: 'opacity .5s ease .2s' }} />}
                  <circle cx={ox} cy={y} r={9} fill={gv(i)} />
                  <text x={ox} y={y - 15} fontSize={12} textAnchor="middle" fill="rgb(var(--ink-700))">{g.observed == null ? 'n/a' : `${g.observed}%`}</text>
                  {hasRef && (
                    <g style={{ transform: `translateX(${settled ? 0 : ox - rx}px)`, opacity: settled ? 1 : 0, transition: 'transform .7s cubic-bezier(.2,.8,.2,1), opacity .5s ease' }}>
                      <circle cx={rx} cy={y} r={9} fill="rgb(var(--card))" stroke="rgb(var(--ink-900))" strokeWidth={3} />
                      <text x={rx} y={y + 25} fontSize={11} textAnchor="middle" fill="rgb(var(--ink-500))">ref {g.reference}%</text>
                    </g>
                  )}
                  {hasRef && <text x={Math.max(ox, rx) + 18} y={y + 4} fontSize={13} fontWeight={700} fill="rgb(var(--ink-900))">{g.gapText}</text>}
                </g>
              )
            })}
            {[0, 25, 50, 75, 100].map((t) => (
              <g key={t}>
                <line x1={x(t)} x2={x(t)} y1={H - 34} y2={H - 29} stroke="rgb(var(--ink-300))" />
                <text x={x(t)} y={H - 14} fontSize={11} textAnchor="middle" fill="rgb(var(--ink-500))">{t}%</text>
              </g>
            ))}
          </svg>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-500">
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-brand-500" />observed share</span>
            {cohort.hasReference
              ? <><span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full border-2 border-ink-900" />supplied reference</span><span>gaps in percentage points, observed minus reference</span></>
              : <span>No reference supplied; shares are descriptive only.</span>}
          </div>
        </div>
        <div>
          <div className="eyebrow">100-square view</div>
          <div className="mx-auto mt-2 grid max-w-[250px] grid-cols-10 gap-1" role="img"
            aria-label={`100-square view of ${fmtNum(total)} rows: ` + groups.map((g: any) => `${g.label} ${g.squares} squares`).join(', ') + `, missing ${cohort.missingSquares} squares.`}>
            {cohort.cells.map((c: any, i: number) => (
              <i key={i} className="block aspect-square rounded-[3px]" title={c.group < 0 ? 'missing value' : groups[c.group].label}
                style={{
                  background: c.group < 0 ? 'repeating-linear-gradient(45deg, rgb(var(--slate-200)) 0 3px, rgb(var(--slate-100)) 3px 6px)' : gv(c.group),
                  boxShadow: c.reference ? '0 0 0 2px rgb(var(--card)), 0 0 0 3.5px rgb(var(--ink-900))' : undefined,
                  opacity: settled ? 1 : 0, transition: `opacity .3s ease ${Math.min(i * 6, 600)}ms`,
                }} />
            ))}
          </div>
          <div className="mt-3 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-ink-500">
            {groups.map((g: any, i: number) => <span key={g.label} className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[3px]" style={{ background: gv(i) }} />{g.label}</span>)}
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[3px] bg-slate-200" />missing · {fmtNum(cohort.missingCount)}</span>
          </div>
        </div>
      </div>
      <p className="text-xs leading-relaxed text-ink-500">
        Denominator: {fmtNum(cohort.observedCount)} non-missing values; {fmtNum(cohort.missingCount)} missing are a separate gray segment, never dropped. One square is about 1% of all {fmtNum(total)} rows.
        {cohort.referenceSquares > 0 && ` Navy outlines mark the reference share for ${cohort.referenceLabel} (${cohort.referenceSquares} squares).`}
      </p>
    </div>
  )
}
