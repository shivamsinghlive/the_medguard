"""Regression coverage for auditing source records instead of generated copies."""
from pathlib import Path
import sys
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from utils.audit_input import dataset_fingerprint


def test_fingerprint_tracks_content_and_schema():
    df = pd.DataFrame({'sex': ['Male', 'Female'], 'outcome': [0, 1]})
    assert dataset_fingerprint(df) == dataset_fingerprint(df.copy(deep=True))
    reloaded = pd.DataFrame({'sex': ['Male', 'Female'], 'outcome': [0, 1]})
    assert dataset_fingerprint(df) == dataset_fingerprint(reloaded)
    changed = df.copy()
    changed.loc[1, 'outcome'] = 0
    for other in (changed, df.iloc[::-1], df[['outcome', 'sex']],
                  df.rename(columns={'outcome': 'label'}), df.astype({'outcome': float})):
        assert dataset_fingerprint(df) != dataset_fingerprint(other)


def test_demo_audits_original_records_and_keeps_results_on_rerun(monkeypatch):
    monkeypatch.chdir(ROOT)
    with patch('ollama.generate', side_effect=RuntimeError('AI disabled in test')), \
         patch('ollama.Client.embeddings', side_effect=RuntimeError('AI disabled in test')), \
         patch('utils.synthetic_generator.SyntheticDataGenerator.generate',
               side_effect=AssertionError('Audit must not generate records')):
        app = AppTest.from_file(str(ROOT / 'src/ui/app_complete.py')).run(timeout=30)
        app.text_area[0].input('Regression audit')
        next(b for b in app.button if 'Continue' in b.label).click().run(timeout=30)
        app.selectbox[0].select('Demo 1: Heart Disease (Quality Issues)').run(timeout=30)
        assert not app.exception
        original = pd.read_csv(ROOT / 'data/synthetic/dataset1_heart_disease_quality.csv')
        assert app.session_state['analysis_hash'] == dataset_fingerprint(original)
        assert app.session_state['quality_summary']['total_records'] == len(original)
        expected_duplicates = int(original.duplicated(keep=False).sum())
        assert expected_duplicates > 0  # This fixture must expose loss of duplicates.
        assert app.session_state['quality_issues']['duplicates']['count'] == expected_duplicates
        for col in original.columns[original.isna().any()]:
            assert app.session_state['quality_issues']['missing_values'][col]['count'] == int(original[col].isna().sum())
        before = app.session_state['quality_issues']
        app.run(timeout=30)
        assert not app.exception
        assert app.session_state['quality_issues'] == before
        assert app.session_state['analysis_hash'] == dataset_fingerprint(original)
        pd.testing.assert_frame_equal(original, pd.read_csv(ROOT / 'data/synthetic/dataset1_heart_disease_quality.csv'))

        # Findings and selected changes must not survive a dataset change.
        app.session_state['modified_dataset'] = original
        app.session_state['fairness_recommendations'] = {'stale_column': 'stale advice'}
        app.selectbox[0].select('Demo 2: Diabetes (Gender Bias)').run(timeout=30)
        assert not app.exception
        assert 'modified_dataset' not in app.session_state
        assert 'stale_column' not in app.session_state['fairness_recommendations']
        second = pd.read_csv(ROOT / 'data/synthetic/dataset2_diabetes_gender_bias.csv')
        assert app.session_state['analysis_hash'] == dataset_fingerprint(second)
        performance = [m for m in app.metric if m.label == 'Performance Gap']
        patients = [m for m in app.metric if m.label == 'Patients Affected']
        assert performance and all(m.value == 'Not measured' for m in performance)
        assert patients and all(m.value == 'Not assessed' for m in patients)
        assert all(not m.delta for m in performance + patients)


def test_empty_column_renders_without_code_recommendation(monkeypatch):
    monkeypatch.chdir(ROOT)
    frame = pd.DataFrame({'measurement': [1.0, 2.0, 3.0], 'empty': [float('nan')] * 3})
    with patch('ollama.generate', side_effect=RuntimeError('AI disabled in test')), \
         patch('ollama.Client.embeddings', side_effect=RuntimeError('AI disabled in test')):
        app = AppTest.from_file(str(ROOT / 'src/ui/app_complete.py')).run(timeout=30)
        app.text_area[0].input('Empty column audit')
        next(b for b in app.button if 'Continue' in b.label).click().run(timeout=30)
        with patch('pandas.read_csv', return_value=frame):
            app.selectbox[0].select('Demo 1: Heart Disease (Quality Issues)').run(timeout=30)
        assert not app.exception
        assert app.session_state['quality_issues']['missing_values']['empty']['count'] == 3
        assert frame['empty'].isna().all()
