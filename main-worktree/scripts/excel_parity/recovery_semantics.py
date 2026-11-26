"""Isolated reference-design tests, never imported by production ERP services."""
from decimal import Decimal
from pathlib import Path
import collections
import json
import re
from u03_recovery_audit import OUT, immutable, p
from workbook_source import SourceBook, SOURCE, coord


def geometric_candidates(required, stocks, rotate=False):
    l, w, t = map(Decimal, map(str, required))
    if min(l, w, t) <= 0:
        return []
    return [s for s in stocks if Decimal(str(s['thickness'])) == t and (
        l <= Decimal(str(s['length'])) and w <= Decimal(str(s['width'])) or
        rotate and w <= Decimal(str(s['length'])) and l <= Decimal(str(s['width'])))]


def minimal(stocks):
    # Partial dimension order, NOT area ranking or invented ID tie-break.
    return [s for s in stocks if not any(
        z['length'] <= s['length'] and z['width'] <= s['width'] and
        (z['length'] < s['length'] or z['width'] < s['width']) for z in stocks)]


def resolve(required, stocks, compatible_ids=None, rotation=None):
    """Unknown compatibility/rotation are not FALSE and never silently approved."""
    direct = minimal(geometric_candidates(required, stocks, False))
    rotated = minimal(geometric_candidates(required, stocks, True))
    if not rotated:
        return {'status': 'BLOCKED_NO_GEOMETRIC_SPEC', 'material_id': None}
    if compatible_ids is None:
        return {'status': 'BLOCKED_MATERIAL_APPLICABILITY', 'material_id': None,
                'geometric_candidate_ids': [s['material_id'] for s in direct]}
    eligible = [s for s in stocks if s['material_id'] in compatible_ids]
    direct = minimal(geometric_candidates(required, eligible, False))
    rotated = minimal(geometric_candidates(required, eligible, True))
    if rotation is None and {s['material_id'] for s in direct} != {s['material_id'] for s in rotated}:
        return {'status': 'U03_DIRECTION_AFFECTS_RESOLUTION', 'material_id': None}
    result = rotated if rotation else direct
    if len(result) != 1:
        return {'status': 'BLOCKED_NO_COMPATIBLE_SPEC' if not result else 'BLOCKED_AMBIGUOUS_MATERIAL', 'material_id': None}
    return {'status': 'RESOLVED', 'material_id': result[0]['material_id'], 'bucket_key': [result[0][k] for k in ('material_id', 'length', 'width', 'thickness')] + ['m²']}


def net_area(l, w, quantity):
    return Decimal(str(l)) * Decimal(str(w)) * Decimal(str(quantity)) / Decimal(1000000)


def gross_area(net, loss_rate):
    if loss_rate is None:
        return None
    rate = Decimal(str(loss_rate))
    if not 0 <= rate < 1:
        raise ValueError('LOSS_RATE_OUT_OF_RANGE')
    return Decimal(str(net)) * (1 + rate)


def gross_edges(edges_mm, quantity, allowance_mm):
    if allowance_mm is None:
        return None
    if Decimal(str(allowance_mm)) < 0:
        raise ValueError('NEGATIVE_EDGE_ALLOWANCE')
    return sum((Decimal(str(e)) + Decimal(str(allowance_mm))) * Decimal(str(quantity)) / 1000 for e in edges_mm)


def prepare_business_evidence():
    formal = p.read(OUT / 'FORMAL_READONLY_SNAPSHOT.json')['tables']
    book = SourceBook()
    purchase_path = SOURCE.parent / '10采购物料.xlsx'
    purchase = SourceBook(purchase_path).sheets['采购物料']
    identities = {r['target_entity_id']: r for r in formal['masterdata_external_identity']['rows'] if r['target_entity_type'] == 'materials' and r['source_object_type'] == 'PURCHASE_MATERIAL_SOURCE'}
    stocks, incomplete = [], []
    for material in formal['material']['rows']:
        identity = identities.get(str(material['id']))
        if not identity or not material['is_active'] or not material['is_purchased'] or material['material_type'] != 'raw':
            continue
        audit = json.loads(identity['audit_metadata'])
        p.require(audit['sourceSha256'].upper() == p.digest(purchase_path), 'PURCHASE SOURCE IDENTITY SHA DRIFT')
        row = audit['sourceRow']
        if purchase.get('E' + str(row), {}).get('value') != '板材':
            continue
        spec = material['specification'] or ''
        match = re.fullmatch(r'(\d+(?:\.\d+)?)\*(\d+(?:\.\d+)?)\*(\d+(?:\.\d+)?)', spec)
        info = {'material_id': material['id'], 'code': material['code'], 'name': material['name'], 'formal_specification': spec, 'base_uom': material['unit'],
            'company_id': material['company_id'], 'source_row': row, 'source_category': purchase.get('D' + str(row), {}).get('value'),
            'source_specification': purchase.get('G' + str(row), {}).get('value'), 'source_identity': identity['external_id'],
            'material_compatibility': 'PENDING_FORMAL_CONSTRAINT', 'rotation_allowed': None, 'grain_direction': None,
            'dimension_provenance': 'FORMAL_SPECIFICATION_TEXT; SOURCE_CONFIRMED_MM_CONTEXT; NOT_NEW_FORMAL_FIELDS', 'requirement_uom': 'm²'}
        if match:
            info.update(zip(('length', 'width', 'thickness'), map(float, match.groups())))
            stocks.append(info)
        else:
            incomplete.append(info)
    real = p.read(OUT / 'REAL_ROW_SOURCE_FACTS.json')
    decisions = []
    for r in real:
        if r['sheet'] != '三合一生产单':
            continue
        rn = r['row']
        value = lambda col: r['source_cells'].get(col + str(rn), {}).get('value')
        required = [value(x) for x in 'JKL']
        direct = minimal(geometric_candidates(required, stocks))
        rotated = minimal(geometric_candidates(required, stocks, True))
        decisions.append({'sheet': r['sheet'], 'row': rn, 'source_part': value('G'), 'required_dimensions': required, 'quantity': value('M'),
            'source_material_basis': '物料目录(设计)!I62 = 实木多层板; not a selected stock Material ID',
            'net_area_m2': str(net_area(required[0], required[1], value('M'))),
            'geometry_minimum_ids': [s['material_id'] for s in direct], 'rotation_alternative_ids': [s['material_id'] for s in rotated],
            'direction_affects_geometric_minimum': {s['material_id'] for s in direct} != {s['material_id'] for s in rotated},
            'resolution': resolve(required, stocks), 'formula_scope_vs_material_applicability': 'SOURCE_ROW_CALCULATION; NO_AUTOMATIC_STOCK_ASSIGNMENT'})
    sources = []
    for filename in ('05半成品板材.xlsx', '10采购物料.xlsx', '12木皮.xlsx', '13坯板.xlsx'):
        path = SOURCE.parent / filename
        sb = SourceBook(path)
        hits = [{'sheet': s, 'cell': a, 'value': v['value']} for s, cells in sb.sheets.items() for a, v in cells.items() if not v['formula'] and isinstance(v['value'], str) and any(x in v['value'].lower() for x in ('rotation', 'grain', '旋转', '纹理方向', '预留', '损耗'))]
        sources.append({'path': str(path), 'sha': p.digest(path), 'direction_loss_attribute_hits': hits})
    result = {'source_sha': p.EXPECTED_SHA, 'formal_snapshot_sha': p.digest(OUT / 'FORMAL_READONLY_SNAPSHOT.json'), 'sources': sources,
        'stocks': stocks, 'missing_formal_dimensions': incomplete, 'rows': decisions,
        'summary': {'formal_stock_candidates': len(stocks), 'distinct_geometric_specs': len({(s['length'], s['width'], s['thickness']) for s in stocks}),
            'formal_stock_lengths': sorted({s['length'] for s in stocks}), 'missing_dimension_count': len(incomplete), 'tri_rows': len(decisions),
            'row_status_counts': dict(collections.Counter(r['resolution']['status'] for r in decisions)), 'direction_affected_real_rows': sum(r['direction_affects_geometric_minimum'] for r in decisions)},
        'issues': ['Formal 2800*1220*1.8 and 3050*1220*1.8 remain literal 1.8; never silently converted to 18.',
            'No formal per-part material compatibility binding; same geometry has distinct substrates/finishes. Names are not approval.',
            'No formal direction/rotation policy. Current real geometry comparison does not require a new direction decision.',
            '13坯板 is a source category dictionary, not 36 available formal stock combinations.',
            'Database has zero rows in material requirement/selection tables, and current backend Python models do not declare those classes; existing tables are not sufficient evidence of runtime readiness.'],
        'production_write': 0}
    immutable('BOARD_STOCK_AND_REAL_ROW_AUDIT.json', result)
    family, _ = p.assets(p.load_manifest())
    candidates = p.read(Path(p.load_manifest()['evidence_directory']) / 'CANDIDATE_FORMULA_RECONSTRUCTION.json')
    ids = {c['family_id'] for c in candidates}
    register = []
    for f in family['families']:
        if not f['broken']:
            continue
        cells = [a for a, fid in family['cell_to_family'].items() if fid == f['family_id']]
        if all(a.startswith('房门单!') for a in cells):
            status, proposal = 'DEPRECATED_LEGACY_TEMPLATE', 'EXCLUDED_CURRENT_SCOPE; HISTORICAL_ONLY'
        elif f['family_id'] in ids:
            status, proposal = 'OLD_CANDIDATE_NOT_BUSINESS_EQUIVALENT', 'KEEP_S_NET_AREA; REPLACE_LENGTH_BANDS_WITH_DYNAMIC_FORMAL_STOCK_RESOLUTION_AND_BUCKETS'
        elif any(a.endswith('!AV30') for a in cells):
            status, proposal = 'RECOVERY_CANDIDATE_PENDING_NATIVE', 'SUM_VISIBLE_AREA_OF_REAL_TRI_ROWS * 1.20; source loss candidate only'
        elif any(a.endswith('!AV31') for a in cells):
            status, proposal = 'RECOVERY_CANDIDATE_PENDING_NATIVE', 'SUM_NET_EDGE_LENGTH_OF_REAL_TRI_ROWS; m; gross allowance policy pending'
        else:
            status, proposal = 'RECOVERY_PROJECTION_PENDING_MATERIAL_BINDING', 'ONE_TO_MANY_SUMIFS_BY_MATERIAL_ID_LENGTH_WIDTH_THICKNESS_UOM; no mixed length total'
        register.append({'family_id': f['family_id'], 'source_cells': cells, 'status': status, 'proposal': proposal,
                         'historically_verified': False, 'business_semantic_verified': False, 'source_write': 0})
    immutable('RECOVERY_REGISTER_U03.json', register)
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.stdout.reconfigure(encoding='utf-8')
    prepare_business_evidence()
