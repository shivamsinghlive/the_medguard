import { Filter, Hand, Maximize2, Minus, MousePointerSquareDashed, Plus, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { groupColor, prefersReducedMotion, token, useScheme } from '../../charts/theme'
import { StatusBadge, fmtNum } from '../ui'

type Lens = 'cohort' | 'missing' | 'duplicate' | 'identifier' | 'readiness'
type Cell = { x: number; y: number; r: any }
const LENSES: { id: Lens; name: string }[] = [
  { id: 'readiness', name: 'Readiness' }, { id: 'cohort', name: 'Cohort' }, { id: 'missing', name: 'Missing values' },
  { id: 'duplicate', name: 'Duplicates' }, { id: 'identifier', name: 'Identifier scan' },
]
const MAX_ZOOM = 14

type Props = { mosaic: any; onSelectRows?: (ids: number[], label: string) => void; compact?: boolean }

export default function RowMap({ mosaic: d, onSelectRows, compact }: Props) {
  const scheme = useScheme()
  // Resolve palette colors once per theme; the canvas paints thousands of cells per frame.
  const pal = useMemo(() => ({
    review: token('review-500'), reviewSoft: token('review-200'), dim: token('slate-100'), dim2: token('slate-200'),
    dim3: token('slate-300'), scan: token('brand-300'), ink: token('ink-900'), card: token('card'), brand: token('brand-500'),
    glow: token('brand-500', 0.25), groups: [0, 1, 2, 3].map(groupColor),
  }), [scheme])
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const miniRef = useRef<HTMLCanvasElement>(null)
  const [lens, setLens] = useState<Lens>(d.initialLens === 'missing' ? 'missing' : 'readiness')
  const [stage, setStage] = useState<number | null>(null)
  const [view, setView] = useState({ k: 1, x: 0, y: 0 })
  const [mode, setMode] = useState<'pan' | 'select'>('pan')
  const [size, setSize] = useState({ w: 600, h: compact ? 220 : 320 })
  const [active, setActive] = useState(-1)
  const [tip, setTip] = useState<{ x: number; y: number; r: any } | null>(null)
  const [rect, setRect] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null)
  const [picked, setPicked] = useState<number[] | null>(null)
  const [sweep, setSweep] = useState<number | null>(null)
  const drag = useRef<{ kind: 'pan' | 'select'; sx: number; sy: number; vx: number; vy: number } | null>(null)

  useEffect(() => { if (d.initialLens === 'missing') setLens('missing') }, [d.initialLens])
  useEffect(() => { setPicked(null); setRect(null) }, [d])

  // Base layout: square cells filling the canvas at zoom 1.
  const layout = useMemo(() => {
    const n = Math.max(d.rows.length, 1)
    let best = { cell: 0, cols: 1 }
    const guess = Math.max(1, Math.round(Math.sqrt((n * size.w) / Math.max(size.h, 1))))
    for (let c = Math.max(1, guess - 8); c <= guess + 8; c++) {
      const rows = Math.ceil(n / c)
      const cell = Math.min(size.w / c, size.h / rows)
      if (cell > best.cell) best = { cell, cols: c }
    }
    const offset = Math.max(0, (size.w - best.cols * best.cell) / 2)
    const cells: Cell[] = d.rows.map((r: any, i: number) => ({ x: offset + (i % best.cols) * best.cell, y: Math.floor(i / best.cols) * best.cell, r }))
    return { cells, cols: best.cols, cell: best.cell }
  }, [d.rows, size])

  const colorFor = useCallback((r: any): string => {
    if (lens === 'cohort') return r.group < 0 ? pal.dim2 : pal.groups[r.group % 4]
    if (lens === 'missing') {
      if (d.focusActive) return r.focus ? pal.review : pal.dim
      return r.missing >= 2 ? pal.review : r.missing === 1 ? pal.reviewSoft : pal.dim
    }
    if (lens === 'duplicate') return r.duplicate ? pal.review : pal.dim
    if (lens === 'identifier') return r.row <= d.rowsScanned ? pal.scan : pal.dim2
    if (stage !== null) return r.drop === stage ? pal.review : pal.dim
    return r.drop === 0 ? pal.scan : r.drop === 1 ? pal.review : r.drop === 2 ? pal.reviewSoft : pal.dim3
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lens, stage, d, pal])

  const toScreen = (c: Cell) => ({ x: c.x * view.k + view.x, y: c.y * view.k + view.y, s: layout.cell * view.k })

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ratio = devicePixelRatio || 1
    canvas.width = Math.round(size.w * ratio)
    canvas.height = Math.round(size.h * ratio)
    const ctx = canvas.getContext('2d')!
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
    ctx.clearRect(0, 0, size.w, size.h)
    const s = layout.cell * view.k
    const gap = s > 6 ? Math.min(2, s * 0.12) : s > 3 ? 0.5 : 0
    layout.cells.forEach((c) => {
      const x = c.x * view.k + view.x, y = c.y * view.k + view.y
      if (x > size.w || y > size.h || x + s < 0 || y + s < 0) return
      ctx.fillStyle = sweep !== null && x > sweep ? pal.dim : colorFor(c.r)
      ctx.fillRect(x, y, s - gap, s - gap)
    })
    if (sweep !== null) {
      const g = ctx.createLinearGradient(sweep - 70, 0, sweep + 6, 0)
      g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.85, pal.glow); g.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = g; ctx.fillRect(sweep - 70, 0, 76, size.h)
    }
    if (active >= 0 && layout.cells[active]) {
      const p = toScreen(layout.cells[active])
      ctx.strokeStyle = pal.ink; ctx.lineWidth = 2
      ctx.strokeRect(p.x - 1.5, p.y - 1.5, p.s - gap + 3, p.s - gap + 3)
    }
    if (picked) {
      ctx.strokeStyle = pal.brand; ctx.lineWidth = 1.5
      const set = new Set(picked)
      layout.cells.forEach((c) => {
        if (!set.has(c.r.id)) return
        const p = toScreen(c)
        ctx.strokeRect(p.x + 0.5, p.y + 0.5, Math.max(1, p.s - gap - 1), Math.max(1, p.s - gap - 1))
      })
    }
    // Minimap while zoomed: the whole grid with the visible window outlined.
    const mini = miniRef.current
    if (mini && view.k > 1.05) {
      const mw = 120, mh = Math.max(40, Math.round((size.h / size.w) * 120))
      mini.width = mw * ratio; mini.height = mh * ratio
      const m = mini.getContext('2d')!
      m.setTransform(ratio, 0, 0, ratio, 0, 0)
      m.fillStyle = pal.card; m.fillRect(0, 0, mw, mh)
      const scale = mw / size.w
      layout.cells.forEach((c) => { m.fillStyle = colorFor(c.r); m.fillRect(c.x * scale, c.y * scale, Math.max(1, layout.cell * scale), Math.max(1, layout.cell * scale)) })
      m.strokeStyle = pal.ink; m.lineWidth = 1.5
      m.strokeRect((-view.x / view.k) * scale, (-view.y / view.k) * scale, (size.w / view.k) * scale, (size.h / view.k) * scale)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layout, view, size, colorFor, active, picked, sweep, pal])

  useEffect(() => { draw() }, [draw])

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      const w = Math.max(200, Math.floor(entry.contentRect.width))
      setSize({ w, h: compact ? 220 : w < 560 ? 240 : 320 })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [compact])

  const switchLens = (next: Lens, nextStage: number | null = null) => {
    setLens(next); setStage(nextStage)
    if (prefersReducedMotion()) return
    const start = performance.now()
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / 650)
      setSweep(p < 1 ? p * (size.w + 70) : null)
      if (p < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }

  const clampView = (k: number, x: number, y: number) => {
    const w = size.w * k, h = size.h * k
    return { k, x: Math.min(0, Math.max(size.w - w, x)), y: Math.min(0, Math.max(size.h - h, y)) }
  }
  const zoomAt = (factor: number, cx = size.w / 2, cy = size.h / 2) => setView((v) => {
    const k = Math.min(MAX_ZOOM, Math.max(1, v.k * factor))
    return clampView(k, cx - ((cx - v.x) / v.k) * k, cy - ((cy - v.y) / v.k) * k)
  })

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const box = canvas.getBoundingClientRect()
      const factor = Math.min(1.2, Math.max(1 / 1.2, Math.exp(-e.deltaY * 0.0015)))
      zoomAt(factor, e.clientX - box.left, e.clientY - box.top)
    }
    canvas.addEventListener('wheel', onWheel, { passive: false })
    return () => canvas.removeEventListener('wheel', onWheel)
  })

  const local = (e: React.PointerEvent) => {
    const box = canvasRef.current!.getBoundingClientRect()
    return { x: e.clientX - box.left, y: e.clientY - box.top }
  }
  const hitIndex = (x: number, y: number) => {
    const s = layout.cell * view.k
    return layout.cells.findIndex((c) => { const px = c.x * view.k + view.x, py = c.y * view.k + view.y; return x >= px && x < px + s && y >= py && y < py + s })
  }
  const onDown = (e: React.PointerEvent) => {
    const p = local(e)
    const kind = e.shiftKey || mode === 'select' ? 'select' : 'pan'
    drag.current = { kind, sx: p.x, sy: p.y, vx: view.x, vy: view.y }
    if (kind === 'select') setRect({ x0: p.x, y0: p.y, x1: p.x, y1: p.y })
    ;(e.target as Element).setPointerCapture(e.pointerId)
  }
  const onMove = (e: React.PointerEvent) => {
    const p = local(e)
    const g = drag.current
    if (g?.kind === 'pan' && view.k > 1) { setView((v) => clampView(v.k, g.vx + p.x - g.sx, g.vy + p.y - g.sy)); return }
    if (g?.kind === 'select') { setRect((r) => (r ? { ...r, x1: p.x, y1: p.y } : r)); return }
    const index = hitIndex(p.x, p.y)
    setActive(index)
    setTip(index >= 0 ? { x: p.x, y: p.y, r: layout.cells[index].r } : null)
  }
  const onUp = (e: React.PointerEvent) => {
    const g = drag.current
    drag.current = null
    if (g?.kind === 'select' && rect) {
      const [x0, x1] = [Math.min(rect.x0, rect.x1), Math.max(rect.x0, rect.x1)]
      const [y0, y1] = [Math.min(rect.y0, rect.y1), Math.max(rect.y0, rect.y1)]
      const s = layout.cell * view.k
      const ids = layout.cells.filter((c) => {
        const px = c.x * view.k + view.x + s / 2, py = c.y * view.k + view.y + s / 2
        return px >= x0 && px <= x1 && py >= y0 && py <= y1
      }).map((c) => c.r.id)
      setRect(null)
      setPicked(ids.length > 1 ? ids : null)
      return
    }
    if (g && Math.abs(local(e).x - g.sx) < 3 && e.pointerType !== 'mouse') onMove(e)
  }
  const onKey = (e: React.KeyboardEvent) => {
    const moves: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: layout.cols, ArrowUp: -layout.cols }
    if (e.key === '+' || e.key === '=') { zoomAt(1.4); return }
    if (e.key === '-') { zoomAt(1 / 1.4); return }
    if (e.key === '0') { setView({ k: 1, x: 0, y: 0 }); return }
    if (e.key === 'Escape') { setTip(null); setActive(-1); setPicked(null); return }
    if (!(e.key in moves)) return
    e.preventDefault()
    const next = Math.max(0, Math.min(layout.cells.length - 1, (active < 0 ? 0 : active + moves[e.key])))
    setActive(next)
    const p = toScreen(layout.cells[next])
    setTip({ x: p.x + p.s, y: p.y, r: layout.cells[next].r })
  }

  const lensStatus: Record<Lens, string> = {
    readiness: d.funnel[d.funnel.length - 1].rows < d.funnel[0].rows ? 'review_needed' : 'descriptive_only',
    cohort: d.cohortStatus, missing: d.missingCells ? 'review_needed' : 'descriptive_only',
    duplicate: d.duplicateRows ? 'review_needed' : 'descriptive_only', identifier: d.screeningStatus,
  }
  const readout = (() => {
    if (lens === 'cohort') return { big: d.labels.length ? fmtNum(d.observedCount) : '—', unit: d.labels.length ? 'rows with a recorded label' : 'No demographic column selected', copy: 'Colored by group label exactly as recorded. Unlabelled rows are dimmed.' }
    if (lens === 'missing') return { big: fmtNum(d.focusActive ? d.focusMissing : d.missingCells), unit: d.focusActive ? 'missing cells in the focus column' : `missing cells across ${fmtNum(d.missingColumns)} columns`, copy: d.focusActive ? 'Rows missing a value in the focus column are highlighted.' : 'Lighter squares have one gap; darker squares have two or more.' }
    if (lens === 'duplicate') return { big: fmtNum(d.duplicateRows), unit: 'rows in exact-duplicate sets', copy: 'Every copy in a duplicate set is counted, including the one a cleanup would keep.' }
    if (lens === 'identifier') return { big: fmtNum(d.screeningMatches), unit: 'matched identifier signals', copy: 'This is screening, not clearance. No matched patterns does not establish HIPAA de-identification.' }
    const last = d.funnel[d.funnel.length - 1]
    return { big: fmtNum(last.rows), unit: `of ${fmtNum(d.funnel[0].rows)} rows pass every row check`, copy: 'Rows passing each measured check in sequence. Nothing is removed. Click a stage to see the rows that leave there.' }
  })()
  const legend: [string, string][] = lens === 'cohort'
    ? [...d.labels.map((l: string, i: number) => [groupColor(i), l] as [string, string]), [token('slate-200'), 'not recorded']]
    : lens === 'missing' ? (d.focusActive ? [[token('review-500'), 'missing in focus column'], [token('slate-100'), 'other rows']] : [[token('review-200'), '1 missing cell'], [token('review-500'), '2 or more'], [token('slate-100'), 'complete']])
    : lens === 'duplicate' ? [[token('review-500'), 'in a duplicate set'], [token('slate-100'), 'no exact copy']]
    : lens === 'identifier' ? [[token('brand-300'), 'values checked'], ...(d.rowsScanned < d.rowCount ? [[token('slate-200'), 'names only'] as [string, string]] : [])]
    : stage !== null ? [[token('review-500'), `leaves at "${d.funnel[stage].label}"`], [token('slate-100'), 'other rows']]
    : [[token('brand-300'), 'passes every check'], [token('review-500'), 'later duplicate copy'], [token('review-200'), 'has a missing cell'], [token('slate-300'), 'no group label']]

  const maxRows = d.funnel[0].rows || 1
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Choose a lens">
        {LENSES.map((l) => (
          <button key={l.id} type="button" aria-pressed={lens === l.id} onClick={() => switchLens(l.id)}
            className={`inline-flex items-center gap-2 rounded-full border py-1 pl-3 pr-1.5 text-sm font-semibold transition ${lens === l.id ? 'border-brand-500 bg-card text-ink-900 ring-4 ring-brand-100' : 'border-slate-200 bg-card text-ink-700 hover:border-brand-300'}`}>
            {l.name} <StatusBadge status={lensStatus[l.id]} small />
          </button>
        ))}
      </div>

      <div className={`grid gap-4 ${compact ? '' : 'lg:grid-cols-[minmax(0,1fr)_250px]'}`}>
        <div className="min-w-0 rounded-2xl border border-slate-200 bg-card p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs text-ink-500">{d.sampled ? `Even sample of ${fmtNum(d.sampleCount)} of ${fmtNum(d.rowCount)} rows` : `All ${fmtNum(d.rowCount)} rows`} · one square per row</div>
            <div className="flex items-center gap-1">
              <button className={`btn-ghost !p-1.5 ${mode === 'pan' ? 'bg-slate-100' : ''}`} aria-pressed={mode === 'pan'} title="Pan (drag)" onClick={() => setMode('pan')}><Hand size={15} /></button>
              <button className={`btn-ghost !p-1.5 ${mode === 'select' ? 'bg-slate-100' : ''}`} aria-pressed={mode === 'select'} title="Select rows (drag, or Shift-drag)" onClick={() => setMode('select')}><MousePointerSquareDashed size={15} /></button>
              <span className="mx-1 h-4 w-px bg-slate-200" />
              <button className="btn-ghost !p-1.5" title="Zoom out (−)" onClick={() => zoomAt(1 / 1.4)} disabled={view.k <= 1}><Minus size={15} /></button>
              <span className="w-10 text-center text-xs tabular-nums text-ink-500">{view.k.toFixed(1)}×</span>
              <button className="btn-ghost !p-1.5" title="Zoom in (+)" onClick={() => zoomAt(1.4)} disabled={view.k >= MAX_ZOOM}><Plus size={15} /></button>
              <button className="btn-ghost !p-1.5" title="Fit (0)" onClick={() => setView({ k: 1, x: 0, y: 0 })} disabled={view.k === 1}><Maximize2 size={15} /></button>
            </div>
          </div>
          <div ref={wrapRef} className="relative w-full min-w-0 select-none overflow-hidden" style={{ height: size.h }}>
            <canvas ref={canvasRef} tabIndex={0} onKeyDown={onKey} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp}
              onPointerLeave={(e) => { if (e.pointerType === 'mouse' && !drag.current) { setTip(null); setActive(-1) } }}
              aria-label={`Row map, ${LENSES.find((l) => l.id === lens)!.name} lens. ${readout.big} ${readout.unit}. Arrow keys inspect rows, plus and minus zoom.`}
              className={`absolute left-0 top-0 block rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${mode === 'select' ? 'cursor-crosshair' : view.k > 1 ? 'cursor-grab' : 'cursor-default'}`}
              style={{ width: size.w, height: size.h, touchAction: 'none' }} />
            {rect && <div className="pointer-events-none absolute border border-brand-500 bg-brand-500/10" style={{ left: Math.min(rect.x0, rect.x1), top: Math.min(rect.y0, rect.y1), width: Math.abs(rect.x1 - rect.x0), height: Math.abs(rect.y1 - rect.y0) }} />}
            {view.k > 1.05 && <canvas ref={miniRef} aria-hidden className="pointer-events-none absolute bottom-2 right-2 rounded-md border border-slate-200 shadow-card" style={{ width: 120 }} />}
            {tip && (
              <div className="pointer-events-none absolute z-10 min-w-[150px] rounded-xl bg-ink-900 px-3 py-2 text-xs leading-relaxed text-card shadow-lift"
                style={{ left: Math.min(size.w - 160, tip.x + 12), top: Math.max(0, tip.y - 70) }}>
                <div className="font-bold">Row {fmtNum(tip.r.row)}</div>
                <div>Group: {tip.r.group < 0 ? 'not recorded' : d.labels[tip.r.group]}</div>
                <div>Missing columns: {tip.r.missing}</div>
                <div>Exact duplicate: {tip.r.duplicate ? 'yes' : 'no'}</div>
              </div>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-500">
            {legend.map(([c, l]) => <span key={l} className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[3px]" style={{ background: c }} />{l}</span>)}
          </div>
          {picked && onSelectRows && (
            <div className="mt-2 flex flex-wrap items-center gap-2 rounded-xl border border-brand-200 bg-brand-50 px-3 py-2 text-sm text-brand-700 animate-rise">
              <Filter size={14} aria-hidden /><span className="font-semibold">{fmtNum(picked.length)} rows selected</span>
              <button className="btn-primary !px-3 !py-1 text-xs" onClick={() => { onSelectRows(picked, `${fmtNum(picked.length)} rows from the row map`); setPicked(null) }}>Filter the workspace</button>
              <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => setPicked(null)}><X size={13} />Clear</button>
            </div>
          )}
        </div>

        <aside className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4" aria-live="polite">
          <div className="eyebrow">{LENSES.find((l) => l.id === lens)!.name}</div>
          <div className="font-display text-4xl font-bold leading-none text-ink-900">{readout.big}</div>
          <div className="text-sm font-semibold text-ink-900">{readout.unit}</div>
          <p className="text-sm leading-relaxed text-ink-500">{readout.copy}</p>
          <div className="mt-1 space-y-1.5">
            <div className="eyebrow">Readiness funnel</div>
            {d.funnel.map((f: any, i: number) => (
              <button key={f.key} type="button" disabled={i === 0} onClick={() => switchLens('readiness', stage === i ? null : i)}
                aria-pressed={lens === 'readiness' && stage === i}
                className={`group block w-full rounded-lg px-2 py-1.5 text-left transition ${lens === 'readiness' && stage === i ? 'bg-card ring-2 ring-review-500' : 'hover:bg-card'} disabled:cursor-default`}>
                <div className="flex items-baseline justify-between gap-2 text-xs">
                  <span className="font-semibold text-ink-900">{f.label}</span>
                  <span className="tabular-nums text-ink-500">{fmtNum(f.rows)}</span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-200">
                  <div className="h-2 rounded-full bg-brand-500 transition-[width] duration-700" style={{ width: `${(f.rows / maxRows) * 100}%` }} />
                </div>
                {i > 0 && f.dropped > 0 && <div className="mt-0.5 text-[11px] text-review-700">−{fmtNum(f.dropped)} leave here</div>}
              </button>
            ))}
          </div>
        </aside>
      </div>
    </div>
  )
}
