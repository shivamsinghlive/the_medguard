import { useCallback, useEffect, useRef, useState } from 'react'
import { api, download, type AnalysisRequest, type FocusGroup, type Idea, type Roles } from './api'
import Header from './components/Header'
import PlanScreen from './components/PlanScreen'
import StartScreen from './components/StartScreen'
import Workspace from './components/Workspace'
import { Note } from './components/ui'

const EMPTY_IDEA: Idea = { title: '', question: '', outcome: '', population: '', groups: '' }
const WORKFLOW_KIND = 'medguard-explorer-workflow'

export default function App() {
  const [health, setHealth] = useState<any>(null)
  const [demos, setDemos] = useState<{ name: string; bytes: number }[]>([])
  const [step, setStep] = useState(0)
  const [maxStep, setMaxStep] = useState(0)
  const [useAi, setUseAi] = useState(true)
  const [idea, setIdea] = useState<Idea>(EMPTY_IDEA)
  const [dataset, setDataset] = useState<any>(null)
  const [rejected, setRejected] = useState<any>(null)
  const [plan, setPlan] = useState<any>(null)
  const [roles, setRoles] = useState<Roles>({ outcome: null, demographics: [], identifiers: [] })
  const [focus, setFocus] = useState<FocusGroup[]>([])
  const [reference, setReference] = useState<Record<string, Record<string, number>>>({})
  const [settings, setSettings] = useState<Record<string, number>>({})
  const [widgets, setWidgets] = useState<string[]>([])
  const [filters, setFilters] = useState<Record<string, string[]>>({})
  const [results, setResults] = useState<any>(null)
  const [selected, setSelected] = useState('outcome')
  const [loading, setLoading] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pendingWorkflow = useRef<any>(null)

  useEffect(() => {
    api.health().then((h) => { setHealth(h); setSettings(h.settings); setWidgets(h.widgets) }).catch((e) => setError(`Cannot reach the local API: ${e.message}`))
    api.demos().then(setDemos).catch(() => undefined)
  }, [])

  const aiOn = useAi && !!health?.ai?.available
  const request = useCallback((): AnalysisRequest => ({
    dataset_id: dataset?.dataset_id, idea, roles, reference, settings, filters, widgets, focus_groups: focus,
  }), [dataset, idea, roles, reference, settings, filters, widgets, focus])

  const acceptDataset = (d: any) => {
    if (!d.accepted) { setRejected(d); return }
    setRejected(null); setDataset(d); setPlan(null); setResults(null); setFilters({}); setMaxStep(0)
    const wf = pendingWorkflow.current
    if (wf) {
      pendingWorkflow.current = null
      if (wf.dataset?.fingerprint && wf.dataset.fingerprint !== d.fingerprint) setError('This dataset differs from the one the workflow was saved with; results will differ.')
    }
  }
  const loadDemo = async (name: string) => {
    setLoading('Validating dataset…'); setError(null)
    try { acceptDataset(await api.loadDemo(name)) } catch (e: any) { setError(e.message) } finally { setLoading(null) }
  }
  const upload = async (file: File) => {
    setLoading(`Validating ${file.name}…`); setError(null)
    try { acceptDataset(await api.upload(file)) } catch (e: any) { setError(e.message) } finally { setLoading(null) }
  }

  const makePlan = async () => {
    setLoading(aiOn ? 'Planning with the local AI and rules (can take ~20 s)…' : 'Planning…'); setError(null)
    try {
      const p = await api.plan(dataset.dataset_id, idea, aiOn)
      setPlan(p)
      setRoles({ outcome: p.outcome.column, demographics: p.demographics.map((d: any) => d.column), identifiers: p.identifiers.map((d: any) => d.column) })
      setFocus(p.focus_groups); setWidgets(p.widgets); setReference({}); setFilters({})
      setStep(1); setMaxStep(1)
    } catch (e: any) { setError(e.message) } finally { setLoading(null) }
  }

  const run = useCallback(async (req: AnalysisRequest) => {
    setRunning(true); setError(null)
    try {
      const res = await api.analyze(req)
      setResults(res)
      setSelected((s) => (req.widgets.includes(s) ? s : req.widgets[0] ?? 'validation'))
      setStep(2); setMaxStep(2)
    } catch (e: any) { setError(e.message) } finally { setRunning(false) }
  }, [])

  // Linked selection, widget and setting changes recompute from the file.
  useEffect(() => {
    if (step === 2 && results) run(request())
  }, [filters, widgets]) // eslint-disable-line react-hooks/exhaustive-deps

  const saveWorkflow = () => download(`medguard-workflow-${new Date().toISOString().slice(0, 10)}.json`, {
    kind: WORKFLOW_KIND, version: 1, saved_at: new Date().toISOString(), idea, roles, focus_groups: focus, reference,
    settings, widgets, filters, dataset: dataset ? { name: dataset.name, source: dataset.source, fingerprint: dataset.fingerprint } : null,
  })
  const loadWorkflow = async (file: File) => {
    try {
      const wf = JSON.parse(await file.text())
      if (wf.kind !== WORKFLOW_KIND) throw new Error('This file is not a MedGuard Explorer workflow.')
      setIdea({ ...EMPTY_IDEA, ...wf.idea }); setRoles(wf.roles); setFocus(wf.focus_groups ?? []); setReference(wf.reference ?? {})
      setSettings({ ...health?.settings, ...wf.settings }); setWidgets(wf.widgets ?? health?.widgets ?? []); setFilters(wf.filters ?? {})
      setPlan({ source: 'rules', ai: { used: false, error: null, model: '' }, outcome: { column: wf.roles.outcome, reason: 'from saved workflow', source: 'rules' },
        demographics: wf.roles.demographics.map((c: string) => ({ column: c, reason: 'from saved workflow', source: 'rules' })),
        identifiers: wf.roles.identifiers.map((c: string) => ({ column: c, reason: 'from saved workflow', source: 'rules' })), focus_groups: wf.focus_groups ?? [], notes: [], widgets: wf.widgets })
      if (wf.dataset?.source === 'bundled_synthetic_demo' && wf.dataset.name !== dataset?.name) {
        pendingWorkflow.current = wf
        acceptDataset(await api.loadDemo(wf.dataset.name))
      } else if (!dataset) {
        setError(`Workflow loaded. Now load the dataset it was saved with: ${wf.dataset?.name ?? 'unknown'}.`)
        setStep(0); return
      }
      setStep(1); setMaxStep(1)
    } catch (e: any) { setError(e.message) }
  }
  const exportReport = async () => {
    try { download(`medguard-readiness-report-${results.dataset.fingerprint.slice(0, 10)}.json`, await api.report(request())) }
    catch (e: any) { setError(e.message) }
  }

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      <Header step={step} onStep={setStep} maxStep={maxStep} ai={health?.ai} useAi={useAi} onToggleAi={() => setUseAi(!useAi)}
        onSave={dataset ? saveWorkflow : undefined} onLoad={loadWorkflow} onExport={results ? exportReport : undefined} />
      {error && <div className="mx-auto max-w-[1500px] px-6 pt-4"><Note tone="warn">{error}</Note></div>}
      {step === 0 && <StartScreen idea={idea} setIdea={setIdea} demos={demos} dataset={dataset} loading={loading}
        onDemo={loadDemo} onUpload={upload} onPlan={makePlan} rejected={rejected} />}
      {step === 1 && plan && dataset && <PlanScreen dataset={dataset} plan={plan} titles={health?.titles ?? {}} roles={roles} setRoles={setRoles}
        focus={focus} setFocus={setFocus} reference={reference} setReference={setReference} settings={settings} setSettings={setSettings}
        widgets={widgets} setWidgets={setWidgets} running={running} onRun={() => run(request())} />}
      {step === 2 && results && <Workspace idea={idea} results={results} titles={health?.titles ?? {}} widgets={widgets} setWidgets={setWidgets}
        selected={selected} setSelected={setSelected} filters={filters} setFilters={setFilters} focus={focus} running={running} aiOn={aiOn}
        onExplain={(w) => api.explain(request(), w, aiOn)} />}
      <footer className="mx-auto max-w-[1500px] px-6 py-8 text-center text-xs text-ink-500">
        MedGuard Explorer prototype · runs locally · descriptive dataset-readiness evidence, not model validation, fairness certification or de-identification.
      </footer>
    </div>
  )
}
