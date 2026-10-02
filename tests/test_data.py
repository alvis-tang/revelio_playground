"""Optional integration tests using real pandas, Parquet, and Stata serialization."""
import json
from pathlib import Path
import tempfile
import unittest
from test_klc import FakeConnection, data

try:
    import pandas as pd
    import pyarrow
except ImportError:
    pd = None


@unittest.skipIf(pd is None, 'Install requirements-klc.txt for serialization tests')
class DataTests(unittest.TestCase):
    def test_parquet_stata_roundtrip_and_size_limit(self):
        class Connection(FakeConnection):
            def raw_sql(self, *args, **kwargs):
                yield pd.DataFrame({'rcid': pd.Series([123, None], dtype='Int64'), 'country': pd.Series(['US', None], dtype='string')})
                yield pd.DataFrame({'rcid': pd.Series([124], dtype='Int64'), 'country': pd.Series(['US'], dtype='string')})
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / 'extract', Path(folder) / 'sample.dta'
            data.extract(Connection(), 'SELECT 1', {}, source)
            with self.assertRaisesRegex(ValueError, 'max-rows'):
                data.export_stata(source, target, 2)
            data.export_stata(source, target, 3)
            frame = pd.read_stata(target)
            self.assertEqual(len(frame), 3)
            self.assertEqual(frame.country.tolist(), ['US', '', 'US'])
            self.assertTrue(pd.isna(frame.rcid.iloc[1]))
            with self.assertRaisesRegex(ValueError, 'already exists'):
                data.export_stata(source, target, 3)

    def test_incomplete_and_large_identifier_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            (source / 'manifest.json').write_text(json.dumps({'status': 'incomplete'}))
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                data.export_stata(source, source / 'test.dta', 10)
            (source / 'manifest.json').write_text(json.dumps({'status': 'complete'}))
            pd.DataFrame({'id': [2**53 + 1]}).to_parquet(source / 'part.parquet')
            with self.assertRaisesRegex(ValueError, 'precision'):
                data.export_stata(source, source / 'test.dta', 10)
