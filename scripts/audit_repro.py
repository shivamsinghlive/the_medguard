"""Reproduce audit findings with fabricated data only; no model calls."""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import numpy as np
import pandas as pd
from utils.bias_detection import BiasDetector
from utils.phi_scanner import PHIScanner
from utils.synthetic_generator import SyntheticDataGenerator
from agents.fairness_specialist import FairnessSpecialist

results = {}
for name, frame in {
    'single_gender': pd.DataFrame({'sex': ['Male'] * 100}),
    'no_demographics': pd.DataFrame({'measurement': [1, 2, 3]}),
}.items():
    detector = BiasDetector(frame)
    detector.run_full_analysis()
    results[name] = detector.get_summary()
results['email_after_row_100_passes'] = PHIScanner().scan_dataset(
    pd.DataFrame({'notes': ['ok'] * 100 + ['example@example.com']})
)[0]
results['numeric_identifier_passes'] = PHIScanner().scan_dataset(
    pd.DataFrame({'patient_id': [123456789], 'age': [95]})
)[0]
np.random.seed(42)
x = np.arange(1, 501)
frame = pd.DataFrame({'x': x, 'y': x * 2, 'outcome': x % 2})
generator = SyntheticDataGenerator()
generator.fit(frame)
twin = generator.generate()
results['original_correlation'] = float(frame.x.corr(frame.y))
results['synthetic_correlation'] = float(twin.x.corr(twin.y))
results['fractional_binary_outcomes'] = int((~twin.outcome.isin([0, 1])).sum())
recommendation = FairnessSpecialist()._create_fallback_recommendation(
    {'minority_group': 'Female', 'distribution': {'Male': 73, 'Female': 27}},
    {'samples_needed': 46}, {}
)
results['fallback_unmeasured_harm'] = recommendation.predicted_harm.model_dump()
print(json.dumps(results, indent=2))
