import ReactECharts from 'echarts-for-react'
import { Filter, MousePointerClick, X, ZoomIn } from 'lucide-react'
import { useCallback, useMemo, useRef, useState } from 'react'
import { themed, token, useScheme } from './theme'

export type BrushPick = { label: string; apply: () => void }

type Props = {
  option: any
  height?: number
  label: string
  onPick?: (params: any) => void
  /** Wheel zoom plus a slider on these axes. Drag is left free for brushing. */
  zoom?: 'x' | 'y' | 'xy'
  /** Turn a finished brush into a pending filter; return null to ignore it. */
  brush?: { type: 'lineX' | 'rect' | 'polygon'; toPick: (event: any, chart: any) => BrushPick | null }
  hint?: string
}

export default function Chart({ option, height = 300, label, onPick, zoom, brush, hint }: Props) {
  useScheme()
  const ref = useRef<ReactECharts>(null)
  const [pending, setPending] = useState<BrushPick | null>(null)

  const full = useMemo(() => {
    const extra: any = {}
    if (zoom) {
      const axes = zoom === 'xy' ? ['x', 'y'] : [zoom]
      extra.dataZoom = axes.flatMap((axis) => [
        { type: 'inside', [`${axis}AxisIndex`]: 0, zoomOnMouseWheel: true, moveOnMouseMove: !brush, moveOnMouseWheel: false },
        { type: 'slider', [`${axis}AxisIndex`]: 0, height: axis === 'x' ? 14 : undefined, width: axis === 'y' ? 14 : undefined,
          bottom: axis === 'x' ? 4 : undefined, right: axis === 'y' ? 4 : undefined, borderColor: 'transparent',
          backgroundColor: token('slate-100'), fillerColor: token('brand-500', 0.15), handleSize: '90%',
          dataBackground: { lineStyle: { color: token('slate-300') }, areaStyle: { color: token('slate-200') } },
          textStyle: { color: token('ink-500') }, showDetail: false },
      ])
      extra.grid = { ...(option.grid ?? { left: 8, right: 16, top: 36, containLabel: true }),
        bottom: axes.includes('x') ? 34 : option.grid?.bottom ?? 8, right: axes.includes('y') ? 30 : option.grid?.right ?? 16 }
    }
    if (brush) {
      extra.brush = { brushType: brush.type, brushMode: 'single', xAxisIndex: brush.type === 'lineX' ? 0 : undefined,
        throttleType: 'debounce', throttleDelay: 200, removeOnClick: true,
        brushStyle: { borderWidth: 1, color: token('brand-500', 0.12), borderColor: token('brand-500', 0.7) },
        outOfBrush: { colorAlpha: 0.25 } }
      extra.toolbox = { show: false }
    }
    return themed({ ...option, ...extra })
  }, [option, zoom, brush])

  const onReady = useCallback((chart: any) => {
    if (brush) chart.dispatchAction({ type: 'takeGlobalCursor', key: 'brush', brushOption: { brushType: brush.type, brushMode: 'single' } })
  }, [brush])

  const events = useMemo(() => {
    const e: Record<string, (p: any) => void> = {}
    if (onPick) e.click = onPick
    if (brush) e.brushEnd = (event: any) => {
      const chart = ref.current?.getEchartsInstance()
      setPending(event.areas?.length ? brush.toPick(event, chart) : null)
    }
    return e
  }, [onPick, brush])

  const clear = () => {
    ref.current?.getEchartsInstance().dispatchAction({ type: 'brush', areas: [] })
    setPending(null)
  }

  return (
    <figure className="m-0">
      <div role="img" aria-label={label}>
        <ReactECharts ref={ref} option={full} style={{ height }} notMerge onEvents={events} onChartReady={onReady} />
      </div>
      {pending && (
        <div className="mt-2 flex flex-wrap items-center gap-2 rounded-xl border border-brand-200 bg-brand-50 px-3 py-2 text-sm text-brand-700 animate-rise">
          <Filter size={14} aria-hidden /> <span className="font-semibold">{pending.label}</span>
          <button className="btn-primary !px-3 !py-1 text-xs" onClick={() => { pending.apply(); clear() }}>Filter the workspace</button>
          <button className="btn-ghost !px-2 !py-1 text-xs" onClick={clear}><X size={13} />Clear</button>
        </div>
      )}
      {(hint || zoom || brush || onPick) && !pending && (
        <figcaption className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-500">
          {onPick && <span className="inline-flex items-center gap-1"><MousePointerClick size={12} aria-hidden />Click a bar to filter</span>}
          {brush && <span className="inline-flex items-center gap-1"><Filter size={12} aria-hidden />Drag to select {brush.type === 'lineX' ? 'a range' : 'rows'}</span>}
          {zoom && <span className="inline-flex items-center gap-1"><ZoomIn size={12} aria-hidden />Scroll to zoom, use the slider to pan</span>}
          {hint && <span>{hint}</span>}
        </figcaption>
      )}
    </figure>
  )
}
