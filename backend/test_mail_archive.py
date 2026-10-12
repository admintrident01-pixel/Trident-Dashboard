import copy, unittest
import reminders, test_accounts
from core import Problem
class MailArchiveTests(unittest.TestCase):
    def setUp(self):
        self.state={'mailOutbox':{'one':{'id':'one','to':'staff@example.nz','subject':'Time sheet due','body':'Reminder text','status':'sent','kind':'timesheet','createdAt':'2026-10-12T00:00:00Z'}}}
    def test_archive_and_restore_preserve_email_and_delivery_state(self):
        original=copy.deepcopy(self.state)
        archived=reminders.archive_mail(self.state,{'id':'one','archived':True},'admin@example.nz')
        self.assertEqual(self.state,original)
        row=archived['mailOutbox']['one']
        self.assertTrue(row['archived']);self.assertEqual(row['archivedBy'],'admin@example.nz')
        for key in ['body','to','subject','status','createdAt']:self.assertEqual(row[key],original['mailOutbox']['one'][key])
        restored=reminders.archive_mail(archived,{'id':'one','archived':False},'admin@example.nz')
        self.assertFalse(restored['mailOutbox']['one']['archived']);self.assertEqual(restored['mailOutbox']['one']['archivedAt'],'')
    def test_validation(self):
        for data in [None,{'id':'one','archived':'true'},{'id':'missing','archived':True}]:
            with self.assertRaises(Problem):reminders.archive_mail(self.state,data,'admin@example.nz')
    def test_api_permissions_conflicts_and_persistence(self):
        api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(copy.deepcopy(self.state))
        body={'id':'one','archived':True}
        self.assertEqual(api.call('/api/mail-archive','POST',body,token='tech')[0],403)
        self.assertEqual(api.call('/api/mail-archive','POST',body,match=False)[0],409)
        self.assertEqual(api.call('/api/mail-archive','POST',body)[0],200)
        self.assertTrue(api.call('/api/mail-outbox')[1]['messages'][0]['archived'])
        self.assertEqual(api.call('/api/mail-archive','POST',{'id':'one','archived':False})[0],200)
        self.assertFalse(api.call('/api/mail-outbox')[1]['messages'][0]['archived'])
