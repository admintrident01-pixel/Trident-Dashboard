import copy,io,json,unittest,importlib.util
from pathlib import Path
from unittest.mock import patch
import schedule,schedule_routes
from core import Problem

class ManualRoutingTests(unittest.TestCase):
 def setUp(self):
  self.date='2026-10-30';self.user={'email':'admin@example.nz'}
  self.state={'staffSettings':{'technicians':[{'name':'Alex','rego':''}]},'appointments':{'a':{'id':'a','date':self.date,'technician':'Alex','technicians':['Alex'],'client':'Visit','address':'1 Road','start':'09:00','duration':60,'type':'Repair','timing':'flexible','notes':'','version':1}}}
  config=patch.object(schedule_routes,'configuration',return_value={'key':'qa-only','depot':'Depot'});config.start();self.addCleanup(config.stop)
  provider=patch.object(schedule_routes.urllib.request,'urlopen',side_effect=lambda *a,**k:io.BytesIO(b'{"routes":[{"duration":"1801s","distanceMeters":5000}]}'));self.http=provider.start();self.addCleanup(provider.stop)
  schedule_routes._itinerary_cache.clear()
 def block(self,state=None):return next(b for b in schedule.travel_blocks(state or self.state,self.date) if b['side']=='before')
 def test_all_read_paths_and_new_addresses_make_zero_google_requests(self):
  before=copy.deepcopy(self.state)
  for address in ('1 Road','2 Road','tbc'):
   state=copy.deepcopy(self.state);state['appointments']['a']['address']=address
   for fast in (True,False):schedule.read(state,self.date,fast=fast)
   schedule_routes.itinerary_totals(list(state['appointments'].values()),['Alex'])
  self.http.assert_not_called();self.assertEqual(self.state,before)
 def test_only_explicit_calculation_calls_google_and_selected_duration_survives_restart(self):
  block=self.block();state=schedule.save_travel(self.state,{**block,'date':self.date,'action':'recalculate'},self.user)
  self.assertEqual(self.http.call_count,1);self.assertEqual(self.block(state)['duration'],45)
  schedule_routes._itinerary_cache.clear()
  for fast in (True,False):
   data=schedule.read(json.loads(json.dumps(state)),self.date,fast=fast)
   self.assertEqual(next(b for b in data['travelBlocks'] if b['id']==block['id'])['duration'],45)
  self.assertEqual(self.http.call_count,1);self.assertEqual(state['appointments'],self.state['appointments'])
  self.assertNotIn('distanceMeters',json.dumps(state));self.assertNotIn('seconds',json.dumps(state))
 def test_fresh_worker_and_cache_only_even_with_force_never_call_provider(self):
  spec=importlib.util.spec_from_file_location('fresh_manual_worker',Path(schedule_routes.__file__))
  second=importlib.util.module_from_spec(spec);spec.loader.exec_module(second)
  self.assertTrue(second.estimate('Depot','1 Road')['manualOnly'])
  self.assertTrue(second.estimate('Depot','1 Road',force=True,cache_only=True)['manualOnly'])
  self.http.assert_not_called()
 def test_failed_calculation_keeps_saved_plan_and_reads_do_not_retry(self):
  block=self.block();state=schedule.save_travel(self.state,{**block,'date':self.date,'action':'planned_time','duration':60},self.user);before=copy.deepcopy(state)
  self.http.side_effect=OSError('offline')
  with self.assertRaises(Problem):schedule.save_travel(state,{**self.block(state),'date':self.date,'action':'recalculate'},self.user)
  self.assertEqual(state,before);self.assertEqual(self.block(state)['duration'],60)
  schedule.read(state,self.date);self.assertEqual(self.http.call_count,1)
 def test_manual_duration_validation_stale_control_and_no_google(self):
  block=self.block()
  for duration in (0,16,True,1500):
   with self.assertRaises(Problem):schedule.save_travel(self.state,{**block,'date':self.date,'action':'planned_time','duration':duration},self.user)
  with self.assertRaises(Problem):schedule.save_travel(self.state,{**block,'date':self.date,'action':'planned_time','duration':30,'version':99},self.user)
  state=schedule.save_travel(self.state,{**block,'date':self.date,'action':'planned_time','duration':30},self.user)
  self.assertEqual(self.block(state)['duration'],30);self.assertFalse(self.block(state)['locked']);self.http.assert_not_called()
 def test_missing_location_explicit_calculation_is_rejected_without_google(self):
  self.state['appointments']['a']['address']='tbc'
  with self.assertRaises(Problem):schedule.save_travel(self.state,{**self.block(),'date':self.date,'action':'recalculate'},self.user)
  self.http.assert_not_called()
