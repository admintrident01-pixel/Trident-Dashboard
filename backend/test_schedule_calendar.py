import copy,unittest
from unittest.mock import patch
import schedule,schedule_links,schedule_history,schedule_release,test_accounts
from core import Problem

class CalendarShadingTests(unittest.TestCase):
 def setUp(self):
  self.date='2026-10-28';self.user={'email':'admin@example.nz'}
  self.base={'staffSettings':{'technicians':[{'name':'Alex','rego':''},{'name':'Blair','rego':''}]},'quotes':{'keep':1},'stock':{'keep':2}}
  self.payload={'date':self.date,'technicians':['Alex'],'start':'11:00','duration':60,'client':'Client','address':'1 Road','type':'Repair','timing':'flexible'}
  self.legacy={'id':'old-lunch','date':self.date,'technician':'Alex','technicians':['Alex'],'source':'lunch','start':'12:00','duration':30,'client':'Lunch','address':'','type':'Lunch','timing':'flexible','version':4,'createdAt':'original','notes':'Keep history','cancelled':False}
  self.base['appointments']={'old-lunch':copy.deepcopy(self.legacy)}
  for target,value in [('configuration',{'key':'test','depot':'Depot'}),('estimate',{'duration':15,'seconds':600})]:
   mock=patch('schedule_routes.'+target,return_value=value);mock.start();self.addCleanup(mock.stop)
 def test_read_keeps_saved_lunch_but_excludes_it_from_every_operational_view(self):
  before=copy.deepcopy(self.base);view=schedule.read(self.base,self.date)
  self.assertEqual(view['appointments'],[]);self.assertEqual(view['lunchBlocks'],[])
  self.assertEqual(view['lunchShading'],{'start':'12:00','duration':30})
  self.assertFalse(any(b['id']=='old-lunch' for b in schedule_links.day_blocks(self.base,self.date)))
  self.assertEqual(schedule_links.connections(self.base,self.date),[]);self.assertEqual(self.base,before)
 def test_booking_moving_and_resizing_cross_lunch_without_changing_history(self):
  state,a=schedule.save(self.base,self.payload,self.user)
  after,a=schedule.save(state,{**a,'start':'12:00','duration':30},self.user)
  after,a=schedule.save(after,{**a,'action':'resize','edge':'end','duration':60},self.user)
  self.assertEqual(after['appointments']['old-lunch'],self.legacy)
  recorded=schedule_history.record(state,after,self.user['email'],self.date,'Cross lunch')
  restored=schedule_history.apply(recorded,self.user['email'],self.date,'undo')
  self.assertEqual(restored['appointments']['old-lunch'],self.legacy)
  self.assertEqual(restored['appointments'][a['id']]['start'],'11:00')
  self.assertEqual(after['quotes'],self.base['quotes']);self.assertEqual(after['stock'],self.base['stock'])
 def test_lunch_does_not_link_to_or_move_with_adjacent_work(self):
  state,a=schedule.save(self.base,self.payload,self.user)
  self.assertFalse(any('old-lunch' in (e['leftId'],e['rightId']) for e in schedule_links.connections(state,self.date)))
  after=schedule.save_travel(state,{'date':self.date,'action':'move_selection','ids':[a['id']],'delta':60},self.user)
  self.assertEqual(after['appointments']['old-lunch'],self.legacy);self.assertEqual(after['appointments'][a['id']]['start'],'12:00')
 def test_routes_can_overlap_lunch_and_header_swap_keeps_hidden_lunch_unchanged(self):
  state,a=schedule.save(self.base,{**self.payload,'start':'12:15'},self.user)
  incoming=next(t for t in schedule.travel_blocks(state,self.date) if t['side']=='before')
  self.assertEqual(incoming['start'],'12:00');self.assertFalse(incoming['routeConflict'])
  after=schedule_release.swap_headers(state,{'date':self.date,'fromTechnician':'Alex','toTechnician':'Blair'},self.user)
  self.assertEqual(after['appointments']['old-lunch'],self.legacy);self.assertEqual(after['appointments'][a['id']]['technicians'],['Blair'])
 def test_holidays_and_lunch_settings_are_validated_and_do_not_modify_bookings(self):
  holidays=[{'date':'2027-01-02','name':' Second day '},{'date':self.date,'name':'Example holiday'}]
  before=copy.deepcopy(self.base)
  state=schedule.save_settings(self.base,{'appointmentTypes':['Repair'],'lunchStart':'13:15','publicHolidays':holidays})
  view=schedule.read(state,self.date)
  self.assertEqual(view['lunchShading']['start'],'13:15');self.assertEqual(view['publicHolidays'],[{'date':self.date,'name':'Example holiday'},{'date':'2027-01-02','name':'Second day'}])
  self.assertEqual(state['appointments'],before['appointments']);self.assertEqual(self.base,before)
  preserved=schedule.save_settings(state,{'appointmentTypes':['Repair']})
  self.assertEqual(preserved['scheduleSettings']['publicHolidays'],view['publicHolidays'])
  _,a=schedule.save(state,{**self.payload,'start':'13:15'},self.user);self.assertEqual(a['start'],'13:15')
  for holidays in ('bad',[None],[{'date':'2027-02-30','name':'Bad'}],[{'date':self.date,'name':''}],[{'date':self.date,'name':'A'}]*2):
   with self.assertRaises(Problem):schedule.save_settings(state,{'appointmentTypes':['Repair'],'publicHolidays':holidays})
 def test_new_lunch_blocks_and_stale_lunch_edit_are_refused_without_record_changes(self):
  before=copy.deepcopy(self.base)
  for data in ({**self.payload,'type':'Lunch'}, {**self.legacy,'start':'13:00'}):
   with self.assertRaisesRegex(Problem,'Schedule settings'):schedule.save(self.base,data,self.user)
  self.assertEqual(self.base,before)
 def test_holiday_settings_keep_admin_permissions_and_revision_checks(self):
  api=test_accounts.AccountsAPI();api.setUp();payload={'appointmentTypes':['Repair'],'publicHolidays':[{'date':self.date,'name':'Example'}]}
  self.assertEqual(api.call('/api/schedule-settings','POST',payload,token='tech')[0],403)
  self.assertEqual(api.call('/api/schedule-settings','POST',payload,match=False)[0],409)
  self.assertEqual(api.call('/api/schedule-settings','POST',payload)[0],200)
  self.assertEqual(api.call('/api/schedule-settings')[1]['publicHolidays'],payload['publicHolidays'])
