import { useCallback, useEffect, useRef, useState } from 'react'
import { api, download, NO_FILTERS, type AnalysisRequest, type Filters, type FocusGroup, type Idea, type Roles } from './api'
import DrillDown from './components/DrillDown'
import Header from './components/Header'
import PlanScreen from './components/PlanScreen'
import StartScreen from './components/StartScreen'
import Tour, { TOUR_KEY } from './components/Tour'
import Workspace from './components/Workspace'
import { Note } from './components/ui'

const EMPTY_IDEA: Idea = { title: '', question: '', outcome: '', population: '', groups: '' }
const WORKFLOW_KIND = 'medguard-explorer-workflow'
const HASH = /^#\/w\/([a-z]+)$/

/** Filter history: every linked selection can be undone. */
function useFilterHistory() {
  const [state, setState] = useState<{ past: Filters[]; present: Filters; future: Filters[] }>({ past: [], present: NO_FILTERS, future: [] })
  const set = useCallback((next: Filters) => setState((s) => ({ past: [...s.past, s.present].slice(-30), present: next, future: [] })), [])
  const reset = useCallback((next: Filters = NO_FILTERS) => setState({ past: [], present: next, future: [] }), [])
  const undo = useCallback(() => setState((s) => (s.past.length ? { past: s.past.slice(0, -1), present: s.past[s.past.length - 1], future: [s.present, ...s.future] } : s)), [])
  const redo = useCallback(() => setState((s) => (s.future.length ? { past: [...s.past, s.present], present: s.future[0], future: s.future.slice(1) } : s)), [])
  return { filters: state.present, set, reset, undo, redo, canUndo: state.past.length > 0, canRedo: state.future.length > 0 }
}

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
  const history = useFilterHistory()
  const [results, setResults] = useState<any>(null)
  const [selected, setSelected] = useState('rows')
  const [drill, setDrill] = useState<string | null>(null)
  const [tourOpen, setTourOpen] = useState(false)
  const [loading, setLoading] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pendingWorkflow = useRef<any>(null)
  const requestId = useRef(0)

  useEffect(() => {
    api.health().then((h) => { setHealth(h); setSettings(h.settings); setWidgets(h.widgets) }).catch((e) => setError(`Cannot reach the local API: ${e.message}`))
    api.demos().then(setDemos).catch(() => undefined)
  }, [])

  const aiOn = useAi && !!health?.ai?.available
  const request = useCallback((): AnalysisRequest => ({
    dataset_id: dataset?.dataset_id, idea, roles, reference, settings, widgets, focus_groups: focus,
    filters: history.filters.labels, ranges: history.filters.ranges, row_ids: history.filters.rows?.ids ?? [], focus_column: null,
  }), [dataset, idea, roles, reference, settings, widgets, focus, history.filters])

  const acceptDataset = (d: any) => {
    if (!d.accepted) { setRejected(d); return }
    setRejected(null); setDataset(d); setPlan(null); setResults(null); history.reset(); setMaxStep(0)
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
    setLoading(aiOn ? 'Planning with the local model and rules (can take ~20 s)…' : 'Planning…'); setError(null)
    try {
      const p = await api.plan(dataset.dataset_id, idea, aiOn)
      setPlan(p)
      setRoles({ outcome: p.outcome.column, demographics: p.demographics.map((d: any) => d.column), identifiers: p.identifiers.map((d: any) => d.column) })
      setFocus(p.focus_groups); setWidgets(p.widgets); setReference({}); history.reset()
      setStep(1); setMaxStep(1)
    } catch (e: any) { setError(e.message) } finally { setLoading(null) }
  }

  // Latest request wins; earlier responses that arrive late are ignored.
  const run = useCallback(async (req: AnalysisRequest) => {
    const id = ++requestId.current
    setRunning(true); setError(null)
    try {
      const res = await api.analyze(req)
      if (id !== requestId.current) return
      setResults(res)
      setSelected((s) => (req.widgets.includes(s) ? s : req.widgets[0] ?? 'validation'))
      setStep(2); setMaxStep(2)
    } catch (e: any) { if (id === requestId.current) setError(e.message) } finally { if (id === requestId.current) setRunning(false) }
  }, [])

  // Linked selection and widget changes recompute from the file, debounced.
  useEffect(() => {
    if (step !== 2 || !results) return
    const t = setTimeout(() => run(request()), 250)
    return () => clearTimeout(t)
  }, [history.filters, widgets]) // eslint-disable-line react-hooks/exhaustive-deps

  // Drill-down panels are linkable: #/w/<widget>.
  useEffect(() => {
    const sync = () => { const m = location.hash.match(HASH); setDrill(m ? m[1] : null) }
    sync()
    addEventListener('hashchange', sync)
    return () => removeEventListener('hashchange', sync)
  }, [])
  // Opening from the workspace pushes one history entry, so Back closes the panel.
  // Panels reached by a shared link close by replacing the hash instead.
  const pushedPanel = useRef(false)
  const openWidget = (w: string) => { setSelected(w); pushedPanel.current = true; location.hash = `#/w/${w}` }
  const closeWidget = () => {
    if (pushedPanel.current) { pushedPanel.current = false; window.history.back(); return }
    window.history.replaceState(null, '', location.pathname + location.search)
    setDrill(null)
  }

  // First visit to the workspace starts the tour once.
  useEffect(() => {
    if (step !== 2 || !results) return
    let done = false
    try { done = localStorage.getItem(TOUR_KEY) === 'done' } catch { done = true }
    if (!done) setTimeout(() => setTourOpen(true), 600)
  }, [step, !!results]) // eslint-disable-line react-hooks/exhaustive-deps

  const addLabel = (column: string, label: string) => {
    if (!column || label == null) return
    const current = history.filters.labels[column] ?? []
    if (current.includes(label)) return
    history.set({ ...history.filters, labels: { ...history.filters.labels, [column]: [...current, label] } })
  }
  const handlers = {
    onFilter: addLabel,
    onRange: (column: string, range: [number, number]) => history.set({ ...history.filters, ranges: { ...history.filters.ranges, [column]: range } }),
    onRows: (ids: number[], source: string) => history.set({ ...history.filters, rows: { ids, source } }),
  }

  const saveWorkflow = () => download(`medguard-workflow-${new Date().toISOString().slice(0, 10)}.json`, {
    kind: WORKFLOW_KIND, version: 2, saved_at: new Date().toISOString(), idea, roles, focus_groups: focus, reference,
    settings, widgets, filters: history.filters, dataset: dataset ? { name: dataset.name, source: dataset.source, fingerprint: dataset.fingerprint } : null,
  })
  const loadWorkflow = async (file: File) => {
    try {
      const wf = JSON.parse(await file.text())
      if (wf.kind !== WORKFLOW_KIND) throw new Error('This file is not a MedGuard Explorer workflow.')
      const saved: Filters = wf.version >= 2 ? { ...NO_FILTERS, ...wf.filters } : { ...NO_FILTERS, labels: wf.filters ?? {} }
      setIdea({ ...EMPTY_IDEA, ...wf.idea }); setRoles(wf.roles); setFocus(wf.focus_groups ?? []); setReference(wf.reference ?? {})
      setSettings({ ...health?.settings, ...wf.settings }); setWidgets(wf.widgets ?? health?.widgets ?? [])
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
      history.reset(saved)
      setStep(1); setMaxStep(1)
    } catch (e: any) { setError(e.message) }
  }
  const exportReport = async () => {
    try { download(`medguard-readiness-report-${results.dataset.fingerprint.slice(0, 10)}.json`, await api.report(request())) }
    catch (e: any) { setError(e.message) }
  }
  const order = results ? results.board.map((b: any) => b.id) : []

  return (
    <div className="min-h-screen bg-paper font-sans">
      <Header step={step} onStep={setStep} maxStep={maxStep} ai={health?.ai} useAi={useAi} onToggleAi={() => setUseAi(!useAi)}
        onSave={dataset ? saveWorkflow : undefined} onLoad={loadWorkflow} onExport={results ? exportReport : undefined}
        onTour={step === 2 && results ? () => setTourOpen(true) : undefined} />
      {health?.public && (
        <div className="border-b border-review-200 bg-review-50 px-4 py-2 text-center text-sm text-review-700" role="note">
          <b>Public demo.</b> Use the bundled synthetic datasets or data that is already de-identified; do not upload patient records.
          Files are processed in this server's memory, never written to disk, kept apart from other visitors, and deleted after {health.retention_minutes} minutes.
        </div>
      )}
      {error && <div className="mx-auto max-w-[1500px] px-6 pt-4"><Note tone="warn">{error}</Note></div>}
      {step === 0 && <StartScreen idea={idea} setIdea={setIdea} demos={demos} dataset={dataset} loading={loading}
        onDemo={loadDemo} onUpload={upload} onPlan={makePlan} rejected={rejected}
        publicDemo={!!health?.public} retentionMinutes={health?.retention_minutes} />}
      {step === 1 && plan && dataset && <PlanScreen dataset={dataset} plan={plan} titles={health?.titles ?? {}} roles={roles} setRoles={setRoles}
        focus={focus} setFocus={setFocus} reference={reference} setReference={setReference} settings={settings} setSettings={setSettings}
        widgets={widgets} setWidgets={setWidgets} running={running} onRun={() => run(request())} />}
      {step === 2 && results && <Workspace idea={idea} dataset={dataset} roles={roles} results={results} titles={health?.titles ?? {}}
        widgets={widgets} setWidgets={setWidgets} selected={selected} setSelected={setSelected} onOpen={openWidget}
        filters={history.filters} setFilters={history.set} history={history} focus={focus} running={running} />}
      {step === 2 && results && drill && order.includes(drill) && (
        <DrillDown widget={drill} order={order} titles={health?.titles ?? {}} results={results} focus={focus} handlers={handlers}
          aiOn={aiOn} onExplain={(w) => api.explain(request(), w, aiOn)} onNavigate={(w) => { setSelected(w); location.replace(`#/w/${w}`) }} onClose={closeWidget} />
      )}
      <Tour open={tourOpen} onClose={() => setTourOpen(false)} />
      <footer className="mx-auto max-w-[1500px] px-6 py-8 text-center text-xs text-ink-500">
        MedGuard Explorer · runs locally · descriptive dataset-readiness evidence, not model validation, fairness certification or de-identification.
      </footer>
    </div>
  )
}
