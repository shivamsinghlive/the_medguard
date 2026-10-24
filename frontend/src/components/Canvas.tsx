import {
  Background, Controls, Handle, MiniMap, Position, ReactFlow, ReactFlowProvider, useNodesState, useReactFlow,
  type Edge, type Node, type NodeProps,
} from '@xyflow/react'
import {
  BarChart3, Database, FileCheck2, FileText, Fingerprint, Grid3x3, KeyRound, LayoutGrid, Layers, LineChart, Network,
  PieChart, ScatterChart, Target, Users,
} from 'lucide-react'
import { memo, useEffect, useMemo, useRef } from 'react'
import { dotColor, STATUS } from './ui'

export const ICONS: Record<string, any> = {
  validation: FileCheck2, screening: KeyRound, rows: LayoutGrid, outcome: PieChart, representation: Users, groups: BarChart3,
  intersections: Grid3x3, leakage: Target, features: Layers, missingness: Fingerprint, correlations: Network,
  distributions: LineChart, projection: ScatterChart,
}

/** Tiny inline visual per card: shares (segmented bar) or a single proportion (progress bar). */
export type Spark = { kind: 'shares'; values: number[] } | { kind: 'share'; value: number; review?: boolean } | null

type CardData = { title: string; status: string; headline: string; count: number; icon: any; selected: boolean; spark: Spark }

const SPARK_COLORS = ['--brand-500', '--teal-500', '--brand-300', '--ink-700']

function SparkBar({ spark }: { spark: Spark }) {
  if (!spark) return null
  if (spark.kind === 'share') {
    return (
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100" aria-hidden>
        <div className="h-1.5 rounded-full" style={{ width: `${Math.max(2, Math.min(100, spark.value * 100))}%`, background: `rgb(var(${spark.review ? '--review-500' : '--brand-500'}))` }} />
      </div>
    )
  }
  const total = spark.values.reduce((a, b) => a + b, 0) || 1
  return (
    <div className="mt-2 flex h-1.5 overflow-hidden rounded-full bg-slate-100" aria-hidden>
      {spark.values.map((v, i) => <div key={i} style={{ width: `${(v / total) * 100}%`, background: `rgb(var(${SPARK_COLORS[i % 4]}))` }} />)}
    </div>
  )
}

const WidgetNode = memo(({ data }: NodeProps<Node<CardData>>) => {
  const Icon = data.icon
  const meta = STATUS[data.status] ?? STATUS.not_available
  return (
    <div className={`w-[220px] rounded-2xl border bg-card px-3 py-2.5 shadow-card transition ${data.selected ? 'border-brand-500 ring-4 ring-brand-100' : 'border-slate-200 hover:border-brand-300 hover:shadow-lift'} ${data.status === 'review_needed' ? 'border-l-4 border-l-review-500' : ''}`}
      title={`${data.title}: ${meta.label}. Double-click to open.`}>
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-slate-300" />
      <div className="flex items-center gap-2">
        <div className="grid h-7 w-7 place-items-center rounded-lg bg-slate-100 text-ink-700"><Icon size={15} /></div>
        <div className="min-w-0 flex-1 truncate text-[13px] font-semibold text-ink-900">{data.title}</div>
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: dotColor(data.status) }} aria-label={meta.label} />
        {data.count > 0 && <span className="rounded-full bg-review-100 px-1.5 text-[10px] font-bold text-review-700">{data.count}</span>}
      </div>
      <div className="mt-1 line-clamp-2 text-[11px] leading-snug text-ink-500">{data.headline}</div>
      <SparkBar spark={data.spark} />
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-slate-300" />
    </div>
  )
})

const COLUMNS: Record<string, [number, number]> = {
  validation: [1, 0], screening: [1, 1], rows: [1, 2],
  outcome: [3, 0], representation: [3, 1], groups: [3, 2], intersections: [3, 3], projection: [3, 4],
  leakage: [4, 0], features: [4, 1], missingness: [4, 2], correlations: [4, 3], distributions: [4, 4],
}
const ANALYSIS = ['outcome', 'representation', 'groups', 'intersections', 'leakage', 'features', 'missingness', 'correlations', 'distributions', 'projection']

type Props = {
  board: any[]; sparks: Record<string, Spark>; selected: string; onSelect: (id: string) => void; onOpen: (id: string) => void
  datasetName: string; question: string; rows: string
}

function CanvasInner({ board, sparks, selected, onSelect, onOpen, datasetName, question, rows }: Props) {
  const nodeTypes = useMemo(() => ({ widget: WidgetNode }), [])
  const flow = useReactFlow()
  const wrap = useRef<HTMLDivElement>(null)
  const { nodes, edges, order } = useMemo(() => {
    const X = (c: number) => c * 260, Y = (r: number) => r * 112
    const review = 'rgb(var(--review-500))'
    const nodes: Node<CardData>[] = [
      { id: 'data', type: 'widget', position: { x: X(0), y: Y(1) }, data: { title: 'Dataset', status: 'descriptive_only', headline: `${datasetName} · ${rows}`, count: 0, icon: Database, selected: false, spark: null } },
      { id: 'plan', type: 'widget', position: { x: X(2), y: Y(1.5) }, data: { title: 'Research plan', status: 'descriptive_only', headline: question || 'Your research idea', count: 0, icon: FileText, selected: false, spark: null } },
    ]
    const edges: Edge[] = [{ id: 'd-v', source: 'data', target: 'validation' }]
    for (const card of board) {
      const [c, r] = COLUMNS[card.id] ?? [5, 0]
      nodes.push({ id: card.id, type: 'widget', position: { x: X(c), y: Y(r) }, data: { title: card.title, status: card.status, headline: card.headline, count: card.finding_count, icon: ICONS[card.id] ?? Layers, selected: selected === card.id, spark: sparks[card.id] ?? null } })
      if (card.id === 'screening' || card.id === 'rows') edges.push({ id: `v-${card.id}`, source: 'validation', target: card.id })
      if (ANALYSIS.includes(card.id)) edges.push({ id: `p-${card.id}`, source: 'plan', target: card.id, animated: card.status === 'review_needed', style: card.status === 'review_needed' ? { stroke: review, strokeWidth: 1.75 } : undefined })
    }
    edges.push({ id: 'v-p', source: 'validation', target: 'plan' }, { id: 's-p', source: 'screening', target: 'plan' })
    const order = board.map((b) => b.id)
    return { nodes, edges, order }
  }, [board, sparks, selected, datasetName, question, rows])

  // Keep positions the user dragged while statuses and selection update.
  const [rfNodes, setRfNodes, onNodesChange] = useNodesState<Node<CardData>>(nodes)
  useEffect(() => {
    setRfNodes((prev) => nodes.map((n) => ({ ...n, position: prev.find((p) => p.id === n.id)?.position ?? n.position })))
  }, [nodes, setRfNodes])

  // Glide to the selected card.
  useEffect(() => {
    const node = rfNodes.find((n) => n.id === selected)
    if (node) flow.setCenter(node.position.x + 110, node.position.y + 40, { zoom: Math.max(flow.getZoom(), 0.9), duration: matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 450 })
  }, [selected]) // eslint-disable-line react-hooks/exhaustive-deps

  const onKey = (e: React.KeyboardEvent) => {
    const i = order.indexOf(selected)
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); onSelect(order[(i + 1) % order.length]) }
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); onSelect(order[(i - 1 + order.length) % order.length]) }
    else if (e.key === 'Enter') { e.preventDefault(); onOpen(selected) }
  }
  const pick = (id: string) => (id === 'data' ? 'validation' : id === 'plan' ? selected : id)

  return (
    <div ref={wrap} tabIndex={0} onKeyDown={onKey} data-tour="canvas"
      aria-label="Workflow canvas. Arrow keys move between widgets, Enter opens one. Scroll to zoom, drag to pan."
      className="relative h-[540px] w-full overflow-hidden rounded-2xl border border-slate-200 bg-card focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
      style={{ backgroundImage: 'radial-gradient(rgb(var(--slate-200)) 1px, transparent 1px)', backgroundSize: '18px 18px' }}>
      <ReactFlow nodes={rfNodes} onNodesChange={onNodesChange} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.12 }}
        onNodeClick={(_, n) => onSelect(pick(n.id))} onNodeDoubleClick={(_, n) => onOpen(pick(n.id))}
        nodesConnectable={false} minZoom={0.25} maxZoom={2.2} zoomOnDoubleClick={false} proOptions={{ hideAttribution: true }}>
        <Background gap={18} color="transparent" />
        <MiniMap pannable zoomable position="bottom-left" nodeBorderRadius={8} maskColor="rgb(var(--paper) / 0.6)"
          nodeColor={(n: any) => (n.data?.status === 'review_needed' ? 'rgb(var(--review-500))' : n.data?.selected ? 'rgb(var(--brand-500))' : 'rgb(var(--slate-300))')} />
        <Controls showInteractive={false} position="bottom-right" />
      </ReactFlow>
    </div>
  )
}

export default function Canvas(props: Props) {
  return <ReactFlowProvider><CanvasInner {...props} /></ReactFlowProvider>
}
