"""Count Hong Kong LinkedIn-source job ads by posting month and draw the trend.

Run ``aggregate`` beside the KLC extract with DuckDB, then ``plot`` locally
with Matplotlib. Only monthly counts leave KLC.
"""

import argparse
import calendar
import csv
from datetime import date, datetime, timezone
import json
from pathlib import Path


def aggregate(source):
    import duckdb

    source = Path(source)
    manifest = json.loads((source / 'manifest.json').read_text())
    table = manifest['tables']['postings_cosmos']
    if manifest.get('status') != 'complete' or table.get('status') != 'complete':
        raise ValueError('Hong Kong extract and postings table must be complete')
    pattern = str(source / 'postings_cosmos' / '**' / '*.parquet')
    con = duckdb.connect()
    con.execute('SET threads = 2')
    counts = con.execute('''
        SELECT count(*) AS rows, count(DISTINCT job_id) AS distinct_job_ids,
               count(*) FILTER (WHERE job_id IS NULL) AS missing_id,
               count(*) FILTER (WHERE post_date IS NULL) AS missing_date,
               count(*) FILTER (WHERE country IS DISTINCT FROM 'Hong Kong') AS non_hk,
               count(*) FILTER (WHERE source_linkedin IS NULL) AS missing_source,
               min(post_date) AS first_date, max(post_date) AS last_date
        FROM read_parquet(?)
    ''', [pattern]).fetchone()
    keys = ('rows', 'distinct_job_ids', 'missing_id', 'missing_date', 'non_hk',
            'missing_source', 'first_date', 'last_date')
    checks = dict(zip(keys, counts))
    if checks['rows'] != table['rows'] or checks['rows'] != checks['distinct_job_ids']:
        raise ValueError('Posting count or distinct job IDs differ from manifest')
    if any(checks[k] for k in ('missing_id', 'missing_date', 'non_hk', 'missing_source')):
        raise ValueError(f'Incomplete or non-Hong Kong posting rows: {checks}')
    rows = con.execute('''
        SELECT date_trunc('month', post_date)::DATE AS month,
               count(*) AS all_ads,
               count(*) FILTER (WHERE source_linkedin IS TRUE) AS linkedin_ads,
               min(post_date) AS first_date, max(post_date) AS last_date
        FROM read_parquet(?)
        GROUP BY 1 ORDER BY 1
    ''', [pattern]).fetchall()
    months = [dict(zip(('month', 'all_ads', 'linkedin_ads', 'first_date', 'last_date'), row))
              for row in rows]
    if sum(row['all_ads'] for row in months) != checks['rows']:
        raise ValueError('Monthly counts do not reconcile with the extract')
    if any(row['linkedin_ads'] > row['all_ads'] for row in months):
        raise ValueError('LinkedIn count exceeds all ads')
    return {
        'source': str(source), 'source_table': table['source'],
        'extract_finished_at_utc': manifest['finished_at_utc'],
        'aggregated_at_utc': datetime.now(timezone.utc).isoformat(),
        'definition': "One unique job_id with country = 'Hong Kong' and source_linkedin IS TRUE; grouped by post_date month.",
        'checks': checks, 'months': months,
    }


def next_month(day):
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)


def plot(input_path, output_dir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    report = json.loads(Path(input_path).read_text())
    observed = {date.fromisoformat(r['month']): int(r['linkedin_ads'])
                for r in report['months']}
    totals = {date.fromisoformat(r['month']): int(r['all_ads'])
              for r in report['months']}
    start = min(month for month, count in observed.items() if count)
    end = max(observed)
    months = []
    cursor = start
    while cursor <= end:
        months.append(cursor)
        cursor = next_month(cursor)
    counts = [observed.get(month, 0) for month in months]
    shares = [100 * observed.get(month, 0) / totals[month] if totals.get(month) else 0
              for month in months]
    last_post = date.fromisoformat(report['checks']['last_date'])
    incomplete_last = last_post.day < calendar.monthrange(last_post.year, last_post.month)[1]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / 'monthly_counts.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(('posting_month', 'linkedin_ads', 'all_hk_ads',
                         'linkedin_share_percent', 'partial_last_month'))
        for month, count, share in zip(months, counts, shares):
            writer.writerow((month.isoformat(), count, totals.get(month, 0),
                             round(share, 3), month == end and incomplete_last))

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False})
    fig, (ax, share_ax) = plt.subplots(2, 1, figsize=(13, 8), sharex=True,
                                      gridspec_kw={'height_ratios': [3, 1.25], 'hspace': .16})
    fig.patch.set_facecolor('#f8fafc')
    ax.set_facecolor('#f8fafc')
    share_ax.set_facecolor('#f8fafc')
    complete_months = months[:-1] if incomplete_last else months
    complete_counts = counts[:-1] if incomplete_last else counts
    ax.plot(complete_months, complete_counts, color='#167d88', linewidth=1.6,
            alpha=.72, label='Monthly ads')
    if len(complete_months) >= 12:
        rolling = [sum(complete_counts[i-11:i+1]) / 12 if i >= 11 else None
                   for i in range(len(complete_counts))]
        ax.plot(complete_months, rolling, color='#b84232', linewidth=2.8,
                label='12-month average')
    if incomplete_last:
        ax.plot([months[-2], months[-1]], [counts[-2], counts[-1]],
                color='#167d88', linewidth=1.6, linestyle=':')
        ax.scatter([end], [counts[-1]], color='#167d88', s=30, zorder=5)
        ax.annotate(f'Partial month\nthrough {last_post:%b %-d, %Y}',
                    (end, counts[-1]), xytext=(-8, 22), textcoords='offset points',
                    ha='right', color='#334155', fontsize=9)
    ax.set_ylim(bottom=0)
    ax.set_xlim(months[0], next_month(end))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.grid(axis='y', color='#dbe4ec', linewidth=.7)
    ax.set_axisbelow(True)
    ax.set_ylabel('Job ads posted per month')
    ax.set_title('LinkedIn-source job ads in Hong Kong', loc='left',
                 fontsize=19, fontweight='bold', pad=20)
    ax.legend(frameon=False, loc='upper left')
    share_ax.plot(complete_months, shares[:-1] if incomplete_last else shares,
                  color='#52637d', linewidth=1.7)
    share_ax.set_ylim(0, max(55, max(shares) * 1.1))
    share_ax.set_ylabel('LinkedIn share of all\nRevelio HK ads (%)')
    share_ax.grid(axis='y', color='#dbe4ec', linewidth=.7)
    share_ax.set_axisbelow(True)
    share_ax.xaxis.set_major_locator(mdates.YearLocator())
    share_ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    fig.text(.12, .052,
             'Source: Revelio Labs job postings extract, completed October 6, 2026. '
             'Unique job IDs; Hong Kong; LinkedIn source flag; posting dates.',
             fontsize=9, color='#475569')
    fig.text(.12, .032, 'Changing source coverage may affect these counts.',
             fontsize=9, color='#475569')
    fig.subplots_adjust(left=.12, right=.97, top=.88, bottom=.15, hspace=.14)
    for suffix in ('png', 'pdf'):
        fig.savefig(output_dir / f'hk_linkedin_postings_monthly.{suffix}',
                    dpi=220, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(json.dumps({
        'total_linkedin_ads': sum(counts),
        'first_linkedin_month': min((m.isoformat() for m, c in zip(months, counts) if c)),
        'last_posting_date': last_post.isoformat(),
        'last_month_partial': incomplete_last,
        'peak_complete_month': max(zip(complete_counts, complete_months))[1].isoformat(),
        'peak_complete_month_ads': max(complete_counts),
        'annual_counts': {str(year): sum(c for m, c in zip(months, counts) if m.year == year)
                          for year in range(start.year, end.year + 1)},
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    aggregate_parser = sub.add_parser('aggregate')
    aggregate_parser.add_argument('source', type=Path)
    plot_parser = sub.add_parser('plot')
    plot_parser.add_argument('input_json', type=Path)
    plot_parser.add_argument('output_dir', type=Path)
    args = parser.parse_args()
    if args.command == 'aggregate':
        print(json.dumps(aggregate(args.source), default=str))
    else:
        plot(args.input_json, args.output_dir)


if __name__ == '__main__':
    main()
