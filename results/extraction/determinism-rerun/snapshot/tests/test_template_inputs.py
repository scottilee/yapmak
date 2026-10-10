"""Offline contracts for template input fixtures and their code adapters."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from extraction_checks import source_adapter
from run_synthetic_cases import load_cases


class InputTests(unittest.TestCase):
    def test_extractor_templates_and_types(self):
        fixture = json.loads((ROOT / 'tests/fixtures/extraction_schemas.json').read_text())
        for schema in fixture['schemas'].values():
            for field in schema:
                self.assertGreaterEqual(field['min_confidence'], 0)
                self.assertLessEqual(field['min_confidence'], 1)
                for name in ('speech', 'conversation.last-10', 'type_preamble', 'variables_list'):
                    self.assertIn('{{extractor.' + name + '}}', field['extraction_prompt'])
        self.assertTrue(all(f['type'] != 'date' for f in fixture['schemas']['date']))
        self.assertEqual(fixture['schemas']['identity_digits'][1]['validation_pattern'], '^[0-9]{4}$')

    def test_correction_with_missing_data_cannot_reconfirm_old_amount(self):
        variables = dict(consent_action='correct', proposed_amount=420, proposal_revision=1, confirmed_revision=1, consent_valid='true', proposal_complete='true')
        scope = dict(vars=variables)
        exec(source_adapter('consent'), scope)
        self.assertEqual(variables['confirmed_revision'], 0)
        self.assertEqual(variables['proposal_complete'], 'false')
        variables['consent_action'] = 'confirm'
        exec(source_adapter('consent'), scope)
        self.assertEqual(variables['consent_valid'], 'false')
        variables.update(consent_action='correct', corrected_amount=350)
        exec(source_adapter('consent'), scope)
        self.assertEqual(variables['proposed_amount'], 350)
        self.assertEqual(variables['consent_valid'], 'false')
        variables['consent_action'] = 'confirm'
        exec(source_adapter('consent'), scope)
        self.assertEqual(variables['confirmed_revision'], variables['proposal_revision'])

    def test_irrelevant_stale_date_fields_ignored(self):
        variables = dict(now='2026-10-14T11:00', date_kind='numbered', date_day=26, date_month=0, date_year=0, date_keyword='vague', date_weekday='monday')
        exec(source_adapter('date'), dict(vars=variables))
        self.assertEqual(variables['date_resolved'], '2026-10-26')
        self.assertEqual(json.loads(variables['date_expr_json']), dict(day=26))

    def test_synthetic_case_capabilities(self):
        path = ROOT / 'tests/fixtures/synthetic'
        manifest = json.loads((path / 'manifest.json').read_text())
        for row in manifest:
            if row['support'] == 'offline_fault_fixture_only':
                with self.assertRaisesRegex(ValueError, 'fault injection'):
                    load_cases(path / row['file'])
            else:
                cases = load_cases(path / row['file'])
                self.assertEqual(len(cases), 1)
                self.assertEqual(cases[0]['id'], row['case_id'])

    def test_adapters_embed_without_template_delimiters(self):
        for mode in ('date', 'amount', 'identity_date', 'identity_digits', 'consent'):
            source = source_adapter(mode)
            self.assertNotIn('{' * 2, source)
            self.assertNotIn('}' * 2, source)
            compile('vars = dict()\n' + source, '<adapter>', 'exec')


if __name__ == '__main__':
    unittest.main()
