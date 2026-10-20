import copy
import datetime as dt
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import reminders
from core import Problem
import test_accounts

NZ = ZoneInfo('Pacific/Auckland')


class PreviousWeekReminders(unittest.TestCase):
    def setUp(self):
        self.state = {
            'users': {'tech@example.nz': {'email': 'tech@example.nz', 'name': 'Technician',
                      'technician': 'Technician', 'role': 'tech', 'active': True, 'verified': True}},
            'vehicles': [], 'timesheets': {}, 'quotes': {'preserve': 1},
            'reminderSettings': {**reminders.DEFAULTS, 'timesheetWeekday': 0,
                'timesheetTime': '17:00', 'timesheetLeadHours': 24, 'timesheetRepeatHours': 24,
                'automaticTimesheets': True, 'timesheetRecipients': ['tech@example.nz']}}

    def time(self, value):
        return dt.datetime.fromisoformat(value).replace(tzinfo=NZ)

    def tick(self, value):
        before = copy.deepcopy(self.state)
        result, count = reminders.due_reminders(self.state, self.time(value))
        self.assertEqual(before, self.state, 'Calculating reminders must not mutate input')
        self.state = result
        return count

    def sheets(self, value):
        return [r for r in reminders.dashboard(self.state, self.time(value)) if r['kind'] == 'timesheet']

    def test_only_previous_completed_week_and_deadline_in_following_week(self):
        rows = self.sheets('2026-10-21T12:00')
        self.assertEqual([r['weekStart'] for r in rows], ['2026-10-12'])
        self.assertEqual(rows[0]['due'], '2026-10-19T17:00:00+13:00')
        self.assertEqual(rows[0]['firstReminderAt'], '2026-10-19T00:00:00+13:00')

    def test_sunday_lead_waits_until_monday_midnight(self):
        self.state['timesheets']['older'] = {'technician': 'Technician', 'weekStart': '2026-10-05'}
        self.assertEqual(self.tick('2026-10-18T17:00'), 0)
        self.assertEqual(self.tick('2026-10-18T23:59:59'), 0)
        self.assertEqual(self.tick('2026-10-19T00:00'), 1)
        mail = next(iter(self.state['mailOutbox'].values()))
        self.assertEqual(mail['context']['weekStart'], '2026-10-12')

    def test_first_plus_three_followups_only_and_no_fifth(self):
        for day in range(19, 23):
            self.assertEqual(self.tick(f'2026-10-{day}T00:00'), 1)
            self.assertEqual(self.tick(f'2026-10-{day}T00:05'), 0)
        self.assertEqual(self.tick('2026-10-23T00:00'), 0)
        self.assertEqual(self.tick('2026-10-25T23:59'), 0)
        self.assertEqual(len(self.state['mailOutbox']), 4)
        self.assertEqual(self.sheets('2026-10-23T12:00')[0]['nextReminderAt'], None)
        self.assertEqual(self.state['quotes'], {'preserve': 1})

    def test_custom_interval_is_elapsed_hours_not_calendar_days(self):
        self.state['reminderSettings']['timesheetRepeatHours'] = 6
        self.assertEqual(self.tick('2026-10-19T09:00'), 1)
        self.assertEqual(self.tick('2026-10-19T14:59:59'), 0)
        self.assertEqual(self.tick('2026-10-19T15:00'), 1)
        self.assertEqual(self.tick('2026-10-19T21:00'), 1)
        self.assertEqual(self.tick('2026-10-20T03:00'), 1)
        self.assertEqual(self.tick('2026-10-20T09:00'), 0)

    def test_delayed_run_does_not_burst_catch_up_emails(self):
        self.assertEqual(self.tick('2026-10-21T15:30'), 1)
        self.assertEqual(self.tick('2026-10-21T15:35'), 0)
        self.assertEqual(self.tick('2026-10-22T15:29'), 0)
        self.assertEqual(self.tick('2026-10-22T15:30'), 1)

    def test_submission_of_other_week_does_not_stop_correct_week(self):
        self.state['timesheets']['current'] = {'technician': 'Technician', 'weekStart': '2026-10-19'}
        self.assertEqual(self.tick('2026-10-19T09:00'), 1)
        self.state['timesheets']['previous'] = {'technician': 'technician', 'weekStart': '2026-10-12'}
        self.assertEqual(self.tick('2026-10-20T09:00'), 0)
        self.assertEqual(self.sheets('2026-10-20T09:00'), [])

    def test_submission_between_queue_and_delivery_cancels_email(self):
        self.tick('2026-10-19T09:00')
        self.state['timesheets']['saved'] = {'technician': 'Technician', 'weekStart': '2026-10-12'}
        store = test_accounts.MemoryStore(self.state)
        with patch('smtplib.SMTP') as smtp:
            reminders.deliver(store, local=True)
            smtp.assert_not_called()
        mail = next(iter(store.state['mailOutbox'].values()))
        self.assertEqual(mail['status'], 'cancelled')
        self.assertEqual(mail['cancelReason'], 'Time sheet submitted')

    def test_empty_recipients_disabled_inactive_and_unverified(self):
        original = copy.deepcopy(self.state)
        for category in ('no_recipients', 'off', 'inactive', 'unverified'):
            self.state = copy.deepcopy(original)
            if category == 'no_recipients': self.state['reminderSettings']['timesheetRecipients'] = []
            if category == 'off': self.state['reminderSettings']['automaticTimesheets'] = False
            if category == 'inactive': self.state['users']['tech@example.nz']['active'] = False
            if category == 'unverified': self.state['users']['tech@example.nz']['verified'] = False
            self.assertEqual(self.tick('2026-10-19T09:00'), 0, category)

    def test_changing_timing_does_not_reset_limit(self):
        for day in range(19, 23): self.tick(f'2026-10-{day}T09:00')
        self.state['reminderSettings'].update(timesheetTime='12:00', timesheetRepeatHours=1)
        self.assertEqual(self.tick('2026-10-23T09:00'), 0)

    def test_long_interval_finishes_started_cycle_without_reminding_current_week(self):
        self.state['reminderSettings']['timesheetRepeatHours'] = 168
        self.tick('2026-10-19T09:00')
        rows = self.sheets('2026-10-26T09:00')
        self.assertEqual({r['weekStart'] for r in rows}, {'2026-10-12', '2026-10-19'})
        self.assertFalse(any(r['weekStart'] == '2026-10-26' for r in rows))

    def test_new_week_starts_new_cycle_without_resetting_previous_history(self):
        for day in range(19, 23): self.tick(f'2026-10-{day}T09:00')
        self.assertEqual(self.tick('2026-10-26T09:00'), 1)
        self.assertEqual(len(self.state['timesheetReminderCycles']), 2)

    def test_legacy_reminders_count_toward_limit(self):
        row = self.sheets('2026-10-21T12:00')[0]
        self.state['reminderSentKeys'] = {row['id'] + ':legacy:' + str(i): '2026-10-19' for i in range(4)}
        self.assertEqual(self.tick('2026-10-21T12:00'), 0)

    def test_archive_or_mail_pruning_does_not_reset_limit(self):
        for day in range(19, 23): self.tick(f'2026-10-{day}T09:00')
        self.state['mailOutbox'] = {}
        self.assertEqual(self.tick('2026-10-23T09:00'), 0)

    def test_spring_and_autumn_followups_use_24_real_hours(self):
        for before, after, expected_hour in [('2026-04-04T17:00', '2026-04-05T16:00', 16),
                                            ('2026-09-26T17:00', '2026-09-27T18:00', 18)]:
            with self.subTest(before=before):
                self.setUp()
                self.state['reminderSettings'].update(timesheetWeekday=6, timesheetLeadHours=168)
                self.assertEqual(self.tick(before), 1)
                next_at = dt.datetime.fromisoformat(self.sheets(after)[0]['nextReminderAt'])
                self.assertEqual(next_at.hour, expected_hour)
                self.assertEqual(self.tick((self.time(after)-dt.timedelta(minutes=1)).isoformat()), 0)
                self.assertEqual(self.tick(after), 1)

    def test_reassigned_account_does_not_continue_another_technicians_cycle(self):
        self.state['reminderSettings']['timesheetRepeatHours'] = 168
        self.tick('2026-10-19T09:00')
        self.state['users']['tech@example.nz']['technician'] = 'Replacement'
        self.assertEqual([r['weekStart'] for r in self.sheets('2026-10-26T09:00')], ['2026-10-19'])

    def test_settings_interval_validation_and_old_clients_preserve_saved_interval(self):
        self.state['reminderSettings']['timesheetRepeatHours'] = 12
        data = reminders.settings_view(self.state)
        for bad in (0, -1, 169, True, '24', 1.5, None):
            with self.assertRaises(Problem): reminders.save_settings(self.state, {**data, 'timesheetRepeatHours': bad})
        del data['timesheetRepeatHours']
        saved = reminders.save_settings(self.state, data)
        self.assertEqual(saved['reminderSettings']['timesheetRepeatHours'], 12)
        self.assertEqual(saved['quotes'], self.state['quotes'])

    def test_api_interval_roundtrip_requires_admin_and_fresh_revision(self):
        api = test_accounts.AccountsAPI(); api.setUp()
        view = api.call('/api/reminder-settings')[1]
        self.assertEqual(view['timesheetRepeatHours'], 24)
        view['timesheetRepeatHours'] = 12
        self.assertEqual(api.call('/api/reminder-settings', 'POST', view, token='tech')[0], 403)
        self.assertEqual(api.call('/api/reminder-settings', 'POST', view, match=False)[0], 409)
        self.assertEqual(api.call('/api/reminder-settings', 'POST', view)[0], 200)
        self.assertEqual(api.call('/api/reminder-settings')[1]['timesheetRepeatHours'], 12)


if __name__ == '__main__': unittest.main()
