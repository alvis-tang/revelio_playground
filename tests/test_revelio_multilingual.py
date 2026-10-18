"""Test language coverage, freezing, request isolation, and verbatim evidence."""
import copy
from contextlib import nullcontext
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import revelio_llm as llm
import revelio_multilingual as multi

TEXTS = {
    'English': 'We are looking for an experienced software engineer to develop reliable services. Candidates must demonstrate strong communication skills and experience working with Python and SQL. A bachelor degree in computer science is required.',
    'Chinese': '岗位职责：负责公司软件系统开发与维护，参与需求分析和技术方案设计，保证项目按时完成。任职要求：本科及以上学历，计算机相关专业，具有三年以上软件开发工作经验，熟悉数据库设计和系统架构，具备良好的沟通能力和团队合作精神。',
    'Spanish': 'Buscamos un ingeniero de software con experiencia en desarrollo de aplicaciones y gestión de bases de datos. Se requiere un título universitario en informática y capacidad para trabajar en equipo. La persona seleccionada participará en el diseño de soluciones técnicas y la comunicación con nuestros clientes.',
    'French': 'Nous recherchons un ingénieur logiciel expérimenté pour développer des applications et maintenir nos systèmes informatiques. Le candidat doit posséder un diplôme universitaire en informatique et de solides compétences en communication. Une expérience dans la gestion des bases de données est nécessaire.',
    'Arabic': 'نبحث عن مهندس برمجيات يتمتع بخبرة في تطوير التطبيقات وإدارة قواعد البيانات. يجب أن يكون المتقدم حاصلاً على شهادة جامعية في علوم الحاسوب وأن يمتلك مهارات تواصل جيدة وقدرة على العمل ضمن فريق. تشمل المسؤوليات تصميم الأنظمة وتحليل متطلبات العملاء وتقديم الدعم الفني المستمر.',
    'Japanese': '仕事内容：ソフトウェアの開発と保守を担当していただきます。応募資格：情報科学の学士号を取得していること。データベースの設計と管理に関する経験が必要です。チームで協力しながらプロジェクトを進める能力と高いコミュニケーション能力を求めています。',
    'Korean': '업무 내용은 소프트웨어 개발과 시스템 유지보수입니다. 지원자는 컴퓨터 공학 학사 학위를 보유하고 데이터베이스 설계 및 관리 경험이 있어야 합니다. 팀원들과 협력하여 프로젝트를 진행하고 고객의 요구사항을 분석할 수 있는 능력이 필요합니다. 원활한 의사소통 능력을 갖춘 분을 찾습니다.',
}
try:
    import lingua
    import opencc
    HAS_LANGUAGES = True
except ImportError:
    HAS_LANGUAGES = False
try:
    from kellogg_llm_batch.core import prepare_run, audit_run
except ImportError:
    prepare_run = None


def classified_records():
    rows, classifications = [], {}
    for group in multi.GROUPS:
        for index in range(3 if group != 'Chinese' else 2):
            job_id = f'000{len(rows):02d}'
            text = TEXTS.get(group, TEXTS['Chinese'] + '\n\n' + TEXTS['English'])
            rows.append({'job_id': job_id, 'title_raw': 'Résumé 第二行', 'description': text + f'\n{index}',
                         'country': 'LOCAL_COUNTRY_ONLY', 'company': 'LOCAL_COMPANY_ONLY'})
            classifications[job_id] = {'group': group, 'languages': group.split('/'),
                                       'chinese_script': {'script': ('simplified' if index == 0 else 'traditional')}
                                       if group == 'Chinese' else None}
    return rows, classifications


@unittest.skipUnless(HAS_LANGUAGES, 'Install pinned Lingua and OpenCC for classification checks')
class LanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector, cls.maps = multi.detector(), multi.script_maps()

    def test_all_seven_languages_and_both_chinese_scripts(self):
        for name, text in TEXTS.items():
            with self.subTest(name=name):
                actual = multi.classify(text, self.detector, self.maps)
                self.assertEqual(actual['group'], name, actual)
        traditional = opencc.OpenCC('s2t').convert(TEXTS['Chinese'])
        self.assertEqual(multi.classify(traditional, self.detector, self.maps)['chinese_script']['script'], 'traditional')
        self.assertEqual(multi.classify(TEXTS['Chinese'], self.detector, self.maps)['chinese_script']['script'], 'simplified')

    def test_substantial_mixed_passages_and_borrowed_term(self):
        actual = multi.classify(TEXTS['Chinese'] + '\n\n' + TEXTS['English'], self.detector, self.maps)
        self.assertEqual(actual['group'], 'Chinese/English', actual)
        borrowed = multi.classify(TEXTS['Chinese'] + ' Python SQL', self.detector, self.maps)
        self.assertNotEqual(borrowed['group'], 'Chinese/English')

    def test_ambiguous_text_and_chinese_scripts_excluded(self):
        self.assertIsNone(multi.classify('SQL Python', self.detector, self.maps)['group'])
        self.assertIsNone(multi.chinese_script('中文', self.maps)['script'])
        self.assertIsNone(multi.chinese_script('软件軟體', self.maps)['script'])
        self.assertIsNone(multi.classify(TEXTS['Chinese'] + opencc.OpenCC('s2t').convert(TEXTS['Chinese']),
                                       self.detector, self.maps)['group'])


class CoverageTests(unittest.TestCase):
    def test_seeded_selection_unique_ids_and_complete_coverage(self):
        rows, classifications = classified_records()
        selected, coverage = multi.select(rows, classifications)
        self.assertEqual(len({row['job_id'] for row in selected}), 16)
        self.assertTrue(coverage['complete'])
        self.assertEqual(selected, multi.select(list(reversed(rows)), classifications)[0])
        self.assertEqual(coverage['seed'], 42)

    def test_duplicate_ids_and_missing_groups_stop(self):
        rows, classifications = classified_records()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            multi.select(rows + [rows[0]], classifications)
        without = [row for row in rows if classifications[row['job_id']]['group'] != 'Arabic']
        selected, report = multi.select(without, classifications)
        self.assertIn('Arabic', report['missing_groups'])
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(ValueError, 'Missing language coverage'):
            multi.save_project(selected, Path(folder) / 'missing', {}, report)
        traditional = [row for row in rows if classifications[row['job_id']].get('chinese_script') == {'script': 'traditional'}]
        _, report = multi.select([row for row in rows if row not in traditional], classifications)
        self.assertIn('Chinese traditional', report['missing_groups'])

    def test_freeze_unicode_and_tamper_detection(self):
        rows, classifications = classified_records()
        selected, coverage = multi.select(rows, classifications)
        with tempfile.TemporaryDirectory() as folder:
            project = multi.save_project(selected, Path(folder) / 'project', {}, coverage)
            actual, _ = multi.validate_frozen(project)
            self.assertEqual([r['description'] for r in actual], [r['description'] for r in selected])
            self.assertTrue(all(isinstance(r['job_id'], str) and r['job_id'].startswith('000') for r in actual))
            self.assertIn('第二行', (project / 'input.jsonl').read_text())
            (project / 'system.txt').write_text('tampered')
            with self.assertRaisesRegex(ValueError, 'Frozen project changed'):
                multi.validate_frozen(project)

    def test_default_llama_configuration_unchanged(self):
        settings = llm.project_config()
        self.assertEqual(settings['providers']['openai_compatible']['model'], 'llama3.1:8b')
        self.assertEqual(settings['providers']['openai_compatible']['options'], {'temperature': 0})
        self.assertEqual(settings['task']['max_output_tokens'], 1000)
        settings = multi.config()
        self.assertEqual(settings['providers']['openai_compatible']['model'], 'qwen3:8b')
        self.assertEqual(settings['providers']['openai_compatible']['options'], {'temperature': 0.7, 'reasoning_effort': 'none'})
        self.assertEqual(settings['task']['rows_per_request'], 1)
        self.assertEqual(settings['task']['max_output_tokens'], 3000)

    def test_run_multilingual_rejects_partial_or_wrong_model(self):
        with patch.dict('os.environ', {'SLURM_JOB_ID': 'test'}):
            for options in ({'sample_size': 4}, {'model': 'llama3.1:8b'}, {'seed': 1}):
                with self.assertRaisesRegex(ValueError, 'all 16 frozen records'):
                    llm.run('/missing', profile='multilingual', **options)

    @unittest.skipUnless(HAS_LANGUAGES, 'Install language dependencies for extraction checks')
    def test_candidate_cap_date_strings_and_missing_coverage_report(self):
        import pandas as pd
        import job_descriptions_smoke
        calls = []

        def query(conn, sql, params):
            calls.append((sql, params))
            if sql.startswith('SELECT post_date'):
                return pd.DataFrame({'post_date': ['2026-09-06']})
            if sql.startswith('EXPLAIN'):
                return pd.DataFrame({'plan': [{'Index Name': 'cosmos_post_date', 'Index Cond': 'date bounds'}]})
            return pd.DataFrame([{'job_id': f'000{index}', 'title_raw': 'Engineer',
                                  'description': TEXTS['English'] + f'\n{index}'}
                                 for index in range(params['limit'])])

        classification = {'group': 'English', 'languages': ['English'], 'chinese_script': None}
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(job_descriptions_smoke, 'connection', return_value=nullcontext(object())), \
                patch.object(multi, 'bounded_query', side_effect=query), \
                patch.object(multi, 'detector'), patch.object(multi, 'script_maps'), \
                patch.object(multi, 'classify', return_value=classification):
            project = Path(folder) / 'incomplete'
            with self.assertRaisesRegex(ValueError, 'Missing groups'):
                multi.extract(project, candidate_limit=16)
            report = json.loads((project / 'language_coverage.json').read_text())
            source = json.loads((project / 'source.json').read_text())
            self.assertIn('Arabic', report['missing_groups'])
            self.assertEqual(source['descriptions_retrieved'], 16)
            self.assertEqual(source['statement_timeout_seconds'], 60)
            self.assertFalse((project / 'project.yaml').exists())
            self.assertEqual([params['limit'] for sql, params in calls if sql == multi.CANDIDATE_SQL], [16])
            self.assertIn('post_date >=', multi.CANDIDATE_SQL)
            self.assertIn('country = ANY', multi.CANDIDATE_SQL)

    @unittest.skipIf(prepare_run is None, 'Install batch package for real prepared requests')
    def test_real_qwen_requests_full_coverage_and_no_metadata(self):
        rows, classifications = classified_records()
        rows[0]['description'] = '  \r\n' + rows[0]['description'] + '\r\n  '
        rows[0]['title_raw'] = ' Résumé 第二行 \r\n'
        rows[1]['title_raw'] = 'NA'
        rows[2]['title_raw'] = ''
        selected, coverage = multi.select(rows, classifications)
        with tempfile.TemporaryDirectory() as folder:
            project = multi.save_project(selected, Path(folder) / 'project', {}, coverage)
            from kellogg_llm_batch.data import normalize_value
            run_dir = multi.prepare(project / 'project.yaml')
            self.assertEqual(normalize_value('  text\r\n'), 'text')
            rows, _ = multi.validate_frozen(project)
            self.assertEqual(multi.validate_requests(run_dir, rows)['requests'], 16)
            for path in (run_dir / 'api_requests').glob('*.jsonl'):
                text = path.read_text()
                self.assertNotIn('LOCAL_COMPANY_ONLY', text)
                self.assertNotIn('LOCAL_COUNTRY_ONLY', text)
                requests = [json.loads(line) for line in text.splitlines()]
                requests[0]['body']['reasoning_effort'] = 'high'
                path.write_text('\n'.join(json.dumps(row) for row in requests))
                with self.assertRaisesRegex(ValueError, 'Prepared request'):
                    multi.validate_requests(run_dir, rows)
                break


class EvidenceTests(unittest.TestCase):
    def test_verbatim_unicode_quotes_missing_and_fabricated_evidence(self):
        source = {'description': '要求：本科及以上学历。熟悉 Python，掌握 SQL。'}
        result = {'detected_languages': ['Chinese'], 'reading_status': 'readable', 'reading_note': '',
                  'skills': [{'english': 'Python', 'quote': '熟悉 Python'}],
                  'education_requirements': [{'english': 'Bachelor degree or higher', 'quote': '本科及以上学历'}]}
        self.assertEqual(multi.evidence_errors(result, source, ['Chinese']), [])
        for quote in ('Bachelor degree', '', '本科及以上學歷', ' 熟悉 Python', 'SQL expert'):
            bad = copy.deepcopy(result)
            bad['skills'][0]['quote'] = quote
            self.assertTrue(multi.evidence_errors(bad, source, ['Chinese']), quote)
        bad = copy.deepcopy(result)
        del bad['education_requirements'][0]['quote']
        self.assertTrue(multi.evidence_errors(bad, source, ['Chinese']))

    def test_absent_requirements_distinct_from_unreadable_text(self):
        result = {'detected_languages': ['English'], 'reading_status': 'readable', 'reading_note': '',
                  'skills': [], 'education_requirements': []}
        self.assertEqual(multi.evidence_errors(result, {'description': 'Welcome'}, ['English']), [])
        result['reading_status'] = 'unreadable'
        self.assertTrue(multi.evidence_errors(result, {'description': 'Welcome'}, ['English']))
        result['reading_note'] = 'Text could not be read.'
        self.assertEqual(multi.evidence_errors(result, {'description': 'Welcome'}, ['English']), [])
        result['skills'] = [{'english': 'Welcome', 'quote': 'Welcome'}]
        self.assertTrue(multi.evidence_errors(result, {'description': 'Welcome'}, ['English']))
        self.assertTrue(multi.evidence_errors(result, {'description': 'Welcome'}, ['French']))

    @unittest.skipIf(prepare_run is None, 'Install batch package and pyarrow for evidence audit')
    def test_evidence_audit_excludes_bad_record_and_requires_exact_coverage(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        rows, classifications = classified_records()
        selected, coverage = multi.select(rows, classifications)
        output = [{'record_id': row['job_id'], 'detected_languages': classifications[row['job_id']]['languages'],
                   'reading_status': 'readable', 'reading_note': '',
                   'skills': [{'english': 'Requirement', 'quote': row['description'][:20]}],
                   'education_requirements': []} for row in selected]
        with tempfile.TemporaryDirectory() as folder:
            run_dir = Path(folder)
            (run_dir / 'outputs').mkdir()
            (run_dir / 'run_reports').mkdir()
            path = run_dir / 'outputs/results.parquet'
            pq.write_table(pa.Table.from_pylist(output), path)
            self.assertTrue(multi.audit_evidence(run_dir, selected, coverage)['complete'])
            output[0]['skills'][0]['quote'] = 'Fabricated quote'
            pq.write_table(pa.Table.from_pylist(output), path)
            with self.assertRaisesRegex(ValueError, 'Evidence audit failed'):
                multi.audit_evidence(run_dir, selected, coverage)
            self.assertEqual(pq.read_table(path).num_rows, 15)
            failures = (run_dir / 'outputs/failures.jsonl').read_text()
            self.assertIn('invalid_evidence', failures)
            with self.assertRaisesRegex(ValueError, 'Evidence audit failed'):
                multi.audit_evidence(run_dir, selected, coverage)


if __name__ == '__main__':
    unittest.main()
