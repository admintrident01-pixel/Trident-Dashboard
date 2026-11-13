import copy, datetime as dt, unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
import accounts, on_call_roster, reminders, test_accounts
from core import Problem

NZ = ZoneInfo('Pacific/Auckland')
NOW = dt.datetime(2026, 11, 13, 10, 0, tzinfo=NZ)
MONDAY = '2026-11-09'


def second_tech(api):
    api.store.state['users']['tech2@example.nz'] = {
        'email': 'tech2@example.nz', 'name': 'Daryll', 'technician': 'Daryll Anderson',
        'role': 'tech', 'active': True, 'verified': True,
    }


class OnCallRosterTests(unittest.TestCase):
    def setUp(self):
        self.api = test_accounts.AccountsAPI()
        self.api.setUp()
        second_tech(self.api)
        base_verify = self.api.app.verify
        self.api.app.verify = lambda token: 'tech2@example.nz' if token == 'tech2' else base_verify(token)
        self.api.store.state['users'][accounts.FIRST_ADMIN]['verified'] = True
        self.state = self.api.store.state
        self.tech = accounts.users(self.state)['tech@example.nz']
        self.tech2 = accounts.users(self.state)['tech2@example.nz']
        self.admin = accounts.users(self.state)[accounts.FIRST_ADMIN]

    def at(self, when=NOW):
        return patch('on_call_roster.now_auckland', return_value=when)

    def mails(self):
        return list(self.api.store.state.get('mailOutbox', {}).values())

    def test_view_builds_six_week_rotation_and_does_not_mutate_state(self):
        view = on_call_roster.read(self.state, self.admin, now=NOW)
        self.assertNotIn('onCallRoster', self.state)
        self.assertEqual(view['currentWeek'], MONDAY)
        self.assertEqual(view['weekNumber'], 46)
        self.assertEqual(view['headerDates'], 'Mon 9 – Sun 15 November 2026')
        self.assertEqual(len(view['rows']), 6)
        self.assertEqual([row['status'] for row in view['rows']], ['awaiting', 'awaiting', 'scheduled', 'scheduled', 'scheduled', 'scheduled'])
        self.assertEqual(view['rows'][0]['technician'], 'Scott Yearbury')
        self.assertEqual(view['rows'][1]['technician'], 'Daryll Anderson')
        self.assertEqual(view['rows'][0]['deadlineLabel'], 'Sun 8 Nov, 5 pm')
        self.assertEqual(view['rows'][1]['deadlineLabel'], 'Sun 15 Nov, 5 pm')
        self.assertTrue(view['rows'][0]['canHandover'])
        self.assertFalse(view['rows'][0]['canAccept'])

    def test_technician_accepts_own_week_and_everyone_is_emailed(self):
        with self.at():
            self.assertEqual(self.api.call('/api/on-call')[0], 200)
            code, body, _ = self.api.call('/api/on-call', 'POST', {'action': 'accept', 'weekStart': MONDAY}, token='tech')
        self.assertEqual(code, 200, body)
        row = body['rows'][0]
        self.assertEqual(row['status'], 'accepted')
        self.assertTrue(row['canAccept'] is False)
        self.assertEqual(row['acceptedBy'], 'tech@example.nz')
        mails = self.mails()
        self.assertEqual({mail['to'] for mail in mails}, {accounts.FIRST_ADMIN, 'nikita.trident2024@gmail.com', 'tech@example.nz', 'tech2@example.nz'})
        self.assertTrue(all(mail['status'] == 'preview' for mail in mails))
        self.assertTrue(all('Week 46' in mail['subject'] for mail in mails))

    def test_accept_requires_the_assigned_technician(self):
        with self.at():
            self.assertEqual(self.api.call('/api/on-call')[0], 200)
            self.assertEqual(self.api.call('/api/on-call', 'POST', {'action': 'accept', 'weekStart': MONDAY}, token='tech2')[0], 403)
            self.assertEqual(self.api.call('/api/on-call', 'POST', {'action': 'accept', 'weekStart': MONDAY})[0], 403)
        self.assertEqual(on_call_roster.read(self.api.store.state, self.tech2, now=NOW)['rows'][0]['status'], 'awaiting')

    def test_handover_to_another_technician_and_open_pool(self):
        with self.at():
            self.assertEqual(self.api.call('/api/on-call')[0], 200)
            code, body, _ = self.api.call('/api/on-call', 'POST', {'action': 'handover', 'weekStart': MONDAY, 'technician': 'Daryll Anderson'}, token='tech')
        self.assertEqual(code, 200, body)
        record = self.api.store.state['onCallRoster']['weeks'][MONDAY]
        self.assertEqual(record['technician'], 'Daryll Anderson')
        self.assertEqual(record['status'], 'awaiting')
        self.assertIn('handed Week 46 to Daryll Anderson', next(mail['body'] for mail in self.mails() if mail['to'] == 'tech2@example.nz'))
        with self.at():
            self.assertEqual(self.api.call('/api/on-call', 'POST', {'action': 'release', 'weekStart': MONDAY}, token='tech2')[0], 200)
        record = self.api.store.state['onCallRoster']['weeks'][MONDAY]
        self.assertEqual(record['status'], 'open')
        self.assertEqual(record['technician'], '')
        self.assertTrue(any('open pool' in mail['body'] for mail in self.mails()))

    def test_release_then_first_grab_wins(self):
        with self.at():
            self.assertEqual(self.api.call('/api/on-call')[0], 200)
            self.assertEqual(self.api.call('/api/on-call', 'POST', {'action': 'release', 'weekStart': MONDAY}, token='tech')[0], 200)
            first = self.api.call('/api/on-call', 'POST', {'action': 'grab', 'weekStart': MONDAY}, token='tech2')
            second = self.api.call('/api/on-call', 'POST', {'action': 'grab', 'weekStart': MONDAY}, token='tech')
        self.assertEqual(first[0], 200, first[1])
        self.assertEqual(first[1]['rows'][0]['technician'], 'Daryll Anderson')
        self.assertEqual(first[1]['rows'][0]['status'], 'accepted')
        self.assertEqual(second[0], 409)
        self.assertEqual(self.api.store.state['onCallRoster']['weeks'][MONDAY]['technician'], 'Daryll Anderson')

    def test_order_is_admin_only_and_preserves_accepted_week(self):
        with self.at():
            self.assertEqual(self.api.call('/api/on-call')[0], 200)
            self.assertEqual(self.api.call('/api/on-call', 'POST', {'action': 'accept', 'weekStart': MONDAY}, token='tech')[0], 200)
            order = ['Daryll Anderson', 'Scott Yearbury', 'Bala Ganesh Venkatesan', 'Andrew Thomas', 'Rick Leef', 'Allan Burney', 'Joby Shearing', 'Jackie Gough']
            self.assertEqual(self.api.call('/api/on-call', 'POST', {'action': 'order', 'order': order}, token='tech')[0], 403)
            code, body, _ = self.api.call('/api/on-call', 'POST', {'action': 'order', 'order': order})
        self.assertEqual(code, 200, body)
        self.assertEqual(body['order'][0], 'Daryll Anderson')
        current = self.api.store.state['onCallRoster']['weeks'][MONDAY]
        self.assertEqual(current['technician'], 'Scott Yearbury')
        self.assertEqual(current['status'], 'accepted')
        self.assertEqual(self.api.store.state['onCallRoster']['weeks']['2026-11-16']['technician'], 'Scott Yearbury')
        self.assertTrue(any('rotation order' in mail['subject'].lower() for mail in self.mails()))

    def test_future_scheduled_week_cannot_be_accepted_early(self):
        with self.at():
            self.assertEqual(self.api.call('/api/on-call')[0], 200)
            code, body, _ = self.api.call('/api/on-call', 'POST', {'action': 'accept', 'weekStart': '2026-11-23'}, token='admin')
        self.assertEqual(code, 409, body)
        self.assertEqual(self.api.store.state['onCallRoster']['weeks']['2026-11-23']['status'], 'scheduled')

    def test_acceptance_deadline_opens_next_week_to_the_pool(self):
        sunday = dt.datetime(2026, 11, 15, 18, 0, tzinfo=NZ)
        view = on_call_roster.read(self.state, self.admin, now=sunday)
        self.assertEqual(view['rows'][1]['status'], 'open')
        self.assertEqual(view['rows'][1]['technician'], '')
        self.assertTrue(view['rows'][1]['canGrab'])
        with self.at(sunday):
            self.assertEqual(self.api.call('/api/on-call')[0], 200)
            code, body, _ = self.api.call('/api/on-call', 'POST', {'action': 'grab', 'weekStart': '2026-11-16'}, token='tech2')
        self.assertEqual(code, 200, body)
        self.assertEqual(body['rows'][1]['technician'], 'Daryll Anderson')
        self.assertTrue(any('open to all technicians' in mail['body'] for mail in self.mails()))

    def test_admin_can_assign_an_open_week(self):
        with self.at():
            self.assertEqual(self.api.call('/api/on-call')[0], 200)
            self.assertEqual(self.api.call('/api/on-call', 'POST', {'action': 'release', 'weekStart': MONDAY}, token='tech')[0], 200)
            view = on_call_roster.read(self.api.store.state, self.admin, now=NOW)
            self.assertTrue(view['rows'][0]['canHandover'])
            code, body, _ = self.api.call('/api/on-call', 'POST', {'action': 'handover', 'weekStart': MONDAY, 'technician': 'Daryll Anderson'})
        self.assertEqual(code, 200, body)
        self.assertEqual(body['rows'][0]['technician'], 'Daryll Anderson')
        self.assertEqual(body['rows'][0]['status'], 'awaiting')

    def test_week_boundary_is_auckland_monday_midnight(self):
        before = dt.datetime(2026, 11, 15, 23, 59, tzinfo=NZ)
        after = dt.datetime(2026, 11, 16, 0, 0, tzinfo=NZ)
        self.assertEqual(on_call_roster.read(self.state, self.admin, now=before)['currentWeek'], '2026-11-09')
        self.assertEqual(on_call_roster.read(self.state, self.admin, now=after)['currentWeek'], '2026-11-16')

    def test_approved_leave_blocks_handover_and_grab(self):
        self.state['leaveRequests'] = {'leave-1': {'id': 'leave-1', 'technician': 'Daryll Anderson', 'status': 'Approved', 'dates': ['2026-11-09', '2026-11-10']}}
        with self.assertRaisesRegex(Problem, 'approved leave'):
            on_call_roster.action(self.state, {'action': 'handover', 'weekStart': MONDAY, 'technician': 'Daryll Anderson'}, self.admin, now=NOW)
        with self.at():
            self.assertEqual(self.api.call('/api/on-call')[0], 200)
            self.assertEqual(self.api.call('/api/on-call', 'POST', {'action': 'release', 'weekStart': MONDAY}, token='tech')[0], 200)
            code, body, _ = self.api.call('/api/on-call', 'POST', {'action': 'grab', 'weekStart': MONDAY}, token='tech2')
        self.assertEqual(code, 409, body)

    def test_rollover_queues_once_and_change_keys_are_deduplicated(self):
        seeded = on_call_roster.initialise(self.state, now=NOW)
        result, count = reminders.due_reminders(seeded, NOW)
        self.assertGreaterEqual(count, 2)
        subjects = [mail['subject'] for mail in result['mailOutbox'].values()]
        self.assertTrue(any('Accept your on-call week' in subject for subject in subjects))
        again, count2 = reminders.due_reminders(result, NOW)
        self.assertEqual(count2, 0)
        self.assertEqual(len(again['mailOutbox']), len(result['mailOutbox']))

    def test_repeated_acceptance_is_rejected_without_duplicate_mail(self):
        with self.at():
            self.assertEqual(self.api.call('/api/on-call')[0], 200)
            self.assertEqual(self.api.call('/api/on-call', 'POST', {'action': 'accept', 'weekStart': MONDAY}, token='tech')[0], 200)
            before = len(self.mails())
            self.assertEqual(self.api.call('/api/on-call', 'POST', {'action': 'accept', 'weekStart': MONDAY}, token='tech')[0], 409)
        self.assertEqual(len(self.mails()), before)

    def test_resend_only_sends_to_the_assigned_technician(self):
        with self.at():
            self.assertEqual(self.api.call('/api/on-call')[0], 200)
            before = len(self.mails())
            code, body, _ = self.api.call('/api/on-call', 'POST', {'action': 'resend', 'weekStart': MONDAY})
        self.assertEqual(code, 200, body)
        new = self.mails()[before:]
        self.assertEqual([mail['to'] for mail in new], ['tech@example.nz'])
        self.assertIn('Sun 8 Nov, 5 pm', new[0]['body'])

    def test_unrelated_state_is_preserved(self):
        self.state['quotes'] = {'a': 1}
        self.state['stock'] = {'b': 2}
        result = on_call_roster.action(self.state, {'action': 'accept', 'weekStart': MONDAY}, self.tech, now=NOW)
        self.assertEqual(result['quotes'], {'a': 1})
        self.assertEqual(result['stock'], {'b': 2})
        self.assertNotIn('onCallRoster', self.state)


if __name__ == '__main__':
    unittest.main()
