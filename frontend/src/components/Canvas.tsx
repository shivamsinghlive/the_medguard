import { Background, Controls, Handle, Position, ReactFlow, useNodesState, type Edge, type Node, type NodeProps } from '@xyflow/react'
import {
  BarChart3, Database, FileCheck2, FileText, Fingerprint, Grid3x3, KeyRound, Layers, LineChart, Network,
  PieChart, ScatterChart, Target, Users,
} from 'lucide-react'
import { memo, useEffect, useMemo } from 'react'
import { STATUS } from './ui'

export const ICONS: Record<string, any> = {
  validation: FileCheck2, screening: KeyRound, outcome: PieChart, representation: Users, groups: BarChart3,
  intersections: Grid3x3, leakage: Target, features: Layers, missingness: Fingerprint, correlations: Network,
  distributions: LineChart, projection: ScatterChart,
}

type CardData = { title: string; status: string; headline: string; count: number; icon: any; selected: boolean; kind: 'widget' | 'source' | 'sink' }

const WidgetNode = memo(({ data }: NodeProps<Node<CardData>>) => {
  const meta = STATUS[data.status] ?? STATUS.not_available
  const Icon = data.icon
  return (
    <div className={`w-[210px] rounded-2xl border bg-white px-3 py-2.5 shadow-card transition ${data.selected ? 'border-brand-500 ring-4 ring-brand-100' : 'border-slate-200 hover:border-brand-300'}`}>
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-slate-300" />
      <div className="flex items-center gap-2">
        <div className="grid h-7 w-7 place-items-center rounded-lg" style={{ background: `${meta.dot}1a`, color: meta.dot }}><Icon size={15} /></div>
        <div className="min-w-0 flex-1 truncate text-[13px] font-semibold text-ink-900">{data.title}</div>
        {data.count > 0 && <span className="rounded-full px-1.5 text-[10px] font-bold text-white" style={{ background: meta.dot }}>{data.count}</span>}
      </div>
      <div className="mt-1 line-clamp-2 text-[11px] leading-snug text-ink-500">{data.headline}</div>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-slate-300" />
    </div>
  )
})

const COLUMNS: Record<string, [number, number]> = {
  validation: [1, 0], screening: [1, 1],
  outcome: [3, 0], representation: [3, 1], groups: [3, 2], intersections: [3, 3],
  leakage: [4, 0], features: [4, 1], missingness: [4, 2], correlations: [4, 3], distributions: [4, 4], projection: [3, 4],
}
const ANALYSIS = ['outcome', 'representation', 'groups', 'intersections', 'leakage', 'features', 'missingness', 'correlations', 'distributions', 'projection']

type Props = { board: any[]; selected: string; onSelect: (id: string) => void; datasetName: string; question: string; rows: string }

export default function Canvas({ board, selected, onSelect, datasetName, question, rows }: Props) {
  const nodeTypes = useMemo(() => ({ widget: WidgetNode }), [])
  const { nodes, edges } = useMemo(() => {
    const X = (c: number) => c * 250, Y = (r: number) => r * 104
    const nodes: Node<CardData>[] = [
      { id: 'data', type: 'widget', position: { x: X(0), y: Y(0.5) }, data: { title: 'Dataset', status: 'descriptive_only', headline: `${datasetName} · ${rows}`, count: 0, icon: Database, selected: selected === 'validation', kind: 'source' } },
      { id: 'plan', type: 'widget', position: { x: X(2), y: Y(1.5) }, data: { title: 'Research plan', status: 'descriptive_only', headline: question || 'Your research idea', count: 0, icon: FileText, selected: false, kind: 'source' } },
    ]
    const edges: Edge[] = [{ id: 'd-v', source: 'data', target: 'validation' }]
    for (const card of board) {
      const [c, r] = COLUMNS[card.id] ?? [5, 0]
      nodes.push({ id: card.id, type: 'widget', position: { x: X(c), y: Y(r) }, data: { title: card.title, status: card.status, headline: card.headline, count: card.finding_count, icon: ICONS[card.id] ?? Layers, selected: selected === card.id, kind: 'widget' } })
      if (card.id === 'screening') edges.push({ id: 'v-s', source: 'validation', target: 'screening' })
      if (ANALYSIS.includes(card.id)) edges.push({ id: `p-${card.id}`, source: 'plan', target: card.id, animated: card.status === 'review_needed', style: { stroke: card.status === 'review_needed' ? '#f97316' : '#cbd5e1', strokeWidth: 1.5 } })
    }
    edges.push({ id: 'v-p', source: 'validation', target: 'plan' }, { id: 's-p', source: 'screening', target: 'plan' })
    return { nodes, edges }
  }, [board, selected, datasetName, question, rows])
  // Keep positions the user dragged while statuses and selection update.
  const [rfNodes, setRfNodes, onNodesChange] = useNodesState<Node<CardData>>(nodes)
  useEffect(() => {
    setRfNodes((prev) => nodes.map((n) => ({ ...n, position: prev.find((p) => p.id === n.id)?.position ?? n.position })))
  }, [nodes, setRfNodes])

  return (
    <div className="h-[520px] w-full overflow-hidden rounded-2xl border border-slate-200 bg-[radial-gradient(#e2e8f0_1px,transparent_1px)] [background-size:18px_18px]">
      <ReactFlow nodes={rfNodes} onNodesChange={onNodesChange} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.15 }}
        onNodeClick={(_, n) => onSelect(n.id === 'data' ? 'validation' : n.id === 'plan' ? selected : n.id)}
        nodesConnectable={false} minZoom={0.4} maxZoom={1.6} proOptions={{ hideAttribution: true }}>
        <Background gap={18} color="transparent" />
        <Controls showInteractive={false} position="bottom-right" />
      </ReactFlow>
    </div>
  )
}
