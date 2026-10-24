"""Local HTTP API for MedGuard Explorer. Binds to 127.0.0.1; data stays in memory.

Every response is computed from the dataset loaded in this process with the
deterministic services; nothing is precomputed or hard-coded.
"""
from collections import OrderedDict
import hashlib
import json
from pathlib import Path
import sys
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
from pydantic import BaseModel, Field

from explorer import insights, llm, planner
from services.contracts import RepresentationInputError
from services.input_validation import validate_input
from services.privacy_screening import screen_identifiers
from services.readiness import (
    DEFAULT_SETTINGS, MISSING_LABEL, ReadinessInputError, _feature_profile, analyze_readiness, apply_filters,
)
from services.representation import _label, analyze_representation
from utils.audit_input import dataset_fingerprint

DEMO_DIR = ROOT / 'data' / 'synthetic'
STATIC_DIR = ROOT / 'frontend' / 'dist'
MAX_DATASETS = 4
PREVIEW_ROWS = 50

app = FastAPI(title='MedGuard Explorer', version='0.1.0')
_DATASETS: 'OrderedDict[str, dict]' = OrderedDict()


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
    widgets: List[str] = Field(default_factory=lambda: list(planner.WIDGETS))
    focus_groups: List[dict] = Field(default_factory=list)


class ExplainRequest(AnalyzeRequest):
    widget: str
    use_ai: bool = True


def _json_safe(df: pd.DataFrame) -> List[dict]:
    return json.loads(df.to_json(orient='records', date_format='iso'))


def _store(name: str, source: str, data: bytes) -> dict:
    validation, frame = validate_input(data)
    if frame is None:
        return {'accepted': False, 'name': name, 'validation': validation}
    dataset_id = dataset_fingerprint(frame)[:16]
    _DATASETS[dataset_id] = {'frame': frame, 'validation': validation, 'name': name, 'source': source}
    _DATASETS.move_to_end(dataset_id)
    while len(_DATASETS) > MAX_DATASETS:
        _DATASETS.popitem(last=False)
    columns = [{'name': str(c), **{k: v for k, v in _feature_profile(frame[c], str(c), 'feature').items()
                                   if k in ('kind', 'distinct', 'missing_count', 'missing_rate', 'id_like',
                                            'constant', 'top', 'stats')}} for c in frame.columns]
    return {'accepted': True, 'dataset_id': dataset_id, 'name': name, 'source': source,
            'fingerprint': dataset_fingerprint(frame), 'validation': validation, 'columns': columns,
            'preview': _json_safe(frame.head(PREVIEW_ROWS))}


def _dataset(dataset_id: str) -> dict:
    if dataset_id not in _DATASETS:
        raise HTTPException(404, 'Dataset not loaded. Load it again (data is kept in memory only).')
    return _DATASETS[dataset_id]


def _analyze(req: AnalyzeRequest) -> dict:
    entry = _dataset(req.dataset_id)
    try:
        frame = apply_filters(entry['frame'], req.filters)
        readiness = analyze_readiness(frame, outcome_column=req.roles.outcome,
                                      demographic_columns=req.roles.demographics,
                                      identifier_columns=req.roles.identifiers, settings=req.settings)
        reference = {k: v for k, v in req.reference.items() if k in req.roles.demographics and v}
        representation = (analyze_representation(frame, demographic_columns=req.roles.demographics,
                                                 reference_proportions=reference or None)
                          if req.roles.demographics else None)
    except (ReadinessInputError, RepresentationInputError) as exc:
        raise HTTPException(422, str(exc))
    results = {'validation': entry['validation'], 'screening': screen_identifiers(frame),
               'readiness': readiness, 'representation': representation, 'focus_groups': req.focus_groups}
    widgets = [w for w in req.widgets if w in insights.TITLES]
    return {**results, 'board': insights.board(results, widgets), 'answers': insights.answers(results, req.focus_groups),
            'subset': {'filters': req.filters, 'row_count': int(len(frame)), 'total_rows': int(len(entry['frame']))},
            'dataset': {'name': entry['name'], 'fingerprint': dataset_fingerprint(entry['frame'])}}


@app.get('/api/health')
def health():
    return {'ok': True, 'ai': llm.status(), 'settings': DEFAULT_SETTINGS, 'widgets': planner.WIDGETS,
            'titles': insights.TITLES, 'missing_label': MISSING_LABEL}


@app.get('/api/demos')
def demos():
    return [{'name': p.name, 'bytes': p.stat().st_size} for p in sorted(DEMO_DIR.glob('*.csv'))]


@app.post('/api/datasets/demo/{name}')
def load_demo(name: str):
    path = DEMO_DIR / name
    if path.parent != DEMO_DIR or not path.is_file():
        raise HTTPException(404, 'Unknown demo dataset.')
    return _store(name, 'bundled_synthetic_demo', path.read_bytes())


@app.post('/api/datasets/upload')
async def upload(request: Request, filename: str = 'upload.csv'):
    data = await request.body()
    return _store(Path(filename).name or 'upload.csv', 'uploaded_csv', data)


@app.post('/api/plan')
def plan(req: PlanRequest):
    entry = _dataset(req.dataset_id)
    frame = entry['frame']
    columns = []
    for c in frame.columns:
        profile = _feature_profile(frame[c], str(c), 'feature')
        labels = (sorted(frame[c].dropna().map(_label).unique().tolist())
                  if profile['kind'] == 'categorical' and profile['distinct'] <= 100 else None)
        columns.append({'name': str(c), 'labels': labels,
                        **{k: v for k, v in profile.items() if k in ('kind', 'distinct', 'id_like', 'top')}})
    return planner.build_plan(columns, req.idea.model_dump(), use_ai=req.use_ai)


@app.post('/api/analyze')
def analyze(req: AnalyzeRequest):
    return _analyze(req)


@app.post('/api/explain')
def explain(req: ExplainRequest):
    if req.widget not in insights.TITLES:
        raise HTTPException(422, 'Unknown widget.')
    results = _analyze(req)
    return insights.explain(req.widget, results, req.idea.model_dump(), use_ai=req.use_ai)


@app.post('/api/report')
def report(req: AnalyzeRequest):
    results = _analyze(req)
    body = {'report_type': 'medguard_explorer_readiness', 'report_version': '0.1',
            'idea': req.idea.model_dump(), 'roles': req.roles.model_dump(), 'reference': req.reference,
            'filters': req.filters, 'focus_groups': req.focus_groups, **results,
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
    print('MedGuard Explorer: http://127.0.0.1:8600')
    uvicorn.run(app, host='127.0.0.1', port=8600, log_level='warning')


if __name__ == '__main__':
    main()
