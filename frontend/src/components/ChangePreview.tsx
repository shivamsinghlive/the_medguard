import { Download, Lock, ShieldCheck, Wand2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api, type ChangeAction, type Roles } from '../api'
import Chart from '../charts/Chart'
import { prefersReducedMotion, token } from '../charts/theme'
import { Note, Spinner, fmtNum } from './ui'

function Identicon({ hash, tone }: { hash: string; tone: 'source' | 'copy' }) {
  const hex = (hash || '').replace(/[^0-9a-f]/gi, '')
  const cells: boolean[] = []
  for (let r = 0; r < 5; r++) {
    const bits = [0, 1, 2].map((c) => parseInt(hex[r * 3 + c] || '0', 16) % 2 === 1)
    cells.push(bits[0], bits[1], bits[2], bits[1], bits[0])
  }
  return (
    <div className="grid w-14 grid-cols-5 gap-0.5" role="img" aria-label={`Fingerprint pattern ${hex.slice(0, 8)}`}>
      {cells.map((on, i) => <i key={i} className="block aspect-square rounded-[2px]" style={{ background: on ? `rgb(var(${tone === 'source' ? '--ink-900' : '--brand-500'}))` : 'rgb(var(--slate-100))' }} />)}
    </div>
  )
}

function RowDrop({ changes }: { changes: any }) {
  const removed = useMemo(() => new Set<number>(changes.removed), [changes.removed])
  const [gone, setGone] = useState(changes.accepted || prefersReducedMotion() ? changes.removed.length : 0)
  useEffect(() => {
    if (changes.accepted || prefersReducedMotion()) { setGone(changes.removed.length); return }
    setGone(0)
    const step = Math.min(40, 1400 / Math.max(changes.removed.length, 1))
    const timers = changes.removed.map((_: number, i: number) => setTimeout(() => setGone(i + 1), 500 + i * step))
    return () => timers.forEach(clearTimeout)
  }, [changes])
  const order = useMemo(() => new Map<number, number>(changes.removed.map((n: number, i: number) => [n, i])), [changes.removed])
  return (
    <div>
      <div className="eyebrow mb-2">Row map{changes.sampled ? ` · even sample of ${fmtNum(changes.sampleCount)}` : ''}</div>
      <div className="grid gap-[2px] rounded-xl border border-slate-200 p-2" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(9px, 1fr))' }}
        role="img" aria-label={`${fmtNum(changes.removedRows)} of ${fmtNum(changes.sourceRows)} rows are left out of the reviewed copy`}>
        {changes.rowNumbers.map((n: number) => {
          const isRemoved = removed.has(n), isGone = isRemoved && (order.get(n) ?? 0) < gone
          return <i key={n} className="block aspect-square rounded-[2px] transition-all duration-500"
            style={{ background: isRemoved ? (isGone ? 'transparent' : 'rgb(var(--review-500))') : 'rgb(var(--brand-200))',
              boxShadow: isGone ? 'inset 0 0 0 1.5px rgb(var(--review-500))' : undefined, transform: isGone ? 'translateY(2px) scale(.75)' : undefined }} />
        })}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 text-xs text-ink-500">
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[2px] shadow-[inset_0_0_0_1.5px_rgb(var(--review-500))]" />left out of the copy</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[2px] bg-brand-200" />kept in the copy</span>
      </div>
    </div>
  )
}

type Props = { dataset: any; roles: Roles }

export default function ChangePreview({ dataset, roles }: Props) {
  const protectedCols = useMemo(() => new Set([...roles.demographics, ...roles.identifiers, ...(roles.outcome ? [roles.outcome] : [])]), [roles])
  const features = dataset.columns.filter((c: any) => !protectedCols.has(c.name))
  const withGaps = features.filter((c: any) => c.missing_count > 0)
  const textCols = features.filter((c: any) => c.kind !== 'numeric')
  const [pick, setPick] = useState({ dedupe: true, dropMissing: false, fill: false, trim: false, dropCol: false })
  const [dropMissingCols, setDropMissingCols] = useState<string[]>([])
  const [fill, setFill] = useState({ column: withGaps[0]?.name ?? '', method: 'median', value: '' })
  const [trimCol, setTrimCol] = useState(textCols[0]?.name ?? '')
  const [dropCol, setDropCol] = useState(features[0]?.name ?? '')
  const [preview, setPreview] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { setPreview(null) }, [pick, dropMissingCols, fill, trimCol, dropCol, roles])

  const fillCol = withGaps.find((c: any) => c.name === fill.column)
  const actions: ChangeAction[] = []
  if (pick.dedupe) actions.push({ action: 'drop_duplicate_rows' })
  if (pick.dropMissing && dropMissingCols.length) actions.push({ action: 'drop_rows_with_missing', columns: dropMissingCols })
  if (pick.fill && fill.column) actions.push(fill.method === 'median' ? { action: 'fill_missing', column: fill.column, method: 'median' }
    : { action: 'fill_missing', column: fill.column, method: 'constant', value: fillCol?.kind === 'numeric' ? Number(fill.value) : fill.value })
  if (pick.trim && trimCol) actions.push({ action: 'strip_whitespace', column: trimCol })
  if (pick.dropCol && dropCol) actions.push({ action: 'drop_column', column: dropCol })

  const generate = async () => {
    setBusy(true); setError(null)
    try { setPreview(await api.preview(dataset.dataset_id, roles, actions)) } catch (e: any) { setError(e.message) } finally { setBusy(false) }
  }
  const accept = async () => {
    try { setPreview(await api.accept(dataset.dataset_id, preview.preview_id)) } catch (e: any) { setError(e.message) }
  }
  const ready = preview?.result.status === 'preview_ready'
  const toggle = (k: keyof typeof pick) => setPick({ ...pick, [k]: !pick[k] })
  const row = 'flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-card px-3 py-2'

  return (
    <section className="card p-6" data-tour="copy" aria-labelledby="copy-title">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="eyebrow">Controlled next step</div>
          <h2 id="copy-title" className="display text-2xl">Prepare a reviewed copy</h2>
          <p className="mt-1 max-w-2xl text-sm text-ink-500">Every action runs on a separate copy; the source dataset stays locked. Resampling, SMOTE and demographic balancing are not offered, and a cleaner copy does not show improved accuracy or fairness.</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-ink-500">
          <ShieldCheck size={14} aria-hidden /> Never changed:
          {['demographic', 'identifier', 'outcome', 'prediction'].map((role) => {
            const assigned = role === 'demographic' ? roles.demographics.length : role === 'identifier' ? roles.identifiers.length : role === 'outcome' ? (roles.outcome ? 1 : 0) : 0
            return <span key={role} className={`chip ${assigned ? 'border-slate-300 bg-slate-100 text-ink-900' : 'border-dashed border-slate-300 bg-card text-ink-500'}`}>{role}{assigned ? '' : ' · none assigned'}</span>
          })}
        </div>
      </div>

      <div className="grid gap-2 lg:grid-cols-2">
        <label className={row}><input type="checkbox" checked={pick.dedupe} onChange={() => toggle('dedupe')} className="accent-[rgb(var(--brand-500))]" /> Remove exact duplicate rows</label>
        <div className={row}>
          <label className="flex items-center gap-2"><input type="checkbox" checked={pick.dropMissing} onChange={() => toggle('dropMissing')} disabled={!withGaps.length} /> Remove rows missing</label>
          {withGaps.map((c: any) => (
            <button key={c.name} type="button" disabled={!pick.dropMissing} aria-pressed={dropMissingCols.includes(c.name)}
              onClick={() => setDropMissingCols(dropMissingCols.includes(c.name) ? dropMissingCols.filter((x) => x !== c.name) : [...dropMissingCols, c.name])}
              className={`chip ${dropMissingCols.includes(c.name) ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-slate-200 text-ink-700'} disabled:opacity-40`}>{c.name}</button>
          ))}
          {!withGaps.length && <span className="text-xs text-ink-500">No unprotected column has gaps.</span>}
        </div>
        <div className={row}>
          <label className="flex items-center gap-2"><input type="checkbox" checked={pick.fill} onChange={() => toggle('fill')} disabled={!withGaps.length} /> Fill missing values in</label>
          <select className="field !w-auto !py-1" value={fill.column} disabled={!pick.fill} onChange={(e) => setFill({ ...fill, column: e.target.value })} aria-label="Column to fill">
            {withGaps.map((c: any) => <option key={c.name}>{c.name}</option>)}
          </select>
          <select className="field !w-auto !py-1" value={fill.method} disabled={!pick.fill} onChange={(e) => setFill({ ...fill, method: e.target.value })} aria-label="Fill method">
            {fillCol?.kind === 'numeric' && <option value="median">median</option>}<option value="constant">constant</option>
          </select>
          {fill.method === 'constant' && <input className="field !w-28 !py-1" placeholder="value" value={fill.value} disabled={!pick.fill} onChange={(e) => setFill({ ...fill, value: e.target.value })} aria-label="Fill value" />}
        </div>
        <div className={row}>
          <label className="flex items-center gap-2"><input type="checkbox" checked={pick.trim} onChange={() => toggle('trim')} disabled={!textCols.length} /> Trim whitespace in</label>
          <select className="field !w-auto !py-1" value={trimCol} disabled={!pick.trim} onChange={(e) => setTrimCol(e.target.value)} aria-label="Text column to trim">
            {textCols.map((c: any) => <option key={c.name}>{c.name}</option>)}
          </select>
        </div>
        <div className={row}>
          <label className="flex items-center gap-2"><input type="checkbox" checked={pick.dropCol} onChange={() => toggle('dropCol')} disabled={!features.length} /> Remove feature column</label>
          <select className="field !w-auto !py-1" value={dropCol} disabled={!pick.dropCol} onChange={(e) => setDropCol(e.target.value)} aria-label="Feature column to remove">
            {features.map((c: any) => <option key={c.name}>{c.name}</option>)}
          </select>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button className="btn-primary" onClick={generate} disabled={!actions.length || busy}><Wand2 size={16} />Generate preview</button>
        {busy && <Spinner label="Preparing a separate copy…" />}
        {error && <Note tone="warn">{error}</Note>}
      </div>

      {preview && !ready && (
        <div className="mt-5 space-y-2 animate-rise">
          <Note tone="warn">This preview is blocked, so no copy was prepared. Any blocked action blocks the whole change set.</Note>
          <ul className="space-y-1 text-sm">{preview.result.actions.map((a: any) => <li key={a.index} className="text-ink-700"><b>{a.action}</b> · {a.status}{a.reason ? ` · ${a.reason}` : ''}</li>)}</ul>
        </div>
      )}

      {ready && (
        <div className="mt-6 space-y-5 animate-rise">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              { label: 'Source rows', value: preview.changes.sourceRows, icon: <Lock size={12} aria-label="locked" /> },
              { label: 'Rows removed', value: preview.changes.removedRows, review: preview.changes.removedRows > 0 },
              { label: 'Rows in copy', value: preview.changes.copyRows },
              { label: 'Cells filled', value: preview.changes.cellsFilled },
            ].map((t) => (
              <div key={t.label} className={`rounded-xl border bg-card px-4 py-3 ${t.review ? 'border-slate-200 border-l-4 border-l-review-500' : 'border-slate-200'}`}>
                <div className="eyebrow flex items-center gap-1">{t.label} {t.icon}</div>
                <div className="font-display text-2xl font-bold text-ink-900">{fmtNum(t.value)}</div>
              </div>
            ))}
          </div>
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px]">
            <RowDrop changes={preview.changes} />
            <div className="space-y-3">
              <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-card p-3">
                <Identicon hash={preview.changes.sourceFingerprint} tone="source" />
                <div className="min-w-0"><div className="font-semibold text-ink-900">Source dataset</div><div className="text-xs text-ink-500">fingerprint unchanged</div><div className="truncate font-mono text-[11px] text-ink-300">{preview.changes.sourceFingerprint.slice(0, 12)}</div></div>
              </div>
              <div className="relative flex items-center gap-3 overflow-hidden rounded-xl border border-slate-200 bg-card p-3">
                <Identicon hash={preview.changes.outputFingerprint} tone="copy" />
                <div className="min-w-0"><div className="font-semibold text-ink-900">Reviewed copy</div><div className="text-xs text-ink-500">separate fingerprint</div><div className="truncate font-mono text-[11px] text-ink-300">{preview.changes.outputFingerprint.slice(0, 12)}</div>
                  {preview.changes.accepted && <span className="mt-1 inline-block rotate-[-3deg] rounded-md border-2 border-brand-500 px-2 py-0.5 text-[11px] font-extrabold uppercase tracking-wide text-brand-700 animate-stamp">ready to export</span>}
                </div>
              </div>
              {!preview.changes.accepted
                ? <button className="btn-primary w-full justify-center" onClick={accept}>Accept for export</button>
                : <a className="btn-outline w-full justify-center" href={api.copyUrl(dataset.dataset_id, preview.preview_id)} download><Download size={16} />Download reviewed copy</a>}
              <p className="text-xs text-ink-500">Accepting adds this preview to the readiness report. The audited source is never replaced.</p>
            </div>
          </div>
          {preview.diff && <Diff diff={preview.diff} />}
        </div>
      )}
    </section>
  )
}

function Diff({ diff }: { diff: any }) {
  const missing = [...diff.missing].sort((a: any, b: any) => b.before - a.before)
  const demographics = Object.keys(diff.demographics.before ?? {})
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="rounded-xl border border-slate-200 bg-card p-4">
        <div className="eyebrow mb-1">Missing cells, before and after</div>
        {missing.length ? (
          <Chart height={Math.max(160, missing.length * 38 + 60)} label="Missing cells per column in the source and the reviewed copy" option={{
            legend: { top: 0 }, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            xAxis: { type: 'value', name: 'cells' }, yAxis: { type: 'category', inverse: true, data: missing.map((m: any) => m.column) },
            series: [
              { name: 'Source', type: 'bar', barMaxWidth: 14, itemStyle: { color: token('review-500'), borderRadius: [0, 4, 4, 0] }, data: missing.map((m: any) => m.before) },
              { name: 'Reviewed copy', type: 'bar', barMaxWidth: 14, itemStyle: { color: token('review-200'), borderRadius: [0, 4, 4, 0] }, data: missing.map((m: any) => m.after ?? 0) },
            ],
          }} />
        ) : <p className="text-sm text-ink-500">Neither table has missing cells.</p>}
        <p className="mt-1 text-xs text-ink-500">Rows {fmtNum(diff.rows[0])} → {fmtNum(diff.rows[1])} · columns {diff.columns[0]} → {diff.columns[1]}</p>
      </div>
      <div className="rounded-xl border border-slate-200 bg-card p-4">
        <div className="eyebrow mb-2">Group shares, before and after</div>
        {demographics.length ? demographics.map((col) => {
          const before = diff.demographics.before[col], after = diff.demographics.after?.[col]
          const labels = Object.keys(before.counts)
          return (
            <div key={col} className="mb-3 space-y-1.5">
              <div className="text-sm font-semibold text-ink-900">{col}</div>
              {labels.map((label) => {
                const b = before.observed_count ? before.counts[label] / before.observed_count : 0
                const a = after?.observed_count ? (after.counts[label] ?? 0) / after.observed_count : 0
                const pp = (a - b) * 100
                return (
                  <div key={label} className="grid grid-cols-[110px_minmax(0,1fr)_64px] items-center gap-2 text-xs">
                    <span className="truncate text-ink-700">{col} = {label}</span>
                    <div className="space-y-0.5">
                      <div className="h-1.5 rounded-full bg-slate-300" style={{ width: `${b * 100}%` }} title={`Source ${(b * 100).toFixed(1)}%`} />
                      <div className="h-1.5 rounded-full bg-brand-500" style={{ width: `${a * 100}%` }} title={`Copy ${(a * 100).toFixed(1)}%`} />
                    </div>
                    <span className="text-right tabular-nums text-ink-700">{`${pp > 0 ? '+' : pp < 0 ? '−' : ''}${Math.abs(pp).toFixed(1)} pp`}</span>
                  </div>
                )
              })}
            </div>
          )
        }) : <p className="text-sm text-ink-500">Choose demographic columns in the plan to compare group shares.</p>}
        <p className="text-xs text-ink-500">Gray: source · cobalt: reviewed copy. Shift in percentage points, descriptive only.</p>
      </div>
    </div>
  )
}
