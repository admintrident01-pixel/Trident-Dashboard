import copy, unittest
from unittest.mock import patch
import reminders, accounts, test_accounts
from core import Problem

class LeaveNotifications(unittest.TestCase):
 def setUp(self):
  self.api=test_accounts.AccountsAPI();self.api.setUp()
  self.state=self.api.store.state
  self.state['users'][accounts.FIRST_ADMIN]['verified']=True
  self.state['reminderSettings']={'leaveRecipients':[accounts.FIRST_ADMIN]}
  self.request={'technician':'Scott Yearbury','leaveType':'Other','other':'Personal leave','startDate':'2026-11-02','endDate':'2026-11-03','hoursPerDay':8,'reason':'Private request detail'}
 def submit(self,token='tech'):
  status,body,_=self.api.call('/api/leave','POST',self.request,token=token)
  self.assertEqual(status,200,body);return body['request']
 def mails(self):return list(self.api.store.state.get('mailOutbox',{}).values())
 def test_submission_selected_admin_and_technician_preview_no_private_reason(self):
  with patch('smtplib.SMTP') as smtp:
   entry=self.submit();smtp.assert_not_called()
  mails=self.mails();self.assertEqual(len(mails),2)
  self.assertEqual({m['to'] for m in mails},{accounts.FIRST_ADMIN,'tech@example.nz'})
  self.assertTrue(all(m['status']=='preview' for m in mails))
  self.assertTrue(all(self.request['reason'] not in m['body'] for m in mails))
  self.assertIn('not approved yet',next(m['body'] for m in mails if m['to']=='tech@example.nz'))
  self.assertEqual(self.api.store.state['leaveRequests'][entry['id']]['status'],'Pending')
 def test_admin_submits_on_behalf_receipt_goes_to_technician(self):
  self.state['reminderSettings']['leaveRecipients']=[];self.submit('admin')
  self.assertEqual([m['to'] for m in self.mails()],['tech@example.nz'])
 def test_approval_and_rejection_reason_and_retry(self):
  for status in ('Approved','Declined'):
   with self.subTest(status=status):
    self.setUp();entry=self.submit();before=len(self.mails())
    decision={'id':entry['id'],'revision':entry['revision'],'status':status,'decisionNotes':'Coverage unavailable' if status=='Declined' else 'Enjoy your leave'}
    code,body,_=self.api.call('/api/leave-decision','POST',decision);self.assertEqual(code,200,body)
    self.assertEqual(len(self.mails()),before+1);mail=self.mails()[-1]
    self.assertEqual(mail['to'],'tech@example.nz');self.assertIn(decision['decisionNotes'],mail['body'])
    if status=='Declined':self.assertIn('Reason for rejection:',mail['body'])
    self.assertEqual(self.api.call('/api/leave-decision','POST',decision)[0],409);self.assertEqual(len(self.mails()),before+1)
 def test_rejection_requires_reason_and_permissions(self):
  entry=self.submit();decision={'id':entry['id'],'revision':1,'status':'Declined','decisionNotes':''}
  self.assertEqual(self.api.call('/api/leave-decision','POST',decision)[0],400)
  self.assertEqual(self.api.call('/api/leave-decision','POST',decision,token='tech')[0],403)
  self.assertEqual(len(self.mails()),2)
 def test_selection_validation_legacy_preservation_and_disabled_users(self):
  view=reminders.settings_view(self.state)
  for bad in (['tech@example.nz'],['unknown@example.nz'],None,'bad'):
   with self.assertRaises(Problem):reminders.save_settings(self.state,{**view,'leaveRecipients':bad})
  data={k:v for k,v in view.items() if k!='leaveRecipients'}
  self.assertEqual(reminders.save_settings(self.state,data)['reminderSettings']['leaveRecipients'],[accounts.FIRST_ADMIN])
  self.state['users'][accounts.FIRST_ADMIN]['active']=False
  self.state['users']['tech@example.nz']['verified']=False
  entry={**self.request,'id':'test','revision':1,'totalHours':16}
  reminders.queue_leave_notifications(self.state,entry,True)
  self.assertFalse(self.state.get('mailOutbox'))
 def test_no_selected_admins_by_default_and_idempotent_event(self):
  self.state.pop('reminderSettings');entry={**self.request,'id':'test','revision':1,'totalHours':16}
  reminders.queue_leave_notifications(self.state,entry,True);before=copy.deepcopy(self.state)
  reminders.queue_leave_notifications(self.state,entry,True)
  self.assertEqual(before,self.state);self.assertEqual([m['to'] for m in self.mails()],['tech@example.nz'])
 def test_delivery_failure_does_not_undo_saved_leave(self):
  with patch.object(reminders,'deliver',side_effect=RuntimeError('delivery unavailable')):entry=self.submit()
  self.assertEqual(self.api.store.state['leaveRequests'][entry['id']]['status'],'Pending')
  self.assertTrue(all(m['status']=='queued' for m in self.mails()))
 def test_stale_submission_has_no_mail_or_leave_change(self):
  before=copy.deepcopy(self.state)
  self.assertEqual(self.api.call('/api/leave','POST',self.request,token='tech',match=False)[0],409)
  self.assertEqual(before,self.api.store.state)

if __name__=='__main__':unittest.main()
