"""Synthetic Revelio-like extract (same schemas and layout as the KLC download)."""
from datetime import date
from decimal import Decimal
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

S, D, I16, F = pa.string(), pa.date32(), pa.int16(), pa.float64()
MONEY = pa.decimal128(19, 2)
SCHEMAS = {
    'individual_positions': [('user_id', S), ('position_id', S), ('region', S), ('country', S), ('state', S),
                             ('metro_area', S), ('msa', S), ('city', S), ('startdate', D), ('enddate', D),
                             ('role_k1500_v2', S), ('role_k17000_v3', S), ('remote_suitability', F), ('weight', F),
                             ('start_salary', MONEY), ('end_salary', MONEY), ('seniority', I16), ('salary', MONEY),
                             ('position_number', I16), ('rcid', S), ('ultimate_parent_rcid', S), ('onet_code', S),
                             ('total_compensation', MONEY), ('additional_compensation', MONEY)],
    'individual_positions_raw': [('user_id', S), ('position_id', S), ('company_raw', S), ('location_raw', S),
                                 ('title_raw', S), ('description', S)],
    'individual_user': [('user_id', S), ('fullname', S), ('prestige', F), ('highest_degree', S),
                        ('user_location', S), ('user_country', S), ('updated_dt', D), ('numconnections', pa.int32())],
    'people_cohort': [('user_id', S)],
    'individual_role_lookup_v2': [('role_k1500_v2', S), ('role_k150_v2', S), ('role_k50_v2', S), ('job_category_v2', S)],
    'individual_role_lookup_v3': [('role_k17000_v3', S), ('role_k150_v3', S), ('role_k50_v3', S), ('role_k10_v3', S),
                                  ('onet_code', S), ('onet_title', S)],
    'company_mapping': [('rcid', S), ('company', S), ('ultimate_parent_rcid', S), ('hq_country', S), ('rics_k50', S)],
    'individual_user_education': [('user_id', S), ('university_name', S), ('rsid', S), ('education_number', F),
                                  ('startdate', D), ('enddate', D), ('degree', S)],
    'school_mapping': [('rsid', S), ('school_name', S), ('country', S)],
}


def month(text):
    if text is None:
        return None
    year, mon = map(int, text.split('-')[:2])
    return date(year, mon, 1)


class Extract:
    def __init__(self):
        self.rows = {name: [] for name in SCHEMAS}
        self.parts = {'individual_positions_raw': 3, 'individual_positions': 2}

    def person(self, user_id, country='Hong Kong', updated='2026-05-15', cohort=True):
        self.rows['individual_user'].append({'user_id': user_id, 'fullname': None, 'prestige': 0.1,
                                             'highest_degree': 'Bachelor', 'user_location': country,
                                             'user_country': country, 'updated_dt': date.fromisoformat(updated),
                                             'numconnections': 100})
        if cohort:
            self.rows['people_cohort'].append({'user_id': user_id})
        return self

    def job(self, user_id, position_id, start, end, country, title='Analyst', rcid='auto', parent=None,
            role='r1', role3='r3a', raw=True):
        rcid = f'c{position_id}' if rcid == 'auto' else rcid
        self.rows['individual_positions'].append({
            'user_id': user_id, 'position_id': position_id, 'country': country, 'city': None,
            'metro_area': 'hong kong metropolitan area' if country == 'Hong Kong' else None,
            'startdate': month(start), 'enddate': month(end), 'role_k1500_v2': role, 'role_k17000_v3': role3,
            'weight': 1.0, 'seniority': 2, 'salary': Decimal('1000.00'), 'position_number': 1,
            'rcid': rcid, 'ultimate_parent_rcid': parent if parent is not None else rcid})
        if raw:
            self.raw(user_id, position_id, title)
        return self

    def raw(self, user_id, position_id, title):
        self.rows['individual_positions_raw'].append({'user_id': user_id, 'position_id': position_id,
                                                      'title_raw': title, 'description': 'text'})
        return self

    def lookups(self):
        self.rows['individual_role_lookup_v2'] += [{'role_k1500_v2': 'r1', 'role_k150_v2': 'a', 'role_k50_v2': 'b',
                                                    'job_category_v2': 'Finance'}]
        self.rows['individual_role_lookup_v3'] += [
            {'role_k17000_v3': 'r3a', 'role_k150_v3': 'x', 'role_k50_v3': 'y', 'role_k10_v3': 'z', 'onet_title': 'A'},
            # Conflicting duplicate lookup key: must be quarantined, never multiply positions.
            {'role_k17000_v3': 'r3dup', 'role_k150_v3': 'x1', 'role_k50_v3': 'y', 'role_k10_v3': 'z', 'onet_title': 'B'},
            {'role_k17000_v3': 'r3dup', 'role_k150_v3': 'x2', 'role_k50_v3': 'y', 'role_k10_v3': 'z', 'onet_title': 'B'}]
        self.rows['company_mapping'] += [{'rcid': r, 'company': f'Co {r}', 'ultimate_parent_rcid': r,
                                          'hq_country': 'Hong Kong', 'rics_k50': 'Finance'}
                                         for r in ('10', '11', '20', '30', '100')]
        self.rows['school_mapping'] += [{'rsid': '1', 'school_name': 'HKU', 'country': 'Hong Kong'}]
        return self

    def write(self, root, manifest_overrides=None):
        root = Path(root)
        manifest = {'status': 'complete', 'country': 'Hong Kong', 'tables': {}, 'unmatched_raw': {},
                    'finished_at_utc': '2026-10-06T00:00:00+00:00', 'snapshots': 'synthetic'}
        for name, fields in SCHEMAS.items():
            schema = pa.schema(fields)
            rows = [{f: r.get(f) for f, _ in fields} for r in self.rows[name]]
            table = pa.Table.from_pylist(rows, schema=schema)
            parts = max(1, min(self.parts.get(name, 1), len(rows)))
            folder = root / name
            folder.mkdir(parents=True)
            size, step = 0, max(1, -(-len(rows) // parts))
            for i in range(parts):
                chunk = table.slice(i * step, step)
                path = (folder / f'unit-{i:06d}' / 'part-00000.parquet') if name == 'individual_positions_raw' \
                    else folder / f'part-{i:05d}.parquet'
                path.parent.mkdir(parents=True, exist_ok=True)
                pq.write_table(chunk, path)
                size += path.stat().st_size
            manifest['tables'][name] = {'status': 'complete', 'rows': len(rows), 'expected_rows': len(rows),
                                        'parts': parts, 'bytes': size, 'source': f'synthetic.{name}'}
        manifest['actual_bytes'] = sum(t['bytes'] for t in manifest['tables'].values())
        for key, value in (manifest_overrides or {}).items():
            manifest['tables'][key].update(value)
        (root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        return root


def scenario():
    """Histories exercising every measurement rule (see test_pipeline.py)."""
    e = Extract().lookups()
    hk, sg, uk = 'Hong Kong', 'Singapore', 'United Kingdom'
    e.person('p01').job('p01', '101', '2015-01', None, hk)                        # continuous stayer
    e.person('p02').job('p02', '201', '2018-01', '2020-02', hk).job('p02', '202', '2020-02', None, sg)  # within-quarter move
    e.person('p03').job('p03', '301', '2019-01', '2020-03', hk).job('p03', '302', '2020-04', None, sg)  # inclusive end month
    e.person('p04').job('p04', '401', '2021-01', '2021-02', hk)                   # spell between quarter ends
    e.person('p05').job('p05', '501', '2016-01', None, hk).job('p05', '502', '2020-06', None, sg, title='Board Member')
    e.person('p06').job('p06', '200', '2017-01', None, hk).job('p06', '1000', '2017-01', None, uk)  # tie -> '1000'
    e.person('p07').job('p07', '701', None, None, sg).job('p07', '702', '2015-01', None, hk)  # undated quarantined
    e.person('p08').job('p08', '801', None, None, hk)                             # only undated -> profile-only
    e.person('p09').job('p09', '901', '2015-01', None, hk).job('p09', '902', '2026-09', None, sg)  # after cutoff
    e.person('p10', updated='2026-05-10').job('p10', '1001', '2019-01', None, None)  # profile fallback HK
    e.person('p11', country=sg, updated='2017-03-01').job('p11', '1101', '2016-01', '2018-12', None)  # stale profile
    e.person('p12', updated='2026-04-10')                                         # profile-only, complete quarter
    e.person('p13', updated='2026-08-20')                                         # profile-only, partial quarter
    e.person('p14', updated='2021-02-01').job('p14', '1401', '2018-01', None, hk)  # stale: cap at refresh
    e.person('p15').job('p15', '1501', '2015-01', '2020-12', hk).job('p15', '1502', '2021-01', '2021-03', sg) \
        .job('p15', '1503', '2021-04', None, hk)                                  # one-quarter excursion
    e.person('p16').job('p16', '1601', '2015-01', '2019-12', hk).job('p16', '1602', '2020-01', '2021-12', uk) \
        .job('p16', '1603', '2022-01', None, hk)                                  # persistent move and return
    e.person('p17').job('p17', '1701', '2015-01', '2020-06', hk).job('p17', '1702', '2021-01', None, sg)  # gap
    e.person('p18').job('p18', '1801', '2015-01', '2023-03', sg).job('p18', '1802', '2023-04', None, hk)  # late entry
    e.person('p19').job('p19', '1901', '2022-01', None, hk)                       # unknown at window start
    big = '2400288101'
    e.person(big).job(big, '9223372036854775807', '2015-01', '2020-12', hk) \
        .job(big, '-9223372036854775808', '2021-01', None, uk, role3='r3dup') \
        .job(big, '18446744073709551615', '2010-01', '2012-12', sg)
    e.rows['individual_positions'].append(dict(e.rows['individual_positions'][-1]))  # exact duplicate row
    e.raw(big, '18446744073709551615', 'Analyst')                                   # exact duplicate raw row
    e.person('p21').job('p21', '2101', '2015-01', '2020-12', hk, rcid='10', parent='100') \
        .job('p21', '2102', '2021-01', None, sg, rcid='11', parent='100')         # same-parent transfer
    e.person('p22').job('p22', '2201', '2015-01', '2020-12', hk).job('p22', '2202', '2021-01', None, sg, rcid=None)
    e.person('p23').job('p23', '2301', '2015-01', None, hk) \
        .job('p23', '2301', '2015-01', None, sg, raw=False)                       # conflicting position key
    e.person('p24').job('p24', '2401', '2015-01', None, hk, raw=False)
    e.raw('p24', '2401', 'Analyst').raw('p24', '2401', 'Intern')                 # conflicting raw title key
    e.rows['individual_user_education'].append({'user_id': 'p01', 'university_name': 'HKU', 'rsid': '1',
                                                'education_number': 1.0, 'degree': 'Bachelor'})
    return e
