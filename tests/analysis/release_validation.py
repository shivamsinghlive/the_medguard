"""W05 measurement run: latency by dataset size, demo-data screening, known misses.

Run: python tests/analysis/release_validation.py [output.json]
Uses seeded fabricated data and bundled synthetic demos only; no AI or network.
Timings depend on the machine; they are not performance guarantees.
"""
import json
from pathlib import Path
import platform
import statistics
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from services.audit_runner import report_csv, report_json, run_audit
from services.change_preview import preview_changes
from services.input_validation import validate_input
from services.privacy_screening import screen_identifiers
from services.representation import analyze_representation

SIZES = (1_000, 10_000, 50_000, 200_000)
REPEATS = 3


def fabricated(rows: int) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        'patient_id': [f'SYNTH_{i:06d}' for i in range(rows)],
        'age': rng.integers(18, 90, rows),
        'sex': rng.choice(['Female', 'Male', None], rows, p=[0.48, 0.48, 0.04]),
        'race_ethnicity': rng.choice(['A', 'B', 'C', 'D', 'E'], rows),
        'bmi': rng.normal(28, 5, rows).round(1),
        'glucose': rng.normal(110, 25, rows).round(0),
        'systolic_bp': rng.integers(90, 180, rows),
        'cholesterol': np.where(rng.random(rows) < 0.05, np.nan, rng.normal(200, 30, rows).round(0)),
        'smoker': rng.choice(['yes', 'no'], rows),
        'site': rng.choice([f'site_{i}' for i in range(12)], rows),
        'note': rng.choice(['stable', 'follow up', 'no change', 'reviewed'], rows),
        'outcome': rng.integers(0, 2, rows),
    })


def timed(fn):
    samples = []
    for _ in range(REPEATS):
        start = time.perf_counter()
        value = fn()
        samples.append(time.perf_counter() - start)
    return round(statistics.median(samples) * 1000, 1), value


def latency():
    rows = []
    for size in SIZES:
        data = fabricated(size).to_csv(index=False).encode()
        ms_validate, (validation, frame) = timed(lambda: validate_input(data))
        ms_screen, _ = timed(lambda: screen_identifiers(frame))
        ms_repr, _ = timed(lambda: analyze_representation(
            frame, demographic_columns=['sex', 'race_ethnicity']))
        ms_audit, report = timed(lambda: run_audit(
            frame, demographic_columns=['sex', 'race_ethnicity'], source_type='uploaded_csv',
            input_validation=validation))
        ms_export, _ = timed(lambda: (report_json(report), report_csv(report)))
        ms_preview, _ = timed(lambda: preview_changes(
            frame, [{'action': 'drop_duplicate_rows'},
                    {'action': 'fill_missing', 'column': 'cholesterol', 'method': 'median'}],
            column_roles={'sex': 'demographic', 'race_ethnicity': 'demographic',
                          'patient_id': 'identifier', 'outcome': 'outcome'}))
        rows.append({'rows': size, 'columns': frame.shape[1], 'bytes': len(data),
                     'validate_ms': ms_validate, 'screen_ms': ms_screen,
                     'representation_ms': ms_repr, 'run_audit_ms': ms_audit,
                     'export_ms': ms_export, 'preview_ms': ms_preview,
                     'end_to_end_ms': round(ms_validate + ms_audit + ms_export, 1)})
    return rows


def demo_datasets():
    results = []
    for path in sorted((ROOT / 'data/synthetic').glob('*.csv')):
        validation, frame = validate_input(path.read_bytes())
        entry = {'file': path.name, 'validation': validation['status'],
                 'rows': validation['row_count'], 'columns': validation['column_count']}
        if frame is not None:
            demographics = [c for c in frame.columns if c.lower() in {'sex', 'gender', 'race_ethnicity'}]
            report = run_audit(frame, demographic_columns=demographics, source_type='bundled_synthetic_demo',
                               input_validation=validation)
            entry['representation_status'] = report['representation']['status']
            entry['representation_findings'] = [f['id'] for f in report['representation']['findings']]
            entry['identifier_findings'] = [
                {'column': f['column'], 'code': f['code'],
                 'kind': f['evidence'].get('kind')} for f in report['identifier_screening']['findings']]
        results.append(entry)
    return results


# Probes chosen to document where screening is expected to miss or over-flag.
PROBES = {
    'untitled_person_name': pd.DataFrame({'remarks': ['ok'] * 30 + ['John Smith']}),
    'street_address_value': pd.DataFrame({'remarks': ['ok'] * 30 + ['12 Main Street']}),
    'zip_values_benign_column': pd.DataFrame({'region': ['02115', '10001', '94105'] * 5}),
    'nine_digit_id_few_rows': pd.DataFrame({'ref': [123456789, 987654321]}),
    'unhyphenated_ssn_text': pd.DataFrame({'remarks': ['ok'] * 30 + ['ssn 123456789']}),
    'drug_name_column': pd.DataFrame({'drug_name': ['metformin', 'insulin'] * 15}),
    'distinct_lab_codes_text': pd.DataFrame({'lab_code': [f'L{i:03d}' for i in range(30)]}),
    'version_like_ip': pd.DataFrame({'firmware': ['10.0.0.1'] * 3}),
}


def probes():
    return {name: sorted({f['code'] for f in screen_identifiers(df)['findings']})
            for name, df in PROBES.items()}


def main():
    output = {
        'environment': {'python': platform.python_version(), 'pandas': pd.__version__,
                        'platform': platform.platform(), 'processor': platform.processor()},
        'method': f'median of {REPEATS} runs per stage; seeded fabricated data',
        'latency': latency(),
        'demo_datasets': demo_datasets(),
        'screening_probes': probes(),
    }
    text = json.dumps(output, indent=2)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text + '\n', encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
