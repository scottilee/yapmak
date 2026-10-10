"""Calendar acceptance, boundary, and embedded-source checks."""
import datetime
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import bankcal as bc

H = ['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01']
BD = [0, 1, 2, 3, 4]
TODAY = '2026-10-14'
CAL = {'next_weekday_means_following_week': True, 'missing_date_parts': 'next_occurrence'}


class CalendarTests(unittest.TestCase):
    def test_public_anchors(self):
        self.assertEqual(bc.parse_now(TODAY + 'T11:00'), (TODAY, '11:00'))
        self.assertEqual(bc.nth_business_day_after(TODAY, 7, H, BD), '2026-10-23')
        self.assertEqual(bc.add_business_days(TODAY, 12, H, BD), '2026-11-02')
        self.assertEqual(bc.last_business_day_of_week(TODAY, H, BD), '2026-10-16')
        self.assertEqual(bc.attempt_date('2026-10-16', 'last_business_day_this_week_or_next', '2026-10-23', H, BD), '2026-10-23')
        self.assertEqual(bc.next_business_day('2026-10-26', H, BD), '2026-10-27')
        self.assertEqual(bc.next_business_day(TODAY, H, BD), TODAY)
        self.assertEqual(bc.next_business_day(TODAY, H, BD, False), '2026-10-15')
        self.assertEqual(bc.resolve_date_expr('2026-10-16', {'weekday': 4, 'relative': 'next'}, CAL), '2026-10-23')

    def test_deadline_semantics_explicit(self):
        self.assertEqual(bc.deadline(TODAY, {'kind': 'nth_business_day', 'n': 7}, H, BD), '2026-10-23')
        for adjustment, expected in [('none', '2026-10-17'), ('following', '2026-10-19'), ('preceding', '2026-10-16')]:
            self.assertEqual(bc.deadline(TODAY, {'kind': 'calendar_days', 'n': 3, 'adjustment': adjustment}, H, BD), expected)
        for basis, expected in [('calendar', '2026-10-31'), ('business', '2026-10-30')]:
            self.assertEqual(bc.deadline(TODAY, {'kind': 'end_of_month', 'basis': basis, 'adjustment': 'none'}, H, BD), expected)
        self.assertIsNone(bc.deadline(TODAY, {'kind': 'calendar_days', 'n': 3}, H, BD))
        self.assertEqual(bc.deadline(TODAY, {'kind': 'fixed_date', 'date': '2026-11-30', 'adjustment': 'none'}, H, BD), '2026-11-30')

    def test_structured_expressions(self):
        pairs = [({'keyword': 'today'}, TODAY), ({'keyword': 'tomorrow'}, '2026-10-15'),
                 ({'keyword': 'vague'}, 'vague'), ({'weekday': 4, 'relative': 'this'}, '2026-10-16'),
                 ({'weekday': 4, 'relative': 'next'}, '2026-10-23'),
                 ({'day': 26, 'month': 10}, '2026-10-26'), ({'day': 6, 'month': 11}, '2026-11-06'),
                 ({'day': 23}, '2026-10-23'), ({'day': 1, 'month': 1}, '2027-01-01'),
                 ({'day': 29, 'month': 2}, '2028-02-29'), ({'day': 13, 'month': 10, 'year': 2026}, '2026-10-13')]
        for expr, expected in pairs:
            self.assertEqual(bc.resolve_date_expr(TODAY, expr, CAL), expected)
        for expr in [{'day': 31, 'month': 2}, {'keyword': 'today', 'day': 23}, {'day': True}, {'weekday': 7}, {}]:
            self.assertIsNone(bc.resolve_date_expr(TODAY, expr, CAL))
        self.assertIsNone(bc.resolve_date_expr(TODAY, {'day': 23}, {}))
        self.assertEqual(bc.resolve_date_expr(TODAY, {'weekday': 4, 'relative': 'next'}, {'next_weekday_means_following_week': False}), '2026-10-16')

    def test_callback(self):
        policy = dict(start='10:00', end='19:00', days='today_or_next_business_day', must_be_after_now=True, holidays=H, business_days=BD)
        # Extractor turns 'tomorrow around eleven' into these structured values.
        day = bc.resolve_date_expr(TODAY, {'keyword': 'tomorrow'}, CAL)
        self.assertTrue(bc.callback_ok(TODAY + 'T11:00', day, '11:00', policy))
        for day, time in [(TODAY, '11:00'), (TODAY, '10:30'), ('2026-10-16', '11:00'), (TODAY, '19:01')]:
            self.assertFalse(bc.callback_ok(TODAY + 'T11:00', day, time, policy))
        self.assertTrue(bc.callback_ok(TODAY + 'T11:00', TODAY, '19:00', policy))
        self.assertTrue(bc.callback_ok(TODAY + 'T09:00', TODAY, '10:00', policy))
        self.assertTrue(bc.callback_ok('2026-10-23T11:00', '2026-10-27', '11:00', policy))

    def test_invalid_and_boundaries(self):
        for day, holidays, weekdays in [(None, H, BD), (TODAY, None, BD), (TODAY, H, []), (TODAY, H, [True]), (TODAY, ['bad'], BD), ('9999-12-31', [], [0])]:
            self.assertIsNone(bc.next_business_day(day, holidays, weekdays))
        self.assertIsNone(bc.nth_business_day_after(TODAY, 10**20, H, BD))
        self.assertIsNone(bc.nth_business_day_after(TODAY, True, H, BD))
        self.assertIsNone(bc.parse_now('garbage'))
        self.assertIsNone(bc.parse_now('2026-10-14T11:00:01'))
        self.assertEqual(bc.next_business_day('2026-12-25', H, BD), '2026-12-28')
        self.assertEqual(bc.next_business_day('2027-01-01', H, BD), '2027-01-04')
        self.assertIsNone(bc.last_business_day_of_week(TODAY, ['2026-10-' + str(x) for x in range(12, 17)], BD))

    def test_against_simple_reference(self):
        for weekdays in ([0, 1, 2, 3, 4], [6], [0, 2, 4, 6]):
            for offset in range(30):
                start = datetime.date(2026, 10, 1) + datetime.timedelta(days=offset)
                for n in (1, 2, 7, 12, 50):
                    d, left = start, n
                    while left:
                        d += datetime.timedelta(days=1)
                        if d.weekday() in weekdays and d.isoformat() not in H:
                            left -= 1
                    self.assertEqual(bc.add_business_days(start.isoformat(), n, H, weekdays), d.isoformat())

    def test_legacy_date_and_normalization_api(self):
        for text, expected in [('today', TODAY), ('tomorrow', '2026-10-15'), ('this friday', '2026-10-16'), ('next friday', '2026-10-23'), ('monday the 26th', '2026-10-26'), ('6 november', '2026-11-06'), ('november 6', '2026-11-06'), ('the thirtieth of october', '2026-10-30'), ('the 23rd', '2026-10-23'), ('23/10', '2026-10-23')]:
            self.assertEqual(bc.resolve_date_expression(text, TODAY, H, BD), dict(status='ok', date=expected))
        for text in ('the week after next', 'next week', 'when my salary comes', 'end of the month'):
            self.assertEqual(bc.resolve_date_expression(text, TODAY, H, BD), dict(status='vague'))
        for text in ('14 March 1988', 'fourteenth of march nineteen eighty-eight', '14/03/1988', '14 3 1988'):
            self.assertEqual(bc.normalize_date_answer(text), '1988-03-14')
        self.assertEqual(bc.normalize_date_answer('03/14/1988', 'mdy'), '1988-03-14')
        self.assertIsNone(bc.normalize_date_answer('14 3 88'))
        for text in ('4471', '44 71', 'four four seven one'):
            self.assertEqual(bc.normalize_digits(text, 4), '4471')
        self.assertIsNone(bc.normalize_digits('447', 4))
        for text, expected in [('420', 420.0), ('637.50', 637.5), ('1,250', 1250.0), ('four hundred and twenty', 420.0), ('two thousand one hundred twenty-five point ten', 2125.1), ('six hundred thirty-seven fifty', 637.5), ('four point zero five', 4.05)]:
            self.assertEqual(bc.parse_amount(text), expected)
        for text in ('nan', 'inf', '-4', '4,20', 'four five', 'twenty thirty', 'first second'):
            self.assertIsNone(bc.parse_amount(text))

    def test_legacy_callback_and_verdicts(self):
        self.assertEqual(bc.callback_slot(TODAY, '11:00', 'tomorrow morning', 'around eleven', '10:00', '19:00', 'today_or_next_business_day', H, BD), dict(status='ok', date='2026-10-15', time='11:00'))
        for expr, clock in [('today', '9am'), ('today', '10:30'), ('friday', '15:00')]:
            self.assertEqual(bc.callback_slot(TODAY, '11:00', expr, clock, '10:00', '19:00', 'today_or_next_business_day', H, BD)['status'], 'outside')
        v = lambda day, status, amount: bc.validate_proposal(TODAY, '2026-11-02', day, status, amount, 126.0, 420.0, H, BD)
        for day, status, amount, verdict in [(TODAY, 'ok', 420, 'ok'), ('2026-10-26', 'ok', None, 'roll_forward'), ('2026-11-06', 'ok', None, 'after_deadline'), (None, 'vague', None, 'vague'), ('2026-10-13', 'ok', None, 'past'), ('2026-10-16', 'ok', 100, 'below_floor'), ('2026-10-16', 'ok', 500, 'above_full'), (TODAY, 'ok', float('nan'), 'unreadable')]:
            self.assertEqual(v(day, status, amount)['verdict'], verdict)
        self.assertEqual(v('2026-10-16', 'ok', None)['amount'], '420.00')
        self.assertEqual(v('2026-10-16', 'ok', 100)['offer_amount'], '126.00')
        self.assertEqual(v('2026-10-26', 'ok', None)['offer_date'], '2026-10-27')

    def test_actual_embedding(self):
        source = pathlib.Path(bc.__file__).read_text()
        self.assertNotIn('{' * 2, source)
        self.assertNotIn('}' * 2, source)
        namespace = {}
        code = "vars = dict()\n" + source + "\nvars['deadline'] = deadline('2026-10-14', dict(kind='nth_business_day', n=7), [], [0,1,2,3,4])\n"
        exec(compile(code, '<setup-code-node>', 'exec'), namespace)
        self.assertEqual(namespace['vars']['deadline'], '2026-10-23')

if __name__ == '__main__':
    unittest.main()
