"""Turn a research idea into a proposed analysis plan the user confirms.

Two planners: the local LLM (column names and the research text only, never
cell values) and a transparent rule-based matcher. The rules always run; the
AI result is used only for fields where it names real columns. Every choice
carries a reason so the user can see why it was suggested.
"""
import re
from typing import Dict, List, Optional

from explorer import llm
from services.privacy_screening import _name_finding, _tokens

WIDGETS = ['validation', 'screening', 'rows', 'outcome', 'representation', 'groups', 'intersections',
           'leakage', 'features', 'missingness', 'correlations', 'distributions', 'projection']
OUTCOME_WIDGETS = {'outcome', 'groups', 'intersections', 'leakage'}

OUTCOME_WORDS = {'outcome', 'target', 'label', 'diagnosis', 'disease', 'diabetes', 'death', 'mortality',
                 'died', 'readmission', 'readmit', 'event', 'positive', 'cancer', 'sepsis', 'stroke',
                 'failure', 'infection', 'heart', 'risk', 'survival', 'admitted'}
DEMOGRAPHIC_TOKENS = {'sex', 'gender', 'race', 'ethnicity', 'ethnic', 'ancestry'}

# concept -> (words in the research text, column tokens it implies, recorded labels it matches)
CONCEPTS = {
    'women': ({'women', 'woman', 'female', 'females', 'girls', 'maternal', 'pregnant'},
              {'sex', 'gender'}, {'female', 'f', 'woman', 'women', 'girl'}),
    'men': ({'men', 'man', 'male', 'males', 'boys'}, {'sex', 'gender'}, {'male', 'm', 'man', 'men', 'boy'}),
    'black': ({'black', 'african'}, {'race', 'ethnicity', 'ethnic'},
              {'black', 'african american', 'black or african american'}),
    'white': ({'white', 'caucasian'}, {'race', 'ethnicity', 'ethnic'}, {'white', 'caucasian'}),
    'asian': ({'asian'}, {'race', 'ethnicity', 'ethnic'}, {'asian'}),
    'hispanic': ({'hispanic', 'latino', 'latina', 'latinx'}, {'race', 'ethnicity', 'ethnic'},
                 {'hispanic', 'latino', 'hispanic or latino'}),
    'indigenous': ({'indigenous', 'native', 'aian', 'tribal', 'first nations'}, {'race', 'ethnicity', 'ethnic'},
                   {'indigenous', 'native american', 'american indian', 'american indian or alaska native',
                    'aian', 'native'}),
    'age': ({'older', 'elderly', 'seniors', 'aged', 'age', 'young', 'children', 'pediatric', 'adolescents'},
            {'age'}, set()),
}

SYSTEM = """You map a healthcare research description to columns of a dataset.
Use ONLY column names from the provided list, spelled exactly. Do not invent columns.
outcome: the single column the study wants to predict or explain, or null if unclear.
demographic_columns: columns describing population groups (sex, gender, race, ethnicity), not clinical measurements.
identifier_columns: columns that identify a person or record (IDs, record numbers).
Return only JSON: {"outcome": string|null, "demographic_columns": [string], "identifier_columns": [string],
"reasons": {"outcome": string, "demographic_columns": string, "identifier_columns": string}}"""


def _words(text: str) -> set:
    return set(re.findall(r'[a-z0-9]+', (text or '').lower()))


def _mentioned(column: str, text: str) -> bool:
    lowered = (text or '').lower()
    name = column.lower()
    return name in lowered or name.replace('_', ' ') in lowered or (
        bool(_tokens(column)) and _tokens(column) <= _words(text))


def _rule_outcome(columns: List[dict], idea: dict, demographics: set, identifiers: set):
    best, best_score, best_reason = None, 0, None
    for col in columns:
        name = col['name']
        if name in demographics or name in identifiers or col.get('id_like'):
            continue
        score, reasons = 0, []
        if _mentioned(name, idea.get('outcome', '')):
            score += 6
            reasons.append('named in your outcome of interest')
        elif _mentioned(name, idea.get('question', '')):
            score += 3
            reasons.append('mentioned in your research question')
        if _tokens(name) & OUTCOME_WORDS:
            score += 2
            reasons.append('its name looks like an outcome')
        if col.get('distinct') == 2:
            score += 1
            reasons.append('it has exactly two values')
        if score > best_score:
            best, best_score, best_reason = name, score, '; '.join(reasons)
    return (best, best_reason) if best_score >= 3 else (None, None)


def rule_plan(columns: List[dict], idea: dict) -> dict:
    text = ' '.join(str(idea.get(k, '')) for k in ('question', 'population', 'groups', 'outcome'))
    words = _words(text)
    concepts = {k for k, (triggers, _, _) in CONCEPTS.items()
                if words & triggers or any(t in text.lower() for t in triggers if ' ' in t)}

    demographics, identifiers, notes = [], [], []
    for col in columns:
        name, tokens = col['name'], _tokens(col['name'])
        finding = _name_finding(name)
        if finding and finding['evidence']['kind'] in ('record_identifier', 'medical_record_number', 'ssn',
                                                       'identifier_number', 'person_name', 'email', 'phone'):
            identifiers.append({'column': name, 'reason': f"name looks like an identifier ({finding['evidence']['kind']})",
                                'source': 'rules'})
            continue
        if col.get('id_like') and col.get('kind') != 'numeric':
            identifiers.append({'column': name, 'reason': 'every value is distinct', 'source': 'rules'})
            continue
        if tokens & DEMOGRAPHIC_TOKENS:
            implied = [k for k in concepts if CONCEPTS[k][1] & tokens]
            reason = 'demographic column name' + (f" and matches your focus on {', '.join(sorted(implied))}" if implied else '')
            demographics.append({'column': name, 'reason': reason, 'source': 'rules'})
        elif 'age' in tokens and 'age' in concepts:
            notes.append(f'Your idea mentions age. "{name}" is continuous; age bands are not created '
                         'automatically, so it is profiled as a feature rather than a group.')

    names_d = {d['column'] for d in demographics}
    names_i = {i['column'] for i in identifiers}
    outcome, reason = _rule_outcome(columns, idea, names_d, names_i)
    return {'outcome': {'column': outcome, 'reason': reason or 'no column clearly matched your outcome',
                        'source': 'rules'},
            'demographics': demographics, 'identifiers': identifiers, 'notes': notes,
            'concepts': sorted(concepts)}


def focus_groups(columns: List[dict], demographics: List[str], concepts: List[str]) -> List[dict]:
    """Match concepts from the research idea to recorded labels of demographic columns."""
    groups = []
    by_name = {c['name']: c for c in columns}
    for name in demographics:
        col = by_name.get(name, {})
        labels = col.get('labels') or [l['label'] for l in (col.get('top') or [])]
        for concept in concepts:
            _, implied, wanted = CONCEPTS[concept]
            if not wanted or not implied & _tokens(name):
                continue
            matched = [l for l in labels if l.strip().lower() in wanted]
            groups += [{'column': name, 'label': l, 'concept': concept, 'missing': False,
                        'reason': f'your idea mentions {concept}; "{l}" is a recorded value of {name}'}
                       for l in matched]
            if not matched:
                groups.append({'column': name, 'label': None, 'concept': concept, 'missing': True,
                               'reason': f'your idea mentions {concept}, but no recorded value of {name} '
                                         f'matches it (values: {", ".join(labels[:8])})'})
    return groups


def _ai_plan(columns: List[dict], idea: dict, model: str) -> dict:
    listing = '\n'.join(f"- {c['name']} ({c.get('kind')}, {c.get('distinct')} distinct values)" for c in columns)
    user = (f"Research question: {idea.get('question', '')}\nOutcome of interest: {idea.get('outcome', '')}\n"
            f"Population: {idea.get('population', '')}\nGroups of concern: {idea.get('groups', '')}\n\n"
            f"Columns:\n{listing}")
    return llm.chat_json(SYSTEM, user, model=model)


def build_plan(columns: List[dict], idea: dict, *, use_ai: bool = True, model: str = llm.DEFAULT_MODEL,
               ai_planner=None) -> dict:
    """Propose roles, focus groups, and widgets for the research idea."""
    names = [c['name'] for c in columns]
    plan = rule_plan(columns, idea)
    ai = {'used': False, 'model': model, 'error': None, 'privacy': 'Column names and your research '
          'text are sent to the local Ollama model on this computer; no cell values are sent.'}
    if use_ai:
        try:
            raw = (ai_planner or _ai_plan)(columns, idea, model)
            reasons = raw.get('reasons') if isinstance(raw.get('reasons'), dict) else {}
            outcome = raw.get('outcome')
            demo = [c for c in raw.get('demographic_columns') or [] if c in names]
            ids = [c for c in raw.get('identifier_columns') or [] if c in names]
            if isinstance(outcome, str) and outcome in names and outcome not in demo + ids:
                plan['outcome'] = {'column': outcome, 'reason': str(reasons.get('outcome') or 'suggested by the local AI'),
                                   'source': 'ai'}
                ai['used'] = True
            if demo:
                rule_reasons = {d['column']: d['reason'] for d in plan['demographics']}
                plan['demographics'] = [{'column': c, 'source': 'ai' if c not in rule_reasons else 'ai+rules',
                                         'reason': rule_reasons.get(c) or str(reasons.get('demographic_columns') or 'suggested by the local AI')}
                                        for c in dict.fromkeys(demo) if c != plan['outcome']['column']]
                ai['used'] = True
            if ids:
                known = {i['column'] for i in plan['identifiers']}
                plan['identifiers'] += [{'column': c, 'reason': str(reasons.get('identifier_columns') or 'suggested by the local AI'),
                                         'source': 'ai'} for c in ids if c not in known
                                        and c != plan['outcome']['column']]
                ai['used'] = True
            if not ai['used']:
                ai['error'] = 'The local AI did not name usable columns; rule-based suggestions are shown.'
        except llm.LLMUnavailable as exc:
            ai['error'] = str(exc)
    demographics = [d['column'] for d in plan['demographics']]
    has_outcome = plan['outcome']['column'] is not None
    widgets = [w for w in WIDGETS if (has_outcome or w not in OUTCOME_WIDGETS)
               and (w != 'intersections' or len(demographics) >= 2)]
    return {'source': 'ai' if ai['used'] else 'rules', 'ai': ai, 'outcome': plan['outcome'],
            'demographics': plan['demographics'], 'identifiers': plan['identifiers'],
            'focus_groups': focus_groups(columns, demographics, plan['concepts']),
            'concepts': plan['concepts'], 'notes': plan['notes'], 'widgets': widgets}
