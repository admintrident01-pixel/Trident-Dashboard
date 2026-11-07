import copy,unittest
import job_imports,test_accounts
from core import Problem
ADMIN={'email':'bala@trice.nz','role':'admin'}
class JobImportMappingTests(unittest.TestCase):
 def test_defaults_read_without_writes_and_save_preserves_all_business_records(self):
  state={'quotes':{'123':{'kept':True}},'appointments':{'a':{'client':'Keep'}},'workbook':'unchanged'};before=copy.deepcopy(state)
  values=job_imports.mapping(state,ADMIN)['mappings'];self.assertEqual(state,before)
  values['email']='notes';saved=job_imports.save_mapping(state,ADMIN,{'mappings':values})
  for key,value in state.items():self.assertEqual(saved[key],value)
  self.assertEqual(saved['jobImportMappingHistory'][0]['before']['email'],'recipientEmail')
  self.assertEqual(saved['jobImportMappingHistory'][0]['actor'],ADMIN['email'])
  self.assertEqual(job_imports.mapping(saved,ADMIN)['mappings']['email'],'notes')
  self.assertEqual(job_imports.save_mapping(saved,ADMIN,{'mappings':values}),saved)
 def test_mapping_rejects_unknown_keys_targets_and_non_admin_or_scott(self):
  values=job_imports.MAPPING_DEFAULTS.copy()
  for changed in [{**values,'email':'number'},{**values,'email':False},{**values,'unknown':'client'},{}]:
   with self.assertRaises(Problem):job_imports.save_mapping({},ADMIN,{'mappings':changed})
  for user in [{'email':'tech@example.invalid','role':'tech'},{'email':'Scott@trice.nz','role':'admin'},{'email':'alias@example.invalid','role':'admin','technician':'Scott Yearbury'}]:
   with self.assertRaises(Problem):job_imports.mapping({},user)
   with self.assertRaises(Problem):job_imports.save_mapping({},user,{'mappings':values})
 def test_endpoint_requires_current_revision_and_preserves_audit(self):
  api=test_accounts.AccountsAPI();api.setUp();values=api.call('/api/job-import-mappings')[1]['mappings'];values['problem']='notes'
  self.assertEqual(api.call('/api/job-import-mappings','POST',{'mappings':values},match=False)[0],409)
  self.assertEqual(api.call('/api/job-import-mappings','POST',{'mappings':values})[0],200)
  self.assertEqual(api.call('/api/job-import-mappings')[1]['mappings']['problem'],'notes')
  self.assertEqual(len(api.store.state['jobImportMappingHistory']),1)
  self.assertEqual(api.call('/api/job-import-mappings',token='tech')[0],403)
  self.assertEqual(api.call('/api/job-import-mappings','POST',{'mappings':values},token='tech')[0],403)
if __name__=='__main__':unittest.main()
