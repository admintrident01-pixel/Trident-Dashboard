import copy,unittest
import vehicles,test_accounts
from core import Problem
class VehicleOrderTests(unittest.TestCase):
 def test_order_preserves_records_and_all_vehicle_fields(self):
  state={'vehicles':vehicles.fleet({}),'vehicleChecks':{'existing':{'vehicleId':'VEH-06','signature':'Andrew Thomas'}}}
  before=copy.deepcopy(state);order=[row['id'] for row in reversed(state['vehicles'])]
  saved=vehicles.save_order(state,{'order':order})
  self.assertEqual([row['id'] for row in vehicles.fleet(saved)],order)
  self.assertEqual(state,before);self.assertEqual(saved['vehicleChecks'],state['vehicleChecks']);self.assertEqual(saved['vehicles'],state['vehicles'])
 def test_missing_duplicate_and_unknown_ids_are_rejected(self):
  order=[row['id'] for row in vehicles.fleet({})]
  for value in [order[:-1],order[:-1]+[order[0]],order[:-1]+['unknown'],None,[{}]]:
   with self.assertRaises(Problem):vehicles.save_order({}, {'order':value})
 def test_new_vehicles_append_and_removed_vehicles_do_not_return(self):
  state=vehicles.save_order({}, {'order':[row['id'] for row in reversed(vehicles.fleet({}))]})
  state['vehicles']=vehicles.fleet({})[1:]+[{'id':'NEW'}]
  ids=[row['id'] for row in vehicles.fleet(state)]
  self.assertEqual(ids[-1],'NEW');self.assertNotIn('VEH-01',ids)
 def test_admin_permissions_cas_and_api_persistence(self):
  api=test_accounts.AccountsAPI();api.setUp();order=[row['id'] for row in reversed(vehicles.fleet(api.store.state))]
  self.assertEqual(api.call('/api/vehicle-order','POST',{'order':order},token='tech')[0],403)
  self.assertEqual(api.call('/api/vehicle-order','POST',{'order':order},match=False)[0],409)
  self.assertEqual(api.call('/api/vehicle-order','POST',{'order':order})[0],200)
  self.assertEqual([row['id'] for row in api.call('/api/vehicles')[1]['vehicles']],order)
