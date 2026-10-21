"""Check random selection, English filtering, and lossless JSON exports."""
from contextlib import redirect_stdout
from datetime import date
import io
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import hk_job_postings_sample as sample

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    pa = pq = None


def english_audit(text):
    letters = sum(char.isalpha() for char in text or '')
    return {'accepted': bool(letters), 'reason': 'english' if letters else 'empty_description',
            'group': 'English', 'letters': letters, 'language_letters': {'English': letters},
            'passages': [{'language': 'English', 'letters': letters}]}


class SelectionTests(unittest.TestCase):
    def test_uniform_permutation_has_no_replacement_and_is_repeatable(self):
        for size in (0, 1, 2, 97):
            first = list(sample.row_order(size, 42))
            self.assertEqual(sorted(first), list(range(size)))
            self.assertEqual(first, list(sample.row_order(size, 42)))
        self.assertNotEqual(list(sample.row_order(97, 42)), list(sample.row_order(97, 43)))
        self.assertEqual(len(set(itertools.islice(sample.row_order(10**12, 42), 100))), 100)

    def test_row_positions_cross_part_boundaries(self):
        parts = [{'part': 'first'}, {'part': 'second'}]
        positions = sample.positions_for([4, 0, 2, 1], parts, [2, 5])
        self.assertEqual([(p['part'], p['row']) for p in positions],
                         [('second', 2), ('first', 0), ('second', 0), ('first', 1)])

    def test_english_filter_rejects_other_substantial_passages(self):
        report = {'group': 'English', 'letters': 1000, 'language_letters': {'English': 900},
                  'passages': [{'language': 'English', 'letters': 900},
                               {'language': 'Chinese', 'letters': 100}]}
        with patch.object(sample.multilingual, 'classify', return_value=report):
            self.assertFalse(sample.english_check('text', object())['accepted'])
            report['passages'].pop()
            self.assertTrue(sample.english_check('text', object())['accepted'])
            report['group'] = None
            self.assertFalse(sample.english_check('text', object())['accepted'])
        for text in (None, '', ' \t\n'):
            self.assertEqual(sample.english_check(text, object())['reason'], 'empty_description')


@unittest.skipIf(importlib.util.find_spec('lingua') is None, 'Lingua is installed on KLC')
class RealLanguageTests(unittest.TestCase):
    def test_real_detector_accepts_english_and_rejects_bilingual_and_foreign_text(self):
        detector = sample.multilingual.detector()
        english = ('We are looking for a software engineer to join our technology team. '
                   'The successful candidate will develop reliable applications, review code, '
                   'and work with colleagues to improve our systems. Applicants should have '
                   'experience writing software and communicating clearly with customers. '
                   'We offer professional training, annual leave, and opportunities for career development. ')
        chinese = ('我們正在招聘軟件工程師加入技術團隊。申請人需要具有開發應用程式的經驗，'
                   '能夠與同事合作並且清楚了解客戶的業務需求。公司提供專業培訓和良好的工作環境。') * 3
        spanish = ('Buscamos un ingeniero de software para trabajar con nuestro equipo de tecnología. '
                   'La persona seleccionada desarrollará aplicaciones y colaborará con nuestros clientes. '
                   'Ofrecemos formación profesional y oportunidades para desarrollar su carrera. ') * 2
        self.assertTrue(sample.english_check(english, detector)['accepted'])
        self.assertFalse(sample.english_check(english + chinese, detector)['accepted'])
        self.assertFalse(sample.english_check(spanish, detector)['accepted'])


@unittest.skipIf(pa is None, 'Run with the KLC .venv-llm environment for PyArrow checks')
class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.raw = [{
            'job_id': str(12345678901234567890123456789000 + index),
            'title_raw': 'Résumé analyst 王', 'jobtitle_translated': None,
            'location_raw': 'Hong Kong\r\n香港',
            'description': '  Full description, "quotes".\r\nSecond line\tRésumé 王\n  ',
            'extra_raw_field': None,
        } for index in range(10)]
        self.raw[0]['description'] = None
        self.raw[1]['description'] = '\t\n '
        self.postings = [{
            'job_id': row['job_id'], 'country': 'Hong Kong', 'company': 'Example',
            'rcid': '12345678901234567890', 'ultimate_parent_rcid': None,
            'post_date': date(2020 + index % 6, 1, 2), 'salary': None,
            'source_linkedin': bool(index % 2), 'source_indeed': True,
        } for index, row in enumerate(self.raw)]
        self.postings[0]['ultimate_parent_rcid'] = '98765432109876543210'
        schema = pa.schema([(name, pa.string()) for name in self.raw[0]])
        table = pa.Table.from_pylist(self.raw, schema=schema)
        raw_path = self.source / 'postings_cosmos_raw'
        raw_path.mkdir()
        for index in range(0, 10, 3):
            pq.write_table(table.slice(index, 3), raw_path / f'part-{index:03d}.parquet', row_group_size=2)
        posting_path = self.source / 'postings_cosmos'
        posting_path.mkdir()
        pq.write_table(pa.Table.from_pylist(self.postings), posting_path / 'part-000.parquet')
        snapshot = {'status': 'complete', 'country': 'Hong Kong',
                    'finished_at_utc': '2026-10-06T23:47:53+00:00', 'tables': {
                        name: {'status': 'complete', 'rows': 10, 'source': 'test.' + name}
                        for name in ('postings_cosmos', 'postings_cosmos_raw')}}
        sample.write_json(self.source / 'manifest.json', snapshot)

    def run_sample(self, output, count=5, seed=42, batch_size=4):
        with patch.object(sample.multilingual, 'detector', return_value=object()), \
                patch.object(sample, 'english_check', side_effect=lambda text, _: english_audit(text)), \
                patch.object(sample.importlib.metadata, 'version', return_value='test'), \
                redirect_stdout(io.StringIO()):
            return sample.sample(self.source, output, count, seed, batch_size)

    def test_lossless_source_round_trip_all_fields_and_metadata(self):
        output = self.root / 'output'
        manifest = self.run_sample(output)
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual(manifest['requested_count'], 5)
        self.assertEqual(manifest['validation']['rows'], 5)
        self.assertEqual(len(list(output.glob('*.json'))), 6)
        originals = {row['job_id']: row for row in self.raw}
        for entry in manifest['selected']:
            row = json.loads((output / entry['filename']).read_text())
            raw = {key: value for key, value in row.items() if key != 'posting'}
            self.assertEqual(raw, originals[entry['job_id']])
            self.assertIsInstance(row['job_id'], str)
            self.assertEqual(row['posting']['rcid'], '12345678901234567890')
            self.assertIsNone(row['posting']['salary'])
            self.assertIsNone(row['extra_raw_field'])
            self.assertEqual(row['posting']['country'], 'Hong Kong')
            self.assertRegex(row['posting']['post_date'], r'^202\d-01-02$')
        self.assertTrue(sample.verify_export(output, self.source)['raw_fields_verified_against_source'])
        self.assertFalse(sample.verify_export(output)['raw_fields_verified_against_source'])

    def test_seed_is_repeatable_independent_of_batch_size(self):
        first = self.run_sample(self.root / 'first', batch_size=1)
        second = self.run_sample(self.root / 'second', batch_size=7)
        self.assertEqual([entry['job_id'] for entry in first['selected']],
                         [entry['job_id'] for entry in second['selected']])
        self.assertEqual(first['candidates_evaluated'], second['candidates_evaluated'])

    def test_checksum_detects_transfer_corruption(self):
        output = self.root / 'output'
        manifest = self.run_sample(output)
        path = output / manifest['selected'][0]['filename']
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
            sample.verify_export(output)

    def test_source_comparison_detects_changed_raw_text(self):
        output = self.root / 'output'
        manifest = self.run_sample(output)
        entry = manifest['selected'][0]
        path = self.source / entry['raw_position']['part']
        table = pq.read_table(path)
        rows = table.to_pylist()
        rows[entry['raw_position']['row']]['description'] += ' changed'
        pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), path)
        with self.assertRaisesRegex(ValueError, 'differs from source'):
            sample.verify_export(output, self.source)

    def test_insufficient_english_remains_incomplete(self):
        output = self.root / 'output'
        with self.assertRaisesRegex(ValueError, 'Only 8 English descriptions'):
            self.run_sample(output, count=10)
        self.assertEqual(json.loads((output / 'manifest.json').read_text())['status'], 'incomplete')
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            sample.verify_export(output)

    def test_missing_duplicate_and_non_hk_metadata_fail(self):
        ids = [self.raw[2]['job_id']]
        with self.assertRaisesRegex(ValueError, 'lack matching'):
            sample.lookup_postings(self.source, ['999999'])
        path = self.source / 'postings_cosmos/part-000.parquet'
        pq.write_table(pa.Table.from_pylist(self.postings + [self.postings[2]]), path)
        with self.assertRaisesRegex(ValueError, 'Duplicate structured'):
            sample.lookup_postings(self.source, ids)
        self.postings[2]['country'] = 'China'
        pq.write_table(pa.Table.from_pylist(self.postings), path)
        with self.assertRaisesRegex(ValueError, 'Non-Hong Kong'):
            sample.lookup_postings(self.source, ids)

    def test_existing_output_and_source_output_are_refused(self):
        output = self.root / 'output'
        self.run_sample(output)
        with self.assertRaises(FileExistsError):
            self.run_sample(output)
        with self.assertRaisesRegex(ValueError, 'read-only source'):
            self.run_sample(self.source / 'new-output')


if __name__ == '__main__':
    unittest.main()
