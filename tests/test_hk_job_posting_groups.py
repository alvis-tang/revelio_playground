"""Verify packet allocation, safe formatting, pagination, and workbook references."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import hk_job_posting_groups as packets


class AllocationTests(unittest.TestCase):
    def test_repeatable_random_partition_has_exact_overlap_and_coverage(self):
        ids = [str(index) for index in range(300)]
        groups = packets.allocate(ids, 42)
        packets.validate_allocation(groups)
        self.assertEqual(groups, packets.allocate(list(reversed(ids)), 42))
        self.assertNotEqual(groups, packets.allocate(ids, 43))
        self.assertEqual(groups[0][:100], groups[1][:100])
        self.assertEqual(set(groups[0]) & set(groups[1]), set(groups[0][:100]))
        self.assertEqual(set(groups[0]) | set(groups[1]), set(ids))
        self.assertFalse(set(groups[0][100:]) & set(groups[1][100:]))

    def test_reject_wrong_count_duplicate_ids_and_incorrect_overlap(self):
        with self.assertRaises(ValueError):
            packets.allocate(['1'] * 300, 42)
        with self.assertRaises(ValueError):
            packets.allocate([str(i) for i in range(299)], 42)
        groups = packets.allocate([str(i) for i in range(300)], 42)
        groups[1][0], groups[1][1] = groups[1][1], groups[1][0]
        with self.assertRaises(ValueError):
            packets.validate_allocation(groups)


class FormattingTests(unittest.TestCase):
    def test_plain_text_keeps_literal_angles_newlines_and_unicode(self):
        original = 'Salary < 50000 & > 10000\n中文 café 🚀'
        html, text = packets.description_content(original)
        self.assertEqual(text, original)
        self.assertIn('&lt; 50000 &amp; &gt;', html)
        self.assertIn('\n中文 café 🚀', html)

    def test_html_keeps_wording_and_lists_without_active_content(self):
        html, text = packets.description_content(
            '<p onclick="alert(1)">R&amp;D</p><ul><li>中文</li></ul>'
            '<script>secret()</script><style>hide</style>'
            '<a href="https://example.com">Apply</a><img src="remote" alt="Logo">')
        self.assertIn('<p>R&amp;D</p><ul><li>中文</li></ul>', html)
        self.assertIn('<a>Apply</a>Logo', html)
        self.assertEqual(text.strip().replace('\n', ''), 'R&D中文ApplyLogo')
        for unwanted in ('onclick', 'href', 'src', 'secret', 'hide', '<script', '<style'):
            self.assertNotIn(unwanted, html)

    def test_job_header_escapes_fields_and_omits_missing_employer(self):
        record = {'job_id': '123', 'title_raw': '<script>Example</script>',
                  'location_raw': 'Hong Kong', 'description': 'Full description.',
                  'posting': {'company': None}}
        html = packets.packet_html([record])
        self.assertIn('Job ID: 123', html)
        self.assertIn('&lt;script&gt;Example&lt;/script&gt;', html)
        self.assertNotIn('None', html)

    def test_redundant_scraped_html_breaks_do_not_expand_list_spacing(self):
        html, text = packets.description_content(
            'Description:<br><br><p><br><br></p><br>'
            '<p><strong>Your role<br><br></strong></p><br>'
            '<ul><br><li>Analyse data.</li><br><li>Report results.</li><br></ul>')
        self.assertEqual(html, 'Description:<p><strong>Your role</strong></p>'
                         '<ul><li>Analyse data.</li><li>Report results.</li></ul>')
        self.assertIn('Analyse data.', text)
        self.assertIn('Report results.', text)


@unittest.skipUnless(importlib.util.find_spec('openpyxl'), 'Install packet dependencies')
class WorkbookTests(unittest.TestCase):
    def test_identifiers_remain_text_and_page_numbers_match_each_group(self):
        from openpyxl import load_workbook

        groups = [[{'job_id': '001234567890123456789', 'page_number': 1},
                   {'job_id': '200', 'page_number': 4}],
                  [{'job_id': '001234567890123456789', 'page_number': 1},
                   {'job_id': '300', 'page_number': 4}]]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'groups.xlsx'
            packets.write_workbook(path, groups)
            packets.verify_workbook(path, groups)
            workbook = load_workbook(path)
            sheet = workbook['Group 2']
            self.assertEqual(sheet['A2'].value, '001234567890123456789')
            self.assertEqual(sheet.freeze_panes, 'A2')
            sheet['B3'] = 3
            workbook.save(path)
            workbook.close()
            with self.assertRaisesRegex(ValueError, 'page references'):
                packets.verify_workbook(path, groups)


@unittest.skipUnless(os.environ.get('RUN_JOB_PACKET_PDF_TESTS') == '1',
                     'Set RUN_JOB_PACKET_PDF_TESTS=1 with Chromium installed')
class PDFTests(unittest.TestCase):
    def test_multipage_ads_unicode_html_start_pages_and_text_completeness(self):
        from playwright.sync_api import sync_playwright
        from pypdf import PdfReader

        records = [
            {'job_id': '1001', 'title_raw': 'Long analyst role',
             'location_raw': 'Hong Kong', 'posting': {'company': 'Example'},
             'description': '\n\n'.join(
                 f'Paragraph {i}: Analyse data and report full results to colleagues.'
                 for i in range(200))},
            {'job_id': '1002', 'title_raw': 'Engineer 中文',
             'location_raw': '香港', 'posting': {'company': None},
             'description': '<p>Résumé &amp; 中文 responsibilities. 需求部门：内部审计部</p>'
                            '<div>Distinct first line.\nDistinct second line.</div>'
                            '<ul><li>Build reliable systems.</li><li>Support customers.</li></ul>'},
            {'job_id': '1003', 'title_raw': 'Short role',
             'location_raw': 'Hong Kong', 'posting': {'company': 'Example'},
             'description': 'Final job. Complete description ends here.'},
        ]
        ids = [r['job_id'] for r in records]
        by_id = {r['job_id']: r for r in records}
        with tempfile.TemporaryDirectory() as directory, sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(java_script_enabled=False)
                page.route('**/*', lambda route: route.abort())
                path = Path(directory) / 'test.pdf'
                packets.render_packet(page, records, path)
                starts, page_count = packets.inspect_pdf(path, ids, by_id)
                self.assertEqual(starts[0]['page_number'], 1)
                self.assertGreater(starts[1]['page_number'], 2)
                self.assertEqual(starts[2]['page_number'], starts[1]['page_number'] + 1)
                self.assertEqual(page_count, starts[2]['page_number'])
                reader = PdfReader(path)
                html_page = reader.pages[starts[1]['page_number'] - 1].extract_text()
                self.assertRegex(html_page, r'Distinct first line\.\s*\nDistinct second line\.')
                for number, pdf_page in enumerate(reader.pages, 1):
                    self.assertRegex(pdf_page.extract_text(),
                                     rf'Page\s+{number}\s+of\s+{page_count}')
                wrong_records = {**by_id, '1003': {**by_id['1003'],
                                                   'description': 'MISSING WORDING'}}
                with self.assertRaisesRegex(ValueError, 'Incomplete PDF description'):
                    packets.inspect_pdf(path, ids, wrong_records)
                with self.assertRaisesRegex(ValueError, 'job order'):
                    packets.inspect_pdf(path, list(reversed(ids)), by_id)
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
