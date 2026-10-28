import copy,io,json,threading,unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import schedule,schedule_links,schedule_history,schedule_routes,test_accounts
from core import Problem

class GapPackTests(unittest.TestCase):
 def setUp(self):
  for target,value in [('configuration',{'key':'test','depot':'Depot'}),('estimate',{'duration':15,'seconds':600})]:
   mock=patch.object(schedule_routes,target,return_value=value);mock.start();self.addCleanup(mock.stop)
  self.user={'email':'admin@example.nz'};self.date='2027-02-01'
  self.base={'staffSettings':{'technicians':[{'name':'Scott','rego':''},{'name':'Bala','rego':''}]},'quotes':{'keep':{'value':12}},'otherRecords':{'preserved':True}}
  self.booking={'date':self.date,'technician':'Scott','start':'09:00','duration':60,'client':'Upper','address':'1 Road','type':'Repair','timing':'flexible','notes':''}
 def setup_gap(self):
  state,self.early=schedule.save(self.base,{**self.booking,'start':'07:00','client':'Early'},self.user)
  state,self.upper=schedule.save(state,self.booking,self.user)
  state,self.lower=schedule.save(state,{**self.booking,'start':'11:00','duration':30,'client':'Lower','address':'2 Road'},self.user)
  gap=next(g for g in schedule_links.free_gaps(state,self.date,'Scott') if g['upperId']==self.upper['id'])
  return state,{'date':self.date,'technician':'Scott','action':'pack_gap','direction':'above',**gap}
 def test_all_above_and_attached_travel_move_down_with_spacing(self):
  state,body=self.setup_gap();original=copy.deepcopy(state);before={b['id']:b for b in schedule_links.day_blocks(state,self.date)}
  result=schedule.save_travel(state,body,self.user);after={b['id']:b for b in schedule_links.day_blocks(result,self.date)}
  self.assertEqual(state,original);self.assertEqual(result['quotes'],state['quotes']);self.assertEqual(result['otherRecords'],state['otherRecords'])
  delta=body['end']-body['start'];self.assertEqual(delta,45)
  for identifier in (self.early['id'],self.upper['id']):self.assertEqual(schedule.minutes(after[identifier]['start'])-schedule.minutes(before[identifier]['start']),delta)
  self.assertEqual(after[self.lower['id']],before[self.lower['id']])
  for identifier,b in before.items():
   if b.get('source')=='travel':
    self.assertEqual(after[identifier]['duration'],b['duration'])
    self.assertEqual(schedule.minutes(after[identifier]['start'])-schedule.minutes(b['start']),delta if b['anchorId'] in (self.early['id'],self.upper['id']) else 0)
  joined=[e for e in schedule_links.connections(result,self.date) if e['leftId']==body['upperId'] and e['rightId']==body['lowerId']]
  self.assertTrue(joined);self.assertFalse(joined[0]['linked'])
 def test_all_below_move_up_and_undo_restores_the_whole_action(self):
  state,body=self.setup_gap();body['direction']='below';result=schedule.save_travel(state,body,self.user)
  self.assertEqual(result['appointments'][self.lower['id']]['start'],'10:15')
  self.assertEqual(result['appointments'][self.upper['id']],state['appointments'][self.upper['id']])
  self.assertFalse(any(b.get('source')=='lunch' for b in schedule.read(result,self.date)['appointments']));self.assertEqual(schedule.read(result,self.date)['lunchShading']['start'],'12:00')
  result=schedule_history.record(state,result,self.user['email'],self.date,'Close gap')
  undo=schedule_history.apply(result,self.user['email'],self.date,'undo')
  self.assertEqual(undo['appointments'][self.lower['id']]['start'],self.lower['start'])
  self.assertEqual(schedule.read(undo,self.date)['lunchBlocks'],[])
 def test_fixed_or_confirmed_anywhere_on_chosen_side_prevents_entire_move(self):
  for change in ({'timing':'fixed'},{'bookingStatus':'confirmed'}):
   state,body=self.setup_gap();state['appointments'][self.early['id']].update(change);state['appointments'][self.early['id']].pop('bookingControlsVersion',None);before=copy.deepcopy(state)
   with self.assertRaises(Problem):schedule.save_travel(state,body,self.user)
   self.assertEqual(state,before)
 def test_leave_and_recurring_note_are_barriers(self):
  for source in ('leave','note'):
   state,body=self.setup_gap();block={'id':'barrier','date':self.date,'technician':'Scott','start':'05:00','duration':30,'client':'Reserved','source':source,'timing':'fixed'}
   target='leave_blocks' if source=='leave' else 'schedule_notes.blocks'
   with patch('schedule.'+target,return_value=[block]):
    with self.assertRaisesRegex(Problem,'cannot move'):schedule.save_travel(state,body,self.user)
 def test_team_appointment_is_checked_against_another_technicians_booking(self):
  state,body=self.setup_gap();state['appointments'][self.upper['id']]['technicians']=['Scott','Bala']
  state,_=schedule.save(state,{**self.booking,'technician':'Bala','start':'10:00','duration':30,'client':'Bala fixed','timing':'fixed'},self.user)
  state['scheduleLinks']={schedule_links.edge_id('Bala',self.upper['id'],next(a['id'] for a in state['appointments'].values() if a['client']=='Bala fixed')):False}
  before=copy.deepcopy(state)
  with self.assertRaisesRegex(Problem,'overlap'):schedule.save_travel(state,body,self.user)
  self.assertEqual(state,before)
 def test_linked_team_neighbour_follows_and_is_not_silently_excluded(self):
  with patch.object(schedule,'travel_blocks',return_value=[]):
   state,body=self.setup_gap();state['appointments'][self.upper['id']]['technicians']=['Scott','Bala']
   state,other=schedule.save(state,{**self.booking,'technician':'Bala','start':'10:00','duration':30,'client':'Team neighbour'},self.user)
   edge=schedule_links.edge_id('Bala',self.upper['id'],other['id']);state['scheduleLinks']={edge:True}
   # The gap changes when routing is disabled; setup_gap used the same patch.
   result=schedule.save_travel(state,body,self.user)
   self.assertEqual(result['appointments'][other['id']]['start'],'11:00')
   self.assertEqual(result['appointments'][self.upper['id']]['start'],'10:00')
 def test_stale_gap_day_bounds_and_detached_locked_travel_reject(self):
  state,body=self.setup_gap()
  with self.assertRaisesRegex(Problem,'empty space changed'):schedule.save_travel(state,{**body,'end':body['end']+15},self.user)
  with patch.object(schedule,'travel_blocks',return_value=[]):
   state,body=self.setup_gap();state['appointments'][self.upper['id']]['technicians']=['Scott','Bala']
   state,late=schedule.save(state,{**self.booking,'technician':'Bala','start':'10:00','duration':840,'client':'Long team neighbour'},self.user)
   state['scheduleLinks']={schedule_links.edge_id('Bala',self.upper['id'],late['id']):True}
   with self.assertRaisesRegex(Problem,'selected day'):schedule.save_travel(state,body,self.user)
  state,body=self.setup_gap();detached={'id':'detached','date':self.date,'technician':'Scott','source':'travel','start':'05:00','duration':15,'client':'Detached travel','locked':True,'linked':False}
  with patch.object(schedule,'travel_blocks',return_value=[detached]):
   gap=next(g for g in schedule_links.free_gaps(state,self.date,'Scott') if g['upperId']==self.upper['id'])
   with self.assertRaisesRegex(Problem,'Unlock detached'):schedule.save_travel(state,{**body,**gap},self.user)
 def api_call(self,api,body,tag):
  raw=json.dumps(body).encode();env={'REQUEST_METHOD':'POST','PATH_INFO':'/api/schedule/travel','HTTP_AUTHORIZATION':'Bearer admin','HTTP_ORIGIN':'http://127.0.0.1:18780','HTTP_IF_MATCH':tag,'CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw)};meta=[]
  payload=b''.join(api.app(env,lambda status,headers:meta.append(int(status[:3]))))
  return meta[0],json.loads(payload)
 def test_preview_etag_rejects_change_even_if_gap_ids_are_unchanged(self):
  state,body=self.setup_gap();api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(state);tag=schedule_history.etag(api.store.state)
  api.store.state['appointments'][self.lower['id']]['notes']='Changed by second administrator';api.store.revision+=1;before=copy.deepcopy(api.store.state)
  self.assertEqual(self.api_call(api,body,tag)[0],409);self.assertEqual(api.store.state,before)
 def test_simultaneous_pack_saves_commit_only_one_whole_move(self):
  state,body=self.setup_gap();api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(state);tag=schedule_history.etag(api.store.state)
  original=api.store.commit;barrier=threading.Barrier(2)
  def commit(revision,result):barrier.wait(timeout=10);return original(revision,result)
  with patch.object(api.store,'commit',side_effect=commit):
   with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.api_call(api,body,tag),range(2)))
  self.assertEqual(sorted(r[0] for r in results),[200,409]);self.assertEqual(api.store.revision,2)
  self.assertEqual(api.store.state['appointments'][self.upper['id']]['start'],'09:45')
  self.assertEqual(api.store.state['appointments'][self.early['id']]['start'],'07:45')
  self.assertEqual(api.store.state['appointments'][self.lower['id']]['start'],'11:00')
  self.assertEqual(sum(len(days[self.date]['undo']) for days in api.store.state['scheduleHistory'].values()),1)
