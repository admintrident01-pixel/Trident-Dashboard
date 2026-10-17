import unittest
from unittest.mock import patch
import schedule_routes
class RouteTotalTests(unittest.TestCase):
 def setUp(self):
  self.cache=patch.dict(schedule_routes._itinerary_cache,{},clear=True);self.cache.start();self.addCleanup(self.cache.stop)
  self.a={'id':'a','technician':'Rick','start':'09:00','address':'A'}
  self.b={**self.a,'id':'b','start':'11:00','address':'B'}
 def test_depot_appointment_order_and_complete_distance(self):
  with patch.object(schedule_routes,'configuration',return_value={'depot':'Depot','key':'test'}),patch.object(schedule_routes,'estimate',return_value={'distanceMeters':1200}) as estimate:
   total=schedule_routes.itinerary_totals([self.b,self.a,{**self.a,'id':'cancel','cancelled':True},{**self.a,'id':'lunch','source':'lunch'}],['Rick','Daryll'])
  self.assertEqual(total['Rick']['distanceMeters'],3600);self.assertTrue(total['Rick']['complete']);self.assertEqual(total['Daryll']['distanceMeters'],0)
  self.assertEqual({call.args for call in estimate.call_args_list},{('Depot','A'),('A','B'),('B','Depot')})
 def test_failed_leg_is_not_a_false_complete_total(self):
  def estimate(a,b):return {'error':'Not found'} if a=='A' else {'distanceMeters':1000}
  with patch.object(schedule_routes,'configuration',return_value={'depot':'Depot','key':'test'}),patch.object(schedule_routes,'estimate',side_effect=estimate):
   total=schedule_routes.itinerary_totals([self.a,self.b],['Rick'])['Rick']
  self.assertFalse(total['complete']);self.assertIsNone(total['distanceMeters']);self.assertEqual(total['knownLegs'],2)
 def test_team_itineraries_are_independent_and_repeated_legs_count(self):
  with patch.object(schedule_routes,'configuration',return_value={'depot':'Depot','key':'test'}),patch.object(schedule_routes,'estimate',return_value={'distanceMeters':500}):
   result=schedule_routes.itinerary_totals([{**self.a,'technicians':['Rick','Daryll']},self.b],['Rick','Daryll'])
  self.assertEqual(result['Rick']['distanceMeters'],1500);self.assertEqual(result['Daryll']['distanceMeters'],1000)

 def test_unchanged_itinerary_reuses_totals_but_returns_an_independent_value(self):
  with patch.object(schedule_routes,'configuration',return_value={'depot':'Depot','key':'test'}),patch.object(schedule_routes,'estimate',return_value={'distanceMeters':500}) as estimate:
   first=schedule_routes.itinerary_totals([self.a,self.b],['Rick']);count=estimate.call_count
   first['Rick']['distanceMeters']=999999
   second=schedule_routes.itinerary_totals([self.a,self.b],['Rick'])
   self.assertEqual(estimate.call_count,count);self.assertEqual(second['Rick']['distanceMeters'],1500)
   schedule_routes.itinerary_totals([self.a,{**self.b,'address':'C'}],['Rick']);self.assertGreater(estimate.call_count,count)
 def test_forced_recalculation_invalidates_itinerary_cache(self):
  schedule_routes._itinerary_cache['test']=(999999999,{})
  with patch.object(schedule_routes,'configuration',return_value={'key':'','depot':'Depot'}):schedule_routes.estimate('A','B',force=True)
  self.assertFalse(schedule_routes._itinerary_cache)
