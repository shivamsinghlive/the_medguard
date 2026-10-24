// Thin client for the local MedGuard Explorer API (src/explorer/server.py).
export type Idea = { title: string; question: string; outcome: string; population: string; groups: string }
export type Roles = { outcome: string | null; demographics: string[]; identifiers: string[] }
export type FocusGroup = { column: string; label: string | null; concept: string; missing: boolean; reason: string }
export type Status = 'review_needed' | 'descriptive_only' | 'insufficient_evidence' | 'no_patterns_found' | 'not_available'

/** Everything that narrows the analysed rows. The stored dataset is never changed. */
export type Filters = {
  labels: Record<string, string[]>
  ranges: Record<string, [number, number]>
  rows: { ids: number[]; source: string } | null
}
export const NO_FILTERS: Filters = { labels: {}, ranges: {}, rows: null }
export const hasFilters = (f: Filters) => Object.keys(f.labels).length > 0 || Object.keys(f.ranges).length > 0 || !!f.rows

export type AnalysisRequest = {
  dataset_id: string
  idea: Idea
  roles: Roles
  reference: Record<string, Record<string, number>>
  settings: Record<string, number>
  filters: Record<string, string[]>
  ranges: Record<string, [number, number]>
  row_ids: number[]
  focus_column: string | null
  widgets: string[]
  focus_groups: FocusGroup[]
}

export type ChangeAction = Record<string, unknown> & { action: string }

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* keep status text */ }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json()
}

const json = (body: unknown): RequestInit => ({
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
})

export const api = {
  health: () => call<any>('/api/health'),
  demos: () => call<{ name: string; bytes: number }[]>('/api/demos'),
  loadDemo: (name: string) => call<any>(`/api/datasets/demo/${encodeURIComponent(name)}`, { method: 'POST' }),
  upload: (file: File) => call<any>(`/api/datasets/upload?filename=${encodeURIComponent(file.name)}`,
    { method: 'POST', body: file, headers: { 'Content-Type': 'application/octet-stream' } }),
  plan: (dataset_id: string, idea: Idea, use_ai: boolean) => call<any>('/api/plan', json({ dataset_id, idea, use_ai })),
  analyze: (req: AnalysisRequest) => call<any>('/api/analyze', json(req)),
  explain: (req: AnalysisRequest, widget: string, use_ai: boolean) => call<any>('/api/explain', json({ ...req, widget, use_ai })),
  report: (req: AnalysisRequest) => call<any>('/api/report', json(req)),
  preview: (dataset_id: string, roles: Roles, actions: ChangeAction[]) => call<any>('/api/preview', json({ dataset_id, roles, actions })),
  accept: (dataset_id: string, preview_id: string) => call<any>('/api/preview/accept', json({ dataset_id, preview_id })),
  copyUrl: (dataset_id: string, preview_id: string) =>
    `/api/preview/copy.csv?dataset_id=${encodeURIComponent(dataset_id)}&preview_id=${encodeURIComponent(preview_id)}`,
}

export function download(name: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  a.click()
  URL.revokeObjectURL(url)
}
