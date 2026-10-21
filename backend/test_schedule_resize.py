import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
import schedule,test_accounts
from core import Problem

class ResizePlan(unittest.TestCase):
 def test_shared_frontend_backend_scenarios_and_atomic_failures(self):
  scenarios=json.loads((Path(__file__).parent.parent/'tests/fixtures/schedule-resize.json').read_text())
  for case in scenarios:
   with self.subTest(case=case['name']):
    state={'appointments':{b['id']:b for b in case['blocks']},'quotes':{'preserved':1},'stock':{'preserved':2},'officeFiles':{'preserved':3}}
    before=copy.deepcopy(state);old=state['appointments'][case['root']]
    data={**old,'action':'resize','edge':case['edge'],'start':case['start'],'duration':case['duration']}
    with patch.object(schedule,'read_without_travel',return_value=case['blocks']),patch.object(schedule,'travel_blocks',return_value=case['travel']):
     if case['error']:
      with self.assertRaises(Problem):schedule.save(state,data,{'email':'admin@example.nz'})
     else:
      result,booking=schedule.save(state,data,{'email':'admin@example.nz'})
      changed={id:b['start'] for id,b in result['appointments'].items() if b!=state['appointments'][id]}
      self.assertEqual(changed,case['expected']);self.assertEqual(booking['duration'],case['duration'])
      for key in ('quotes','stock','officeFiles'):self.assertEqual(result[key],state[key])
      for id in changed:self.assertEqual(result['appointments'][id]['version'],2)
    self.assertEqual(state,before)
 def test_resize_validation_and_no_extra_field_edits(self):
  case=json.loads((Path(__file__).parent.parent/'tests/fixtures/schedule-resize.json').read_text())[0]
  old=case['blocks'][0];state={'appointments':{old['id']:old}}
  with patch.object(schedule,'read_without_travel',return_value=[old]),patch.object(schedule,'travel_blocks',return_value=[]):
   for patch_data in ({'version':0},{'duration':16},{'edge':'invalid'},{'start':'09:01'},{'start':'10:00'},{'duration':1500}):
    with self.assertRaises(Problem):schedule.save(state,{**old,'action':'resize','edge':'end',**patch_data},{'email':'admin@example.nz'})
   result,booking=schedule.save(state,{**old,'action':'resize','edge':'end','duration':90,'client':'Do not overwrite','technician':'Other'},{'email':'admin@example.nz'})
   self.assertEqual(booking['client'],old['client']);self.assertEqual(booking['technician'],old['technician'])
 def test_http_permission_etag_and_undo(self):
  api=test_accounts.AccountsAPI();api.setUp()
  data={'date':'2026-10-21','technician':'Scott Yearbury','start':'09:00','duration':60,'client':'First sample','address':'1 Sample Road','type':'Equipment repair','timing':'fixed'}
  first=api.call('/api/schedule','POST',data)[1]['appointment']
  second=api.call('/api/schedule','POST',{**data,'start':'10:00','timing':'flexible','client':'Second sample'})[1]['appointment']
  change={**first,'action':'resize','edge':'end','duration':90}
  self.assertEqual(api.call('/api/schedule','POST',change,token='tech')[0],403)
  self.assertEqual(api.call('/api/schedule','POST',change,match=False)[0],409)
  status,result,_=api.call('/api/schedule','POST',change);self.assertEqual(status,200,result)
  self.assertEqual(api.store.state['appointments'][second['id']]['start'],'10:30')
  status,_,_=api.call('/api/schedule/travel','POST',{'date':data['date'],'action':'undo'})
  self.assertEqual(status,200);self.assertEqual(api.store.state['appointments'][second['id']]['start'],'10:00')
  self.assertEqual(api.store.state['appointments'][first['id']]['duration'],60)

if __name__=='__main__':unittest.main()
