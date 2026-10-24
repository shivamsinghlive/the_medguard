"""HTTP API for MedGuard Explorer. Data stays in memory and is never written to disk.

Every response is computed from the dataset loaded in this process with the
deterministic services; nothing is precomputed or hard-coded.

Locally it binds to 127.0.0.1. As a public demo (MEDGUARD_PUBLIC=1) each visitor
gets a private session and datasets expire after SESSION_TTL_SECONDS. The local
Ollama model is never used there; a hosted provider configured in llm.py can be. MEDGUARD_HOST and PORT choose where it listens; MEDGUARD_MAX_UPLOAD_MB,
MEDGUARD_MAX_ROWS, and MEDGUARD_MAX_SESSIONS keep memory within small hosting plans.
"""
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import pandas as pd
from pydantic import BaseModel, Field

from explorer import insights, llm, planner
from services.audit_runner import reviewed_copy_csv, run_audit
from services.change_preview import preview_changes
from services.contracts import ChangePreviewError, RepresentationInputError
from services.input_validation import DEFAULT_MAX_BYTES, DEFAULT_MAX_ROWS, validate_input
from services.readiness import (
    DEFAULT_SETTINGS, MISSING_LABEL, ReadinessInputError, _feature_profile, analyze_readiness, apply_filters,
)
from services.representation import _label
from ui.visuals.payloads import (
    build_change_payload, build_cohort_payload, build_coverage_payload, build_mosaic_payload,
    build_quality_tiles, build_status_tiles, format_gap,
)
from utils.audit_input import dataset_fingerprint

DEMO_DIR = ROOT / 'data' / 'synthetic'
STATIC_DIR = ROOT / 'frontend' / 'dist'
MAX_DATASETS = 2  # per session; older ones are dropped first
MAX_SESSIONS = int(os.environ.get('MEDGUARD_MAX_SESSIONS', '200'))
MAX_UPLOAD_BYTES = min(int(os.environ.get('MEDGUARD_MAX_UPLOAD_MB', '25')) * 1024 * 1024, DEFAULT_MAX_BYTES)
MAX_ROWS = min(int(os.environ.get('MEDGUARD_MAX_ROWS', str(DEFAULT_MAX_ROWS))), DEFAULT_MAX_ROWS)
SESSION_TTL_SECONDS = 60 * 60
SESSION_ID = re.compile(r'^[A-Za-z0-9-]{16,64}$')
PREVIEW_ROWS = 50

app = FastAPI(title='MedGuard Explorer', version='0.1.0')
_SESSIONS: 'OrderedDict[str, dict]' = OrderedDict()  # session id -> {'seen', 'datasets'}


def public_mode() -> bool:
    return os.environ.get('MEDGUARD_PUBLIC') == '1'


def ai_allowed() -> bool:
    """A public server never reaches for a local Ollama model; hosted providers are fine."""
    return not (public_mode() and llm.is_local())


def _session_id(request: Optional[Request]) -> str:
    """The visitor's session from the X-MedGuard-Session header (or ?session= for downloads)."""
    if request is None:  # internal call, as in tests
        return 'local'
    sid = request.headers.get('x-medguard-session') or request.query_params.get('session')
    if sid and SESSION_ID.match(sid):
        return sid
    if public_mode():
        raise HTTPException(400, 'Missing session. Reload the page to start a new one.')
    return 'local'


def _datasets(session_id: str) -> 'OrderedDict[str, dict]':
    """This session's datasets; expired and least-recent sessions are dropped first."""
    now = time.monotonic()
    for sid in [s for s, v in _SESSIONS.items() if now - v['seen'] > SESSION_TTL_SECONDS]:
        del _SESSIONS[sid]
    session = _SESSIONS.setdefault(session_id, {'seen': now, 'datasets': OrderedDict()})
    session['seen'] = now
    _SESSIONS.move_to_end(session_id)
    while len(_SESSIONS) > MAX_SESSIONS:
        _SESSIONS.popitem(last=False)
    return session['datasets']


class Idea(BaseModel):
    title: str = ''
    question: str = ''
    outcome: str = ''
    population: str = ''
    groups: str = ''


class Roles(BaseModel):
    outcome: Optional[str] = None
    demographics: List[str] = Field(default_factory=list)
    identifiers: List[str] = Field(default_factory=list)


class PlanRequest(BaseModel):
    dataset_id: str
    idea: Idea
    use_ai: bool = True


class AnalyzeRequest(BaseModel):
    dataset_id: str
    idea: Idea = Field(default_factory=Idea)
    roles: Roles = Field(default_factory=Roles)
    reference: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    settings: Dict[str, float] = Field(default_factory=dict)
    filters: Dict[str, List[str]] = Field(default_factory=dict)
    ranges: Dict[str, List[float]] = Field(default_factory=dict)  # numeric column -> [low, high]
    row_ids: List[int] = Field(default_factory=list)  # rows picked in the mosaic or the 2-D map
    focus_column: Optional[str] = None  # missing-values lens focus for the row map
    widgets: List[str] = Field(default_factory=lambda: list(planner.WIDGETS))
    focus_groups: List[dict] = Field(default_factory=list)


class ExplainRequest(AnalyzeRequest):
    widget: str
    use_ai: bool = True


class PreviewRequest(BaseModel):
    dataset_id: str
    roles: Roles = Field(default_factory=Roles)
    actions: List[Dict[str, Any]] = Field(default_factory=list)


class AcceptRequest(BaseModel):
    dataset_id: str
    preview_id: str


def _json_safe(df: pd.DataFrame) -> List[dict]:
    return json.loads(df.to_json(orient='records', date_format='iso'))


def _store(request: Request, name: str, source: str, data: bytes) -> dict:
    validation, frame = validate_input(data, max_bytes=MAX_UPLOAD_BYTES, max_rows=MAX_ROWS)
    if frame is None:
        return {'accepted': False, 'name': name, 'validation': validation}
    dataset_id = dataset_fingerprint(frame)[:16]
    datasets = _datasets(_session_id(request))
    datasets[dataset_id] = {'frame': frame, 'validation': validation, 'name': name, 'source': source}
    datasets.move_to_end(dataset_id)
    while len(datasets) > MAX_DATASETS:
        datasets.popitem(last=False)
    columns = [{'name': str(c), **{k: v for k, v in _feature_profile(frame[c], str(c), 'feature').items()
                                   if k in ('kind', 'distinct', 'missing_count', 'missing_rate', 'id_like',
                                            'constant', 'top', 'stats')}} for c in frame.columns]
    return {'accepted': True, 'dataset_id': dataset_id, 'name': name, 'source': source,
            'fingerprint': dataset_fingerprint(frame), 'validation': validation, 'columns': columns,
            'preview': _json_safe(frame.head(PREVIEW_ROWS))}


def _dataset(request: Optional[Request], dataset_id: str) -> dict:
    datasets = _datasets(_session_id(request))
    if dataset_id not in datasets:
        raise HTTPException(404, 'Dataset not loaded. Load it again (data is kept in memory only, '
                                 f'for up to {SESSION_TTL_SECONDS // 60} minutes).')
    return datasets[dataset_id]


def _subset(entry: dict, req: AnalyzeRequest) -> pd.DataFrame:
    """Apply label filters, numeric ranges, and picked rows; the stored frame is never changed."""
    frame = apply_filters(entry['frame'], req.filters)
    for column, bounds in req.ranges.items():
        if column not in frame.columns:
            raise ReadinessInputError(f'Range column not found: {column!r}.')
        if not pd.api.types.is_numeric_dtype(frame[column]) or len(bounds) != 2:
            raise ReadinessInputError(f'A range needs a numeric column and two bounds: {column!r}.')
        low, high = sorted(bounds)
        frame = frame[frame[column].between(low, high)]
    if req.row_ids:
        frame = frame[frame.index.isin(req.row_ids)]
    if frame.empty:
        raise ReadinessInputError('No rows match the current filters. Remove a filter to continue.')
    return frame


def _evidence(frame: pd.DataFrame, report: dict, req: AnalyzeRequest) -> dict:
    """Shared evidence payloads (status strip, row map, cohort, coverage, quality)."""
    demographic = req.roles.demographics[0] if req.roles.demographics else None
    focus = req.focus_column if req.focus_column in report['quality']['missing_by_column'] else None
    cohort = []
    for attribute in report['representation']['attributes']:
        payload = build_cohort_payload(attribute)
        for group in payload['groups']:
            group['gapText'] = format_gap(group['gap'])
        cohort.append(payload)
    return {'status_tiles': build_status_tiles(report),
            'mosaic': build_mosaic_payload(frame, report, demographic_column=demographic, focus_column=focus),
            'cohort': cohort, 'coverage': build_coverage_payload(report['identifier_screening']),
            'quality_tiles': build_quality_tiles(frame, report), 'quality': report['quality']}


def _analyze(req: AnalyzeRequest, request: Optional[Request] = None) -> dict:
    entry = _dataset(request, req.dataset_id)
    try:
        frame = _subset(entry, req)
        readiness = analyze_readiness(frame, outcome_column=req.roles.outcome,
                                      demographic_columns=req.roles.demographics,
                                      identifier_columns=req.roles.identifiers, settings=req.settings)
        reference = {k: v for k, v in req.reference.items() if k in req.roles.demographics and v}
        # The audit runner reuses the same screening and representation services and
        # checks that none of them changed the frame.
        report = run_audit(frame, demographic_columns=req.roles.demographics,
                           reference_proportions=reference or None, source_type=entry['source'],
                           input_validation={**entry['validation'], 'row_count': int(len(frame))})
    except (ReadinessInputError, RepresentationInputError) as exc:
        raise HTTPException(422, str(exc))
    results = {'validation': entry['validation'], 'screening': report['identifier_screening'],
               'readiness': readiness, 'representation': report['representation'] if req.roles.demographics else None,
               'focus_groups': req.focus_groups, 'evidence': _evidence(frame, report, req)}
    widgets = [w for w in req.widgets if w in insights.TITLES]
    return {**results, 'board': insights.board(results, widgets), 'answers': insights.answers(results, req.focus_groups),
            'subset': {'filters': req.filters, 'ranges': req.ranges, 'row_ids': len(req.row_ids),
                       'row_count': int(len(frame)), 'total_rows': int(len(entry['frame']))},
            'dataset': {'name': entry['name'], 'fingerprint': dataset_fingerprint(entry['frame'])}}


def _column_roles(frame: pd.DataFrame, roles: Roles) -> Dict[str, str]:
    column_roles = {str(c): 'feature' for c in frame.columns}
    named = [(c, 'demographic') for c in roles.demographics] + [(c, 'identifier') for c in roles.identifiers]
    if roles.outcome:
        named.append((roles.outcome, 'outcome'))
    for column, role in named:
        if column not in column_roles:
            raise HTTPException(422, f'Role column not found: {column!r}.')
        column_roles[column] = role
    return column_roles


def _preview_response(entry: dict) -> dict:
    """Change map, before/after diff, and fingerprints for the stored preview."""
    preview, source = entry['preview'], entry['frame']
    copy = preview['frame']
    changes = build_change_payload(source, source_fingerprint=dataset_fingerprint(source),
                                   preview_result=preview['result'], preview_frame=copy,
                                   column_roles=preview['roles'], accepted=preview['accepted'])
    diff = None
    if copy is not None:
        before, after = source.isna().sum(), copy.isna().sum()
        diff = {'rows': [int(len(source)), int(len(copy))],
                'columns': [int(source.shape[1]), int(copy.shape[1])],
                'missing': [{'column': str(c), 'before': int(before[c]),
                             'after': int(after[c]) if c in after.index else None}
                            for c in source.columns if before[c] or (c in after.index and after[c])],
                'demographics': {'before': preview['result']['before'].get('demographic_counts', {}),
                                 'after': (preview['result']['after'] or {}).get('demographic_counts', {})}}
    return {'preview_id': preview['id'], 'result': preview['result'], 'changes': changes, 'diff': diff,
            'accepted': preview['accepted']}


@app.get('/api/health')
def health():
    ai = (llm.status() if ai_allowed() else
          {'available': False, 'model': llm.DEFAULT_MODEL, 'provider': llm.provider_label(),
           'reason': 'No hosted AI provider is configured for this public demo.'})
    return {'ok': True, 'ai': ai, 'settings': DEFAULT_SETTINGS, 'widgets': planner.WIDGETS,
            'titles': insights.TITLES, 'missing_label': MISSING_LABEL,
            'public': public_mode(), 'retention_minutes': SESSION_TTL_SECONDS // 60,
            'limits': {'max_upload_mb': MAX_UPLOAD_BYTES // (1024 * 1024), 'max_rows': MAX_ROWS}}


@app.get('/api/demos')
def demos():
    return [{'name': p.name, 'bytes': p.stat().st_size} for p in sorted(DEMO_DIR.glob('*.csv'))]


@app.post('/api/datasets/demo/{name}')
def load_demo(name: str, request: Request):
    path = DEMO_DIR / name
    if path.parent != DEMO_DIR or not path.is_file():
        raise HTTPException(404, 'Unknown demo dataset.')
    return _store(request, name, 'bundled_synthetic_demo', path.read_bytes())


@app.post('/api/datasets/upload')
async def upload(request: Request, filename: str = 'upload.csv'):
    declared = request.headers.get('content-length')
    if declared and declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f'Files over {MAX_UPLOAD_BYTES // (1024 * 1024)} MB are not accepted.')
    data = await request.body()
    return _store(request, Path(filename).name or 'upload.csv', 'uploaded_csv', data)


@app.post('/api/plan')
def plan(req: PlanRequest, request: Request):
    entry = _dataset(request, req.dataset_id)
    frame = entry['frame']
    columns = []
    for c in frame.columns:
        profile = _feature_profile(frame[c], str(c), 'feature')
        labels = (sorted(frame[c].dropna().map(_label).unique().tolist())
                  if profile['kind'] == 'categorical' and profile['distinct'] <= 100 else None)
        columns.append({'name': str(c), 'labels': labels,
                        **{k: v for k, v in profile.items() if k in ('kind', 'distinct', 'id_like', 'top')}})
    return planner.build_plan(columns, req.idea.model_dump(), use_ai=req.use_ai and ai_allowed())


@app.post('/api/analyze')
def analyze(req: AnalyzeRequest, request: Request):
    return _analyze(req, request)


@app.post('/api/explain')
def explain(req: ExplainRequest, request: Request):
    if req.widget not in insights.TITLES:
        raise HTTPException(422, 'Unknown widget.')
    results = _analyze(req, request)
    return insights.explain(req.widget, results, req.idea.model_dump(), use_ai=req.use_ai and ai_allowed())


@app.post('/api/preview')
def preview(req: PreviewRequest, request: Request):
    entry = _dataset(request, req.dataset_id)
    roles = _column_roles(entry['frame'], req.roles)
    try:
        result, output = preview_changes(entry['frame'], req.actions, column_roles=roles)
    except ChangePreviewError as exc:
        raise HTTPException(422, str(exc))
    key = json.dumps({'source': result['source_fingerprint'], 'roles': roles, 'actions': req.actions},
                     sort_keys=True, default=str)
    entry['preview'] = {'id': hashlib.sha256(key.encode()).hexdigest()[:16], 'result': result,
                        'frame': output, 'roles': roles, 'accepted': False}
    return _preview_response(entry)


def _current_preview(request: Request, dataset_id: str, preview_id: str) -> dict:
    entry = _dataset(request, dataset_id)
    preview = entry.get('preview')
    if not preview or preview['id'] != preview_id:
        raise HTTPException(409, 'This preview is no longer current. Generate it again.')
    return entry


@app.post('/api/preview/accept')
def accept_preview(req: AcceptRequest, request: Request):
    entry = _current_preview(request, req.dataset_id, req.preview_id)
    if entry['preview']['result']['status'] != 'preview_ready':
        raise HTTPException(422, 'A blocked preview cannot be accepted.')
    entry['preview']['accepted'] = True
    return _preview_response(entry)


@app.get('/api/preview/copy.csv')
def preview_copy(dataset_id: str, preview_id: str, request: Request):
    entry = _current_preview(request, dataset_id, preview_id)
    if not entry['preview']['accepted']:
        raise HTTPException(409, 'Accept the preview before downloading the reviewed copy.')
    return Response(reviewed_copy_csv(entry['preview']['frame']), media_type='text/csv',
                    headers={'Content-Disposition': 'attachment; filename="medguard-reviewed-copy.csv"'})


@app.post('/api/report')
def report(req: AnalyzeRequest, request: Request):
    results = _analyze(req, request)
    preview = _dataset(request, req.dataset_id).get('preview')
    if preview and preview['accepted']:
        results['change_preview'] = {**preview['result'], 'accepted_for_export': True}
    body = {'report_type': 'medguard_explorer_readiness', 'report_version': '0.1',
            'idea': req.idea.model_dump(), 'roles': req.roles.model_dump(), 'reference': req.reference,
            'filters': req.filters, 'ranges': req.ranges, 'row_ids': req.row_ids,
            'focus_groups': req.focus_groups, **results,
            'disclaimer': 'Descriptive dataset-readiness evidence. Not model validation, fairness '
                          'certification, clinical validation, or de-identification.'}
    body['report_digest'] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return JSONResponse(body)


if STATIC_DIR.is_dir():
    app.mount('/assets', StaticFiles(directory=STATIC_DIR / 'assets'), name='assets')

    @app.get('/{path:path}')
    def spa(path: str):
        return FileResponse(STATIC_DIR / 'index.html')


def main():
    import uvicorn
    host = os.environ.get('MEDGUARD_HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '8600'))
    print(f'MedGuard Explorer: http://{host}:{port}' + (' (public demo mode)' if public_mode() else ''))
    # Access logs stay off so request URLs (file names, ids) are not written anywhere.
    uvicorn.run(app, host=host, port=port, log_level='warning', access_log=False)


if __name__ == '__main__':
    main()
