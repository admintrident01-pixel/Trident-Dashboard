import copy,unittest
import job_imports,recycle
from core import Problem
class RemovalTests(unittest.TestCase):
 def setUp(self):
  self.user={'email':'admin@example.invalid','role':'admin','technician':'Alex'}
  self.state={'jobImports':{'a':{'id':'a','objectKey':'job-imports/a/source.json','client':'Example'}},'quotes':{'1':{'sourceImports':[{'id':'a'}],'total':123}},'appointments':{'b':{'jobImportId':'a'}},'pdfs':{'keep':'unchanged'}}
 def test_removal_is_recoverable_and_keeps_allocated_business_records(self):
  before=copy.deepcopy(self.state);result=job_imports.remove_all(self.state,self.user,{'confirmed':True,'ids':['a']})
  self.assertEqual(self.state,before);self.assertEqual(result['jobImports'],{})
  for key in ('quotes','appointments','pdfs'):self.assertEqual(result[key],before[key])
  restored,_=recycle.action(result,{'action':'restore','ids':['importedJob:a']},self.user)
  self.assertEqual(restored['jobImports'],before['jobImports'])
 def test_stale_list_unconfirmed_and_non_admin_cannot_remove(self):
  for data in ({'confirmed':True,'ids':[]},{'confirmed':False,'ids':['a']},{'confirmed':True,'ids':['a','a']}):
   with self.assertRaises(Problem):job_imports.remove_all(self.state,self.user,data)
  with self.assertRaises(Problem):job_imports.remove_all(self.state,{**self.user,'role':'technician'},{'confirmed':True,'ids':['a']})
