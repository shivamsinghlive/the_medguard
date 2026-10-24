"""Unsupported model estimates must never become structured audit measurements."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from agents.fairness_specialist import FairnessSpecialist, HarmQuantification, TechnicalMitigation

BIAS = {'minority_group': 'Female', 'distribution': {'Male': 73.0, 'Female': 27.0}}
STATS = {'total_samples': 100, 'samples_needed': 46}


def assert_unmeasured(rec):
    assert rec.predicted_harm.status == 'not_measured'
    assert rec.predicted_harm.performance_gap_percentage is None
    assert rec.predicted_harm.patients_affected_per_100 is None
    assert rec.predicted_harm.annual_impact_estimate is None
    assert rec.immediate_technical_fix.expected_improvement.startswith('Not measured.')


@pytest.mark.parametrize('field,value', [
    ('performance_gap_percentage', 10.0),
    ('performance_gap_percentage', 0),
    ('patients_affected_per_100', 10),
    ('patients_affected_per_100', '11'),
    ('annual_impact_estimate', '100 patients per year'),
    ('clinical_consequence', '11 out of 100 patients misdiagnosed'),
])
def test_schema_rejects_unsupported_measurements(field, value):
    with pytest.raises(ValidationError):
        HarmQuantification(**{field: value})


def test_schema_rejects_accuracy_promise():
    with pytest.raises(ValidationError):
        TechnicalMitigation(method='SMOTE', python_code='# example',
                            expected_improvement='Accuracy: 71% to 84%', limitations='Not validated')


@pytest.mark.parametrize('failure', [RuntimeError('offline'), 'invalid json'])
def test_failed_model_returns_unavailable_not_invented_harm(failure):
    kwargs = {'side_effect': failure} if isinstance(failure, Exception) else {'return_value': {'response': failure}}
    with patch('ollama.generate', **kwargs):
        rec = FairnessSpecialist().analyze_bias(BIAS, {}, STATS)
    assert_unmeasured(rec)


def test_model_numbers_are_rejected_instead_of_clamped():
    specialist = FairnessSpecialist()
    payload = specialist._create_fallback_recommendation(BIAS, STATS, {}).model_dump()
    payload['predicted_harm']['patients_affected_per_100'] = 32.75
    payload['immediate_technical_fix']['expected_improvement'] = 'Accuracy improves by 13%'
    with patch('ollama.generate', return_value={'response': json.dumps(payload)}):
        assert_unmeasured(specialist.analyze_bias(BIAS, {}, STATS))


def test_valid_model_response_preserves_unavailable_and_observed_distribution():
    specialist = FairnessSpecialist()
    payload = specialist._create_fallback_recommendation(BIAS, STATS, {}).model_dump()
    payload['recommendation_priority'] = 'Review cohort coverage with the research team.'
    with patch('ollama.generate', return_value={'response': json.dumps(payload)}) as generate:
        rec = specialist.analyze_bias(BIAS, {}, STATS)
    assert_unmeasured(rec)
    assert rec.current_distribution == BIAS['distribution']
    assert rec.recommendation_priority == payload['recommendation_priority']
    prompt = generate.call_args.kwargs['prompt']
    assert '"performance_gap_percentage": null' in prompt
    assert 'Women accuracy: 71%' not in prompt
