import copy,io,json,time,unittest
from unittest.mock import patch
import schedule,schedule_routes,test_accounts

class SchedulePerformanceTests(unittest.TestCase):
 def setUp(self):
  self.config=patch.object(schedule_routes,'configuration',return_value={'key':'qa-only','depot':'Depot'});self.config.start();self.addCleanup(self.config.stop)
  schedule_routes._itinerary_cache.clear()
  self.date='2026-10-29';self.state={'staffSettings':{'technicians':[{'name':'Alex','rego':''}]},'appointments':{'a':{'id':'a','date':self.date,'technician':'Alex','technicians':['Alex'],'client':'Visit','address':'1 Road','start':'09:00','duration':60,'type':'Repair','timing':'fixed','notes':'','version':1}}}
 def test_fast_and_full_reads_never_call_google_or_wait_for_a_result(self):
  before=copy.deepcopy(self.state)
  with patch.object(schedule_routes.urllib.request,'urlopen',side_effect=AssertionError('No provider on any read')) as provider:
   for fast in (True,False):
    result=schedule.read(self.state,self.date,fast=fast)
    self.assertEqual(len(result['appointments']),1);self.assertEqual(len(result['travelBlocks']),2)
    self.assertTrue(all(b['duration']==15 and not b['routePending'] for b in result['travelBlocks']))
    self.assertFalse(result['routeTotals']['Alex'].get('pending',False))
  provider.assert_not_called();self.assertEqual(self.state,before)
 def test_saved_planned_duration_is_stable_without_provider_cache(self):
  identifier=schedule.travel_id(self.date,'Alex','a','before')
  self.state['travelBlocks']={identifier:{'duration':45,'locked':True,'linked':True,'version':3}}
  with patch.object(schedule_routes.urllib.request,'urlopen',side_effect=AssertionError('No provider')):
   for fast in (True,False):
    result=schedule.read(self.state,self.date,fast=fast)
    before=next(b for b in result['travelBlocks'] if b['side']=='before')
    self.assertEqual(before['duration'],45);self.assertFalse(before['routePending']);self.assertTrue(before['routePlanned']);self.assertFalse(before['routeError'])
 def test_unconfirmed_locations_keep_quarter_hour_warning_in_both_paths(self):
  self.state['appointments']['a']['address']='tbc'
  with patch.object(schedule_routes.urllib.request,'urlopen',side_effect=AssertionError('No guessed location')):
   for fast in (True,False):
    result=schedule.read(self.state,self.date,fast=fast)
    for b in result['travelBlocks']:self.assertEqual(b['duration'],15);self.assertTrue(b['routeLocationMissing']);self.assertTrue(b['routeError']);self.assertFalse(b['routePending'])
 def call(self,api,path,conditional=''):
  env={'REQUEST_METHOD':'GET','PATH_INFO':path.split('?')[0],'QUERY_STRING':path.partition('?')[2],'HTTP_ORIGIN':api.app.origin,'HTTP_AUTHORIZATION':'Bearer admin','HTTP_IF_NONE_MATCH':conditional,'CONTENT_LENGTH':'0','wsgi.input':io.BytesIO()};meta=[]
  raw=b''.join(api.app(env,lambda s,h:meta.append((int(s[:3]),dict(h)))));return meta[0][0],json.loads(raw),meta[0][1]
 def test_fast_conditional_read_skips_route_build_when_state_unchanged(self):
  api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(self.state)
  first=self.call(api,'/api/schedule?view=bookings&date='+self.date)
  with patch.object(schedule,'read',side_effect=AssertionError('Do not rebuild unchanged data')):
   second=self.call(api,'/api/schedule?view=bookings&date='+self.date,first[2]['ETag'])
  self.assertEqual(second[0],200);self.assertEqual(second[1],{'unchanged':True})
 def test_route_endpoint_has_same_snapshot_token_and_never_saves(self):
  api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(self.state);before=copy.deepcopy(api.store.state)
  first=self.call(api,'/api/schedule?view=bookings&date='+self.date)
  with patch.object(schedule_routes,'estimate',return_value={'duration':30,'seconds':1500,'distanceMeters':10000}):
   routes=self.call(api,'/api/schedule/routes?date='+self.date)
  self.assertEqual(routes[2]['ETag'],first[2]['ETag']);self.assertFalse(routes[1]['travelBlocks'][0]['routePending']);self.assertEqual(routes[1]['routeTotals']['Alex']['distanceMeters'],20000);self.assertEqual(api.store.state,before);self.assertEqual(api.store.revision,1)

if __name__=='__main__':unittest.main()
