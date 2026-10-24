import { X } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'

export const TOUR_KEY = 'medguard-explorer-tour-v1'

const STEPS = [
  { target: 'question', title: 'Your research question leads', body: 'Everything below is computed for this question, from your file. Nothing is hard-coded or certified.' },
  { target: 'status', title: 'One summary, measured once', body: 'Four measured numbers with their status. Click a tile to open the evidence behind it.' },
  { target: 'canvas', title: 'A zoomable workflow', body: 'Scroll to zoom, drag to pan or rearrange, and use the minimap to jump. Double-click a card, or press Enter, to open it full screen.' },
  { target: 'filters', title: 'Linked filtering', body: 'Click a bar, drag across a histogram, or select rows on the row map or 2-D map. Every widget recomputes for that subset. Undo any step.' },
  { target: 'widgets', title: 'Add or remove analyses', body: 'Turn widgets on and off. Status dots show where to look first; tangerine always means review.' },
  { target: 'copy', title: 'Prepare a reviewed copy', body: 'Preview allowlisted cleaning on a separate copy, watch the removed rows drop out, then accept it for the report. The source stays locked.' },
]

type Box = { top: number; left: number; width: number; height: number }

export default function Tour({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [step, setStep] = useState(0)
  const [box, setBox] = useState<Box | null>(null)
  const card = useRef<HTMLDivElement>(null)
  const steps = STEPS.filter((s) => document.querySelector(`[data-tour="${s.target}"]`))
  const current = steps[Math.min(step, steps.length - 1)]

  useEffect(() => { if (open) setStep(0) }, [open])

  useLayoutEffect(() => {
    if (!open || !current) return
    const el = document.querySelector(`[data-tour="${current.target}"]`) as HTMLElement | null
    if (!el) return
    el.scrollIntoView({ block: 'center', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
    const measure = () => {
      const r = el.getBoundingClientRect()
      setBox({ top: r.top - 8, left: r.left - 8, width: r.width + 16, height: r.height + 16 })
    }
    measure()
    const t = setTimeout(measure, 400)
    addEventListener('resize', measure); addEventListener('scroll', measure, true)
    card.current?.focus()
    return () => { clearTimeout(t); removeEventListener('resize', measure); removeEventListener('scroll', measure, true) }
  }, [open, current])

  if (!open || !current || !box) return null
  const finish = () => { try { localStorage.setItem(TOUR_KEY, 'done') } catch { /* private mode */ } onClose() }
  const below = box.top + box.height + 220 < innerHeight
  const cardTop = below ? box.top + box.height + 12 : Math.max(12, box.top - 200)
  const cardLeft = Math.max(12, Math.min(innerWidth - 372, box.left))
  const index = steps.indexOf(current)

  return (
    <div className="fixed inset-0 z-[60]" role="dialog" aria-modal="true" aria-labelledby="tour-title"
      onKeyDown={(e) => { if (e.key === 'Escape') finish(); if (e.key === 'ArrowRight') setStep(Math.min(steps.length - 1, index + 1)); if (e.key === 'ArrowLeft') setStep(Math.max(0, index - 1)) }}>
      <div className="pointer-events-none absolute rounded-2xl ring-4 ring-brand-500 transition-all duration-300"
        style={{ ...box, boxShadow: '0 0 0 9999px rgb(var(--shadow) / .45)' }} />
      <div ref={card} tabIndex={-1} className="absolute w-[360px] max-w-[calc(100vw-24px)] rounded-2xl border border-slate-200 bg-card p-4 shadow-lift outline-none animate-rise"
        style={{ top: cardTop, left: cardLeft }}>
        <div className="flex items-start justify-between gap-2">
          <div className="eyebrow">Tour · {index + 1} of {steps.length}</div>
          <button className="btn-ghost !p-1" onClick={finish} aria-label="Close tour"><X size={14} /></button>
        </div>
        <h3 id="tour-title" className="display mt-1 text-lg">{current.title}</h3>
        <p className="mt-1 text-sm leading-relaxed text-ink-700">{current.body}</p>
        <div className="mt-4 flex items-center justify-between">
          <div className="flex gap-1" aria-hidden>{steps.map((s, i) => <span key={s.target} className={`h-1.5 rounded-full transition-all ${i === index ? 'w-5 bg-brand-500' : 'w-1.5 bg-slate-300'}`} />)}</div>
          <div className="flex gap-2">
            {index > 0 && <button className="btn-ghost !px-3 !py-1.5" onClick={() => setStep(index - 1)}>Back</button>}
            {index < steps.length - 1
              ? <button className="btn-primary !px-3 !py-1.5" onClick={() => setStep(index + 1)}>Next</button>
              : <button className="btn-primary !px-3 !py-1.5" onClick={finish}>Done</button>}
          </div>
        </div>
      </div>
    </div>
  )
}
