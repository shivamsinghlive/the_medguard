"""Widget board, research-question answers, and explanations built from computed results.

All text here is generated from measured values. The optional AI explanation
receives the same aggregate facts and is replaced by the rule-based summary if
it is unavailable or makes claims outside the evidence.
"""
import re
from typing import Dict, List, Optional

from explorer import llm

WIDGET_FINDINGS = {
    'outcome': {'missing_outcome_labels', 'single_class', 'class_imbalance', 'minority_class_small'},
    'groups': {'small_group_outcome_cells'},
    'intersections': {'small_intersection_cells'},
    'leakage': {'possible_leakage', 'weak_single_feature_signal'},
    'features': {'constant_feature', 'id_like_feature'},
    'missingness': {'missingness_differs'},
    'correlations': {'redundant_features'},
}
TITLES = {
    'validation': 'File check', 'screening': 'Identifier screen', 'outcome': 'Class balance',
    'representation': 'Representation', 'groups': 'Group x outcome', 'intersections': 'Intersections',
    'leakage': 'Leakage & rank', 'features': 'Feature profile', 'missingness': 'Missingness',
    'correlations': 'Correlations', 'distributions': 'Distributions', 'projection': '2-D map (PCA)',
}
BANNED = re.compile(r'\b(fair|unbiased|biased|safe|guarantee[sd]?|certif\w*|compliant|will work|'
                    r'accura\w*|clinically valid\w*|smote|oversampl\w*)\b', re.I)


def _pct(value) -> str:
    return '-' if value is None else f'{value * 100:.1f}%'


def widget_findings(widget: str, results: dict) -> List[dict]:
    if widget == 'screening':
        return results['screening']['findings']
    if widget == 'representation':
        return results['representation']['findings'] if results.get('representation') else []
    if widget == 'validation':
        return []
    codes = WIDGET_FINDINGS.get(widget, set())
    return [f for f in results['readiness']['findings'] if f['code'] in codes]


def _status(widget: str, results: dict, findings: List[dict]) -> str:
    r = results['readiness']
    if widget in ('outcome', 'groups', 'intersections', 'leakage') and not r['outcome']:
        return 'not_available'
    if widget == 'groups' and not r['group_balance']:
        return 'not_available'
    if widget == 'intersections' and not r['intersections']:
        return 'not_available'
    if widget == 'representation' and not results.get('representation'):
        return 'not_available'
    if widget == 'screening':
        return results['screening']['status']
    if widget == 'representation':
        return results['representation']['status']
    if any(f['priority'] in ('high', 'medium') for f in findings):
        return 'review_needed'
    return 'descriptive_only'


def _headline(widget: str, results: dict) -> str:
    r, v = results['readiness'], results['validation']
    if widget == 'validation':
        return f"{v['row_count']:,} rows x {v['column_count']} columns accepted" + (
            f" ({len(v['warnings'])} warning{'s' * (len(v['warnings']) != 1)})" if v['warnings'] else '')
    if widget == 'screening':
        n = len(results['screening']['findings'])
        return f'{n} potential identifier signal{"s" * (n != 1)}' if n else 'No patterns found (not de-identification)'
    if widget == 'representation':
        rep = results.get('representation')
        return f"{len(rep['attributes'])} attribute(s) - {rep['status'].replace('_', ' ')}" if rep else 'Choose demographic columns'
    o = r['outcome']
    if widget == 'outcome':
        if not o:
            return 'Choose an outcome column'
        if not o['minority']:
            return f"Only one class: {o['classes'][0]['label'] if o['classes'] else 'none'}"
        return (f"Minority '{o['minority']['label']}' is {_pct(o['minority']['proportion'])} "
                f"(1 : {o['imbalance_ratio']:g})")
    if widget == 'groups':
        cells = [g['smallest_cell'] for g in r['group_balance'] if g['smallest_cell']]
        if not cells:
            return 'Choose an outcome and demographic columns'
        c = min(cells, key=lambda c: c['count'])
        return f"Smallest cell: {c['group']} x {c['class']} = {c['count']}"
    if widget == 'intersections':
        if not r['intersections']:
            return 'Needs two demographic columns'
        small = sum(i['small_cells'] for i in r['intersections'])
        total = sum(len(i['cells']) for i in r['intersections'])
        return f"{small} of {total} combined cells below {r['settings']['min_cell']:g} cases"
    if widget == 'leakage':
        if not r['rank']:
            return 'No features scored'
        top = r['rank'][0]
        return f"Strongest single feature: {top['column']} ({top['metric'].upper()} {top['value']:.2f})"
    if widget == 'features':
        f = [x for x in r['features'] if x['role'] == 'feature']
        return (f"{len(f)} features - {sum(x['constant'] for x in f)} constant - "
                f"{sum(x['id_like'] for x in f)} ID-like")
    if widget == 'missingness':
        gaps = [m['max_gap_pp'] for m in r['missingness'] if m['max_gap_pp'] is not None]
        return (f"{len(r['missingness'])} column(s) with missing values"
                + (f" - largest gap {max(gaps):.1f} pp" if gaps else ''))
    if widget == 'correlations':
        n = len(r['correlations']['redundant_pairs'])
        return f"{len(r['correlations']['columns'])} numeric features - {n} near-duplicate pair{'s' * (n != 1)}"
    if widget == 'distributions':
        return f"{len(r['distributions'])} distributions" + (f" split by {r['roles']['outcome']}" if r['roles']['outcome'] else '')
    if widget == 'projection':
        p = r['projection']
        if not p['points']:
            return p.get('reason', 'Not available')
        return f"{len(p['features'])} numeric features - {sum(p['explained_variance']) * 100:.0f}% of variance shown"
    return ''


def board(results: dict, widgets: List[str]) -> List[dict]:
    cards = []
    for widget in widgets:
        findings = widget_findings(widget, results)
        cards.append({'id': widget, 'title': TITLES[widget], 'status': _status(widget, results, findings),
                      'headline': _headline(widget, results), 'finding_count': len(findings)})
    return cards


def answers(results: dict, plan_focus: List[dict]) -> List[dict]:
    """Plain answers to the questions a researcher asks before training."""
    r, out = results['readiness'], []
    o = r['outcome']
    if not o:
        out.append({'question': 'Is the outcome balanced?', 'status': 'not_available',
                    'answer': 'Select an outcome column to assess class balance.'})
    elif not o['minority']:
        out.append({'question': 'Is the outcome balanced?', 'status': 'review_needed',
                    'answer': 'Only one outcome class is present, so a classifier cannot be trained.'})
    else:
        flagged = any(f['code'] == 'class_imbalance' for f in r['findings'])
        out.append({'question': 'Is the outcome balanced?', 'status': 'review_needed' if flagged else 'descriptive_only',
                    'answer': (f"{o['minority']['count']:,} of {o['labeled_count']:,} labeled rows "
                               f"({_pct(o['minority']['proportion'])}) are '{o['minority']['label']}' - a 1 : "
                               f"{o['imbalance_ratio']:g} ratio. "
                               + ('This is below your review setting of '
                                  f"{_pct(r['settings']['imbalance_share'])}." if flagged else
                                  f"This is above your review setting of {_pct(r['settings']['imbalance_share'])}."))})
    absent = [f for f in plan_focus if f.get('missing')]
    if absent:
        out.append({'question': 'Is every focus group in your research idea present in the data?',
                    'status': 'review_needed',
                    'answer': '; '.join(f"No rows for '{f['concept']}' in {f['column']}" for f in absent)
                              + '. The dataset cannot support conclusions about these groups.'})
    if o and o['minority'] and r['group_balance']:
        balance = {g['column']: {row['label']: row for row in g['groups']} for g in r['group_balance']}
        focus = [f for f in plan_focus if not f.get('missing') and f['column'] in balance
                 and f['label'] in balance[f['column']]]
        if focus:
            parts, low = [], False
            for f in focus:
                row = balance[f['column']][f['label']]
                cls = ', '.join(f"{n:,} '{c}'" for c, n in row['classes'].items())
                low |= min(row['classes'].values()) < r['settings']['min_cell']
                parts.append(f"{f['label']} ({f['column']}): {row['count']:,} rows - {cls}")
            out.append({'question': 'Are there enough cases in your focus groups?',
                        'status': 'review_needed' if low else 'descriptive_only', 'answer': '; '.join(parts) + '.'})
        else:
            small = [f for f in r['findings'] if f['code'] == 'small_group_outcome_cells']
            out.append({'question': 'Does every group have enough cases of each outcome?',
                        'status': 'review_needed' if small else 'descriptive_only',
                        'answer': (f"{sum(f['evidence']['cell_count'] for f in small)} group x outcome cell(s) have fewer than "
                                   f"{r['settings']['min_cell']:g} cases." if small else
                                   f"Every group x outcome cell has at least {r['settings']['min_cell']:g} cases.")})
    weak = [f for f in r['findings'] if f['code'] == 'weak_single_feature_signal']
    if o and o['minority'] and r['rank']:
        top = r['rank'][0]
        out.append({'question': 'Do the features carry signal about the outcome?',
                    'status': 'review_needed' if weak else 'descriptive_only',
                    'answer': (f"Weak on their own: the strongest single feature is {top['column']} "
                               f"({top['metric'].upper()} {top['value']:.2f}; 0.5 AUC is chance). Combinations of "
                               'features are not assessed, so a model could still find signal - or none.')
                    if weak else
                    f"The strongest single feature is {top['column']} ({top['metric'].upper()} {top['value']:.2f}). "
                    'This is a single-feature check, not a model result.'})
    if o and o['minority']:
        leaks = [f for f in r['findings'] if f['code'] == 'possible_leakage']
        out.append({'question': 'Could a feature give away the answer?', 'status': 'review_needed' if leaks else 'descriptive_only',
                    'answer': ('Check ' + ', '.join(f"{f['column']} ({f['evidence']['metric'].upper()} {f['evidence']['value']:.2f})"
                                                   for f in leaks) + ': each almost determines the outcome alone.')
                    if leaks else 'No single feature crosses your leakage settings. Combinations are not checked.'})
    s = results['screening']
    out.append({'question': 'Does the data contain identifier signals?', 'status': s['status'],
                'answer': (f"{len(s['findings'])} signal(s) in " + ', '.join(sorted({f['column'] for f in s['findings']}))
                           + '. Screening is heuristic and does not certify de-identification.')
                if s['findings'] else 'No patterns found in the scanned rows. This is not de-identification.'})
    gaps = [m for m in r['missingness'] if m['max_gap_pp'] is not None and m['max_gap_pp'] >= r['settings']['missing_gap_pp']]
    out.append({'question': 'Is missing data uneven across classes or groups?',
                'status': 'review_needed' if gaps else 'descriptive_only',
                'answer': ('Uneven in ' + ', '.join(f"{m['column']} ({m['max_gap_pp']:.1f} pp)" for m in gaps) + '.')
                if gaps else 'No column crosses your missingness-gap setting.'})
    return out


def facts(widget: str, results: dict) -> dict:
    """Aggregate facts for one widget: counts and labels, never rows."""
    r = results['readiness']
    base = {'widget': TITLES.get(widget, widget), 'headline': _headline(widget, results),
            'findings': [{'title': f['title'], 'column': f['column'], 'evidence': f['evidence']}
                         for f in widget_findings(widget, results)][:8]}
    if widget == 'outcome' and r['outcome']:
        base['classes'] = r['outcome']['classes']
    if widget == 'groups':
        base['groups'] = [{'column': g['column'], 'groups': [{'label': x['label'], 'classes': x['classes']}
                                                             for x in g['groups']][:12]} for g in r['group_balance']]
    if widget == 'leakage':
        base['top_features'] = r['rank'][:8]
    if widget == 'missingness':
        base['columns'] = [{'column': m['column'], 'overall_rate': m['overall_rate'], 'max_gap_pp': m['max_gap_pp']}
                           for m in r['missingness']][:10]
    if widget == 'projection' and r['projection']['points']:
        base['projection'] = {'features': r['projection']['features'],
                              'explained_variance': r['projection']['explained_variance']}
    absent = [{'group': f['concept'], 'column': f['column']} for f in results.get('focus_groups', []) if f.get('missing')]
    if absent:
        base['focus_groups_with_no_rows'] = absent
    balance = {g['column']: {x['label']: x for x in g['groups']} for g in r['group_balance']}
    present = [{'group': f['label'], 'column': f['column'], 'rows': balance[f['column']][f['label']]['count'],
                'outcome_counts': balance[f['column']][f['label']]['classes']}
               for f in results.get('focus_groups', [])
               if not f.get('missing') and f['label'] in balance.get(f['column'], {})]
    if present:
        base['focus_groups'] = present
    return base


def _detail_points(widget: str, results: dict) -> List[str]:
    r, points = results['readiness'], []
    o = r['outcome']
    if widget == 'outcome' and o:
        points.append('Classes: ' + ', '.join(f"'{c['label']}' {c['count']:,} ({_pct(c['proportion'])})" for c in o['classes']) + '.')
        if o['missing_count']:
            points.append(f"{o['missing_count']:,} rows have no outcome label.")
    if widget == 'groups':
        for g in r['group_balance']:
            target = o['minority']['label'] if o and o['minority'] else None
            rates = [(x['rates'].get(target), x['label']) for x in g['groups'] if x['rates'].get(target) is not None]
            if target and len(rates) > 1:
                lo, hi = min(rates), max(rates)
                points.append(f"In {g['column']}, the share of '{target}' ranges from {_pct(lo[0])} ({lo[1]}) "
                              f"to {_pct(hi[0])} ({hi[1]}).")
    if widget == 'leakage':
        points += [f"{x['column']}: {x['metric'].upper()} {x['value']:.2f}" for x in r['rank'][:3]]
    if widget == 'missingness':
        top = sorted(r['missingness'], key=lambda m: -(m['overall_rate'] or 0))[:3]
        points += [f"{m['column']}: {_pct(m['overall_rate'])} missing" + (f", gap {m['max_gap_pp']:.1f} pp" if m['max_gap_pp'] else '')
                   for m in top]
    return points


def rule_explanation(widget: str, results: dict) -> dict:
    f = facts(widget, results)
    points = _detail_points(widget, results) + [f"Flag: {x['title']} ({x['column']})." for x in f['findings'][:3]]
    points += [f"No rows for '{a['group']}' in {a['column']}." for a in f.get('focus_groups_with_no_rows', [])]
    return {'summary': f['headline'] + '.', 'points': points[:5] or ['No review flags for this widget.'],
            'caution': 'These are descriptive dataset signals; they do not measure model performance or fairness.'}


def _mentions_absent_group(text: str, widget_facts: dict) -> bool:
    """True if the text names a population group whose labels are absent from the facts."""
    import json
    from explorer.planner import CONCEPTS
    words = set(re.findall(r'[a-z]+', text.lower()))
    known = json.dumps(widget_facts).lower()
    for triggers, _, labels in CONCEPTS.values():
        if labels and words & triggers and not any(f'"{l}"' in known for l in labels):
            return True
    return False


SYSTEM = """You explain one panel of a healthcare dataset-readiness audit to a researcher.
Use only the JSON facts. Do not claim a model will work, is accurate, fair, safe, compliant, or validated.
Do not recommend SMOTE or oversampling. Be concrete with the numbers given. Plain language.
Mention only groups, columns, and numbers that appear in the facts; never add groups from the research question.
The facts describe this one panel. Never say data is missing unless "focus_groups_with_no_rows" says so.
Return only JSON: {"summary": string, "points": [string, up to 4], "caution": string}"""


def explain(widget: str, results: dict, idea: dict, *, use_ai: bool = True, model: str = llm.DEFAULT_MODEL,
            chat=None) -> dict:
    fallback = rule_explanation(widget, results)
    if not use_ai:
        return {'source': 'rules', 'reason': 'AI explanations are turned off.', **fallback}
    import json
    try:
        raw = (chat or llm.chat_json)(SYSTEM, f"Research question: {idea.get('question', '')}\n"
                                              f"Facts: {json.dumps(facts(widget, results))}", model=model)
        summary, points, caution = raw.get('summary'), raw.get('points'), raw.get('caution')
        if not isinstance(summary, str) or not isinstance(points, list) or not all(isinstance(p, str) for p in points):
            raise llm.LLMUnavailable('The local model returned an unexpected shape.')
        text = ' '.join([summary, caution or ''] + points)
        widget_facts = facts(widget, results)
        claims_absence = re.search(r"\b(no|lack of|missing|absent|without)\s+(data|rows|records|information|cases)\b", text, re.I)
        if BANNED.search(text) or _mentions_absent_group(text, widget_facts) or (
                claims_absence and 'focus_groups_with_no_rows' not in widget_facts):
            return {'source': 'rules', 'reason': 'The AI answer made a claim outside the evidence and was replaced.',
                    **fallback}
        return {'source': 'ai', 'reason': None, 'summary': summary, 'points': points[:4],
                'caution': caution if isinstance(caution, str) and caution else fallback['caution']}
    except llm.LLMUnavailable as exc:
        return {'source': 'rules', 'reason': str(exc), **fallback}
