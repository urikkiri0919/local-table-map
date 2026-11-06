"""Private source-scoped analysis, not a place match or publication approval.

Qualification sets must come from separately reviewed source headings. Unknown
units and potentially overlapping bureau-level units remain unqualified. This
is not general personal-name detection; source text still needs manual review.
"""
import re
import sys
from pathlib import Path
from collections import defaultdict

PROJECT = Path(__file__).resolve().parent.parent / 'expense-pilot'
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
from wide_data import merge_transactions, group_candidates

ROLE = re.compile(r'(?:시장|군수|읍장|면장|동장|국장|과장|실장|단장|관장|센터장|본부장|청장|의장|소장)$')
UNIT = re.compile(r'(?:과|실|단|관|본부|센터|소|읍|면|동|청|팀)$')


def sanitize_department(value, verified_units):
    """Return a qualified unit, never an inferred unit from a spender label."""
    name = re.sub(r'\s+', '', str(value or ''))
    allowed = {re.sub(r'\s+', '', str(unit)) for unit in verified_units}
    if not name or name not in allowed or ROLE.search(name):
        return None
    # A parent bureau and its child departments are not automatically independent.
    if name.endswith('국') or not UNIT.search(name):
        return None
    return name


def normalize_batches(batches, verified_units_by_source):
    """Copy inputs; retain reported labels separately from counting eligibility."""
    missing = set(batches) - set(verified_units_by_source)
    if missing:
        raise ValueError('Missing verified source qualification: ' + ','.join(sorted(missing)))
    result = {}
    for source, rows in batches.items():
        result[source] = []
        for original in rows:
            reported = original.get('reported_department', original.get('department', ''))
            basis = str(original.get('department_basis') or '').strip()
            eligible = sanitize_department(reported, verified_units_by_source[source]) if basis else None
            record = dict(original, reported_department=reported,
                          department=eligible or '',
                          department_qualification='qualified' if eligible else 'held_unknown_role_or_overlap')
            result[source].append(record)
    return result


def analyze_sources(batches, verified_units_by_source):
    """Keep name groups source-scoped until independent business/address review."""
    normalized = normalize_batches(batches, verified_units_by_source)
    sources = {}
    name_sources = defaultdict(set)
    for source in sorted(normalized):
        merged = merge_transactions({source: normalized[source]})
        candidates = group_candidates(merged['rows'])
        sources[source] = {'merge': merged, 'candidates': candidates}
        for row in merged['rows']:
            if row['classification'] in ('meal_candidate', 'review_purpose') and row.get('purpose'):
                name_sources[''.join(str(row['merchant']).split())].add(source)
    cross = [{'merchant_key': name, 'sources': sorted(owners)}
             for name, owners in sorted(name_sources.items()) if len(owners) > 1]
    return {'source_count': len(sources),
            'normalized_rows': sum(len(s['merge']['rows']) for s in sources.values()),
            'candidate_group_count': sum(len(s['candidates']) for s in sources.values()),
            'sources': sources, 'cross_source_names': cross}
