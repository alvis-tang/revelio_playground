"""Describe school/year coverage and the generic University of Malawi bucket."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

TARGETS = [
    'Chancellor College', 'Mzuzu University',
    'Lilongwe University of Agriculture and Natural Resources',
    'Malawi University of Science and Technology',
]
MISSING = '[missing]'
CLUES = {
    'Polytechnic / MUBAS': r'\bmubas\b|\bpolytechnic\b|malawi university of business and applied sciences',
    'Chancellor': r'\bchancellor\b',
    'Medicine / nursing / KUHeS': r'\bkuhes\b|college of medicine|kamuzu college of nursing|kamuzu university of health sciences',
}


def clean(series):
    return series.fillna('').astype(str).str.replace(r'\s+', ' ', regex=True).str.strip().replace('', MISSING)


def read_table(source, name, columns):
    import pyarrow.dataset as ds
    files = sorted((source / name).glob('*.parquet'))
    if not files:
        raise ValueError(f'No Parquet parts for {name}')
    return ds.dataset([str(f) for f in files], format='parquet').to_table(columns=columns).to_pandas()


def counts(frame, keys):
    return (frame.groupby(keys, dropna=False, observed=True)
            .agg(records=('user_id', 'size'), people=('user_id', 'nunique'))
            .reset_index().sort_values(['records', *keys], ascending=[False, *([True] * len(keys))]))


def run(source, output, start=2015, end=2025):
    import pandas as pd
    import pyarrow as pa
    pa.set_cpu_count(1)
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest['status'] != 'complete':
        raise ValueError('A complete extract is required.')
    education = read_table(source, 'individual_user_education',
                          ['user_id', 'rsid', 'education_number', 'university_name',
                           'university_country', 'field', 'degree', 'enddate'])
    schools = read_table(source, 'school_mapping', ['rsid', 'school_name', 'country'])
    education = education.merge(schools, on='rsid', how='left', validate='many_to_one')
    education['clean_school'] = clean(education['school_name'].fillna(education['university_name']))
    education['field_of_study'] = clean(education['field'])
    education['degree'] = clean(education['degree'])
    education['education_end_year'] = pd.to_datetime(education['enddate']).dt.year.astype('Int64')
    malawi = education[education['country'].eq('Malawi')].copy()
    window = malawi[malawi.education_end_year.between(start, end).fillna(False)]
    generic = malawi[malawi.clean_school.eq('University of Malawi')].copy()
    generic_window = generic[generic.education_end_year.between(start, end).fillna(False)]
    output.mkdir(parents=True, exist_ok=False)
    counts(window, ['clean_school', 'education_end_year']).to_csv(output / 'school_year.csv', index=False)
    school_audit = counts(malawi, ['clean_school'])
    for label, mask in {
        'missing_end_year': malawi.education_end_year.isna(),
        'before_window': malawi.education_end_year.lt(start),
        'after_window': malawi.education_end_year.gt(end),
        'in_window': malawi.education_end_year.between(start, end),
    }.items():
        values = malawi[mask.fillna(False)].groupby('clean_school').size()
        school_audit[label] = school_audit.clean_school.map(values).fillna(0).astype(int)
    school_audit.to_csv(output / 'school_coverage.csv', index=False)
    target = window[window.clean_school.isin(TARGETS)]
    for metric in ['records', 'people']:
        table = counts(target, ['clean_school', 'education_end_year'])
        pivot = table.pivot(index='education_end_year', columns='clean_school', values=metric)
        pivot = pivot.reindex(index=range(start, end + 1), columns=TARGETS).fillna(0).astype(int)
        pivot.to_csv(output / f'target_school_year_{metric}.csv')
    counts(generic, ['field_of_study', 'degree', 'education_end_year']).to_csv(
        output / 'university_of_malawi_field_degree_year_all.csv', index=False)
    counts(generic_window, ['field_of_study', 'degree', 'education_end_year']).to_csv(
        output / 'university_of_malawi_field_degree_year_window.csv', index=False)
    field_counts = counts(generic, ['field_of_study', 'degree'])
    field_counts.to_csv(output / 'university_of_malawi_field_degree.csv', index=False)
    raw = read_table(source, 'individual_user_education_raw',
                     ['user_id', 'education_number', 'university_raw', 'degree_raw', 'field_raw', 'description'])
    generic = generic.merge(raw, on=['user_id', 'education_number'], how='left',
                            validate='one_to_one', indicator=True)
    generic['field_raw'] = clean(generic['field_raw'])
    generic['degree_raw'] = clean(generic['degree_raw'])
    counts(generic, ['field_raw', 'degree_raw', 'education_end_year']).to_csv(
        output / 'university_of_malawi_raw_field_degree_year_all.csv', index=False)
    text = generic[['university_raw', 'degree_raw', 'field_raw', 'description']].fillna('').agg(' '.join, axis=1)
    clues = []
    for label, pattern in CLUES.items():
        subset = generic[text.str.contains(pattern, case=False, regex=True)]
        table = counts(subset, ['field_of_study', 'degree', 'education_end_year'])
        table.insert(0, 'explicit_text_clue', label)
        clues.append(table)
    pd.concat(clues, ignore_index=True).to_csv(output / 'university_of_malawi_explicit_clues.csv', index=False)
    summary = {
        'source': str(source), 'window': [start, end],
        'clean_school_rule': 'Mapped school name; fallback to education name; whitespace normalized only. No institution reassignment.',
        'year_rule': 'Year of recorded education enddate; not verified graduation. Missing years retained in all-years diagnostic.',
        'count_rule': 'Record counts and distinct people per cell; people can appear in multiple cells.',
        'malawi_records': len(malawi), 'malawi_people': int(malawi.user_id.nunique()),
        'country_disagreements': int((education.country.fillna(MISSING) != education.university_country.fillna(MISSING)).sum()),
        'generic_records': len(generic), 'generic_people': int(generic.user_id.nunique()),
        'generic_window_records': len(generic_window), 'generic_window_people': int(generic_window.user_id.nunique()),
        'generic_missing_end_year': int(generic.education_end_year.isna().sum()),
        'generic_missing_field': int(generic.field_of_study.eq(MISSING).sum()),
        'generic_missing_degree': int(generic.degree.eq(MISSING).sum()),
        'generic_unmatched_raw': int(generic['_merge'].eq('left_only').sum()),
        'explicit_clues': {label: {'records': int(text.str.contains(pattern, case=False, regex=True).sum()),
                                  'people': int(generic.loc[text.str.contains(pattern, case=False, regex=True), 'user_id'].nunique())}
                           for label, pattern in CLUES.items()},
        'clue_caution': 'Text matches may overlap and are evidence to review, not institution assignments.',
    }
    assert school_audit[['missing_end_year', 'before_window', 'after_window', 'in_window']].sum(axis=1).eq(school_audit.records).all()
    assert int(counts(generic, ['field_of_study', 'degree', 'education_end_year']).records.sum()) == len(generic)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    print('TARGET RECORD COUNTS\n' + (output / 'target_school_year_records.csv').read_text())
    print('SCHOOL COVERAGE\n' + school_audit.to_csv(index=False))
    print('TOP GENERIC FIELD / DEGREE\n' + field_counts.head(35).to_csv(index=False))
    print(f'OUTPUT: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--start-year', type=int, default=2015)
    parser.add_argument('--end-year', type=int, default=2025)
    args = parser.parse_args()
    if args.start_year > args.end_year:
        parser.error('start-year must not exceed end-year')
    output = args.output or args.source.parent.parent / 'results' / (
        'malawi_education_diagnostic_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run(args.source, output, args.start_year, args.end_year)
