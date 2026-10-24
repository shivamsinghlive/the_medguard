"""Knowledge-base claims must be traceable to the reviewed source inventory (W04)."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / 'knowledge_base'
INVENTORY = KB / 'SOURCES.md'
DOCUMENTS = sorted(KB.rglob('*.txt'))
CITATION = re.compile(r'\[(S\d+)\]')

# Claims removed in the W04 review; they must not return without a new review.
REMOVED_CLAIMS = ['>5%', '5% across groups', 'FDA 2021 Guidance', 'completely unreliable',
                  '3x national average', 'Heart disease death rate: 2x', '510(k) rejection',
                  '50% more likely', 'Very high: 400', 'Statistical Analysis Handbook']


def inventory():
    rows = {}
    for line in INVENTORY.read_text(encoding='utf-8').splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if re.fullmatch(r'S\d+', cells[0]):
            rows[cells[0]] = cells
    return rows


def test_inventory_rows_have_url_date_check_and_claims():
    rows = inventory()
    assert rows, 'SOURCES.md has no source rows'
    for source_id, cells in rows.items():
        _, title, publisher_date, url, checked, claims = cells
        assert url.startswith('https://'), source_id
        assert re.search(r'(19|20)\d\d', publisher_date), source_id
        assert checked in {'text read', 'abstract read', 'metadata only'}, source_id
        assert title and claims, source_id


@pytest.mark.parametrize('path', DOCUMENTS, ids=lambda p: p.relative_to(KB).as_posix())
def test_every_claim_cites_a_reviewed_source(path):
    text = path.read_text(encoding='ascii')  # the loader uses the platform default encoding
    lines = [l for l in text.splitlines() if l.strip()]
    assert lines[1].startswith('Reviewed: 20')
    rows = inventory()
    body, _, references = text.partition('\nSources:\n')
    assert references, 'missing Sources section'
    for line in [l for l in body.splitlines()[2:] if l.strip()]:
        cited = CITATION.findall(line)
        assert cited, f'uncited claim: {line!r}'
        assert set(cited) <= set(rows), f'unknown source in {line!r}'
        for source_id in cited:
            assert f'[{source_id}]' in references
            assert rows[source_id][3] in references  # URL is retrievable with the chunk


def test_every_inventory_source_is_used():
    cited = {s for p in DOCUMENTS for s in CITATION.findall(p.read_text(encoding='ascii'))}
    assert cited == set(inventory())


@pytest.mark.parametrize('claim', REMOVED_CLAIMS)
def test_removed_claims_do_not_return(claim):
    for path in DOCUMENTS:
        assert claim not in path.read_text(encoding='ascii'), f'{claim!r} in {path.name}'


def test_embeddings_limitation_is_documented():
    text = INVENTORY.read_text(encoding='utf-8')
    assert 'Retrieval and embeddings status' in text
    assert 'not** been verified' in text
