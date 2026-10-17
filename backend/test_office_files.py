import base64,copy,io,unittest,zipfile
from unittest.mock import Mock
import office_files
from core import Problem
from test_accounts import AccountsAPI
class OfficeFilesTests(unittest.TestCase):
 def setUp(self):
  self.state={};self.objects={};self.user={'email':'admin@example.nz'}
  self.storage=Mock();self.storage.put=lambda k,v:self.objects.__setitem__(k,v);self.storage.get=lambda k:self.objects[k];self.storage.delete=lambda k:self.objects.pop(k,None)
 def act(self,p):
  office_files.action(self.state,p,self.user,self.storage,lambda s:setattr(self,'state',s));return list(self.state['officeFiles'].values())[-1]
 def test_nested_upload_rename_move_trash_restore(self):
  folder=self.act({'action':'folder','name':'Repairs'});file=self.act({'action':'upload','name':'SOP.txt','parent':folder['id'],'content':base64.b64encode(b'Instructions').decode()})
  self.assertNotIn('key',office_files.listing(self.state)['items'][1]);self.assertEqual(office_files.read(self.state,file['id'],self.storage)['content'],base64.b64encode(b'Instructions').decode())
  self.act({'action':'trash','id':folder['id'],'version':1})
  with self.assertRaises(Problem):office_files.read(self.state,file['id'],self.storage)
  self.act({'action':'restore','id':folder['id'],'version':2});self.act({'action':'rename','id':file['id'],'version':1,'name':'Guide.txt'});self.act({'action':'move','id':file['id'],'version':2,'parent':''})
  self.assertEqual(self.state['officeFiles'][file['id']]['parent'],'')
 def test_reject_invalid_folder_stale_edits_and_empty_file(self):
  folder=self.act({'action':'folder','name':'Process'})
  for p in [{'action':'move','id':folder['id'],'version':1,'parent':folder['id']},{'action':'rename','id':folder['id'],'version':0,'name':'New'},{'action':'upload','name':'Empty.txt','content':''},{'action':'folder','name':'../bad'}]:
   before=copy.deepcopy(self.state)
   with self.assertRaises(Problem):self.act(p)
   self.assertEqual(self.state,before)
 def test_failed_commit_cleans_uploaded_object(self):
  def fail(_):raise Problem(409,'Changed')
  with self.assertRaises(Problem):office_files.action({}, {'action':'upload','name':'a.txt','content':'YQ=='},self.user,self.storage,fail)
  self.assertEqual(self.objects,{})
 def test_word_content_preview(self):
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Safe SOP</w:t></w:r></w:p></w:document>')
  file=self.act({'action':'upload','name':'SOP.docx','content':base64.b64encode(out.getvalue()).decode()});self.assertIn('Safe SOP',office_files.read(self.state,file['id'],self.storage)['preview'])
 def test_authenticated_read_admin_write(self):
  api=AccountsAPI();api.setUp();api.app.objects=self.storage
  self.assertEqual(api.call('/api/office-files',token='')[0],401)
  self.assertEqual(api.call('/api/office-files',token='tech')[0],403)
  self.assertEqual(api.call('/api/office-files/content',token='tech')[0],403)
  self.assertEqual(api.call('/api/office-files','POST',{'action':'folder','name':'SOP'},token='tech')[0],403)
  self.assertEqual(api.call('/api/office-files','POST',{'action':'folder','name':'SOP'})[0],200)
class DatabaseTransferTests(OfficeFilesTests):
 def test_copy_folder_includes_contents_once_and_leaves_originals(self):
  folder=self.act({'action':'folder','name':'SOPs'})
  child=self.act({'action':'upload','name':'Guide.txt','parent':folder['id'],'content':'YWJj'})
  refs=[{'id':folder['id'],'version':1},{'id':child['id'],'version':1}]
  self.act({'action':'copy-items','items':refs,'parent':''})
  rows=self.state['officeFiles'];self.assertEqual(len(rows),4)
  copied=next(i for i in rows.values() if i['name']=='SOPs (copy)')
  copyfile=next(i for i in rows.values() if i['parent']==copied['id'])
  self.assertNotEqual(copyfile['key'],child['key']);self.assertEqual(self.objects[copyfile['key']],b'abc');self.assertEqual(rows[child['id']]['parent'],folder['id'])
 def test_multi_move_is_atomic_and_rejects_stale_or_recursive_moves(self):
  folder=self.act({'action':'folder','name':'SOPs'});a=self.act({'action':'upload','name':'A.txt','content':'YQ=='});b=self.act({'action':'upload','name':'B.txt','content':'Yg=='})
  before=copy.deepcopy(self.state)
  with self.assertRaises(Problem):self.act({'action':'move-items','parent':folder['id'],'items':[{'id':a['id'],'version':1},{'id':b['id'],'version':0}]})
  self.assertEqual(self.state,before)
  with self.assertRaises(Problem):self.act({'action':'move-items','parent':folder['id'],'items':[{'id':folder['id'],'version':1}]})
  self.act({'action':'move-items','parent':folder['id'],'items':[{'id':a['id'],'version':1},{'id':b['id'],'version':1}]})
  self.assertEqual(self.state['officeFiles'][a['id']]['parent'],folder['id']);self.assertEqual(self.state['officeFiles'][b['id']]['parent'],folder['id'])
 def test_copy_cleanup_and_duplicate_names(self):
  a=self.act({'action':'upload','name':'A.txt','content':'YQ=='})
  refs=[{'id':a['id'],'version':1}]
  self.act({'action':'copy-items','parent':'','items':refs});self.act({'action':'copy-items','parent':'','items':refs})
  self.assertEqual({i['name'] for i in self.state['officeFiles'].values()},{'A.txt','A (copy).txt','A (copy 2).txt'})
  old=set(self.objects)
  def fail(_):raise Problem(409,'Concurrent update')
  with self.assertRaises(Problem):office_files.action(self.state,{'action':'copy-items','parent':'','items':refs},self.user,self.storage,fail)
  self.assertEqual(set(self.objects),old)
if __name__=='__main__':unittest.main()
