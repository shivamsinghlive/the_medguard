import { useEffect, useState } from 'react'
import { prefersReducedMotion } from '../../charts/theme'
import { StatusBadge, fmtNum } from '../ui'

function CountUp({ value }: { value: number }) {
  const reduced = prefersReducedMotion()
  const [shown, setShown] = useState(reduced ? value : 0)
  useEffect(() => {
    if (reduced || !value) { setShown(value); return }
    const start = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / 650)
      setShown(Math.round(value * (1 - Math.pow(1 - p, 3))))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value, reduced])
  return <>{fmtNum(shown)}</>
}

/** Measured numbers with their contract status; one summary for the whole workspace. */
export default function StatusStrip({ tiles, onOpen }: { tiles: any[]; onOpen?: (label: string) => void }) {
  return (
    <section className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Measured audit status">
      {tiles.map((t) => {
        const Tag = onOpen ? 'button' : 'div'
        return (
          <Tag key={t.label} {...(onOpen ? { type: 'button', onClick: () => onOpen(t.label) } : {})}
            className={`flex min-w-0 flex-col gap-1.5 rounded-2xl border bg-card p-4 text-left shadow-card transition ${t.status === 'review_needed' ? 'border-slate-200 border-l-4 border-l-review-500' : 'border-slate-200'} ${onOpen ? 'hover:-translate-y-0.5 hover:shadow-lift focus-visible:ring-2 focus-visible:ring-brand-500' : ''}`}>
            <span className="eyebrow">{t.label}</span>
            <span className="font-display text-3xl font-bold leading-none text-ink-900"><CountUp value={t.value} /></span>
            <span className="text-xs leading-snug text-ink-500">{t.unit}</span>
            <span><StatusBadge status={t.status} small /></span>
            <span className="mt-auto text-[11px] text-ink-300">{t.note}</span>
          </Tag>
        )
      })}
    </section>
  )
}
