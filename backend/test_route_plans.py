import importlib.util, io, json, tempfile, threading, time, unittest, sys, types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
import route_plans, schedule_routes, schedule

class DurableRouteTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)/'plans.sqlite3';self.backend=route_plans.SQLiteStore(self.path)
        store_patch=patch.object(route_plans,'store',return_value=self.backend);self.store_mock=store_patch.start();self.addCleanup(store_patch.stop)
        self.config=patch.object(schedule_routes,'configuration',return_value={'key':'test-only','depot':'Depot'});self.config.start();self.addCleanup(self.config.stop)
        schedule_routes._cache.clear();schedule_routes._itinerary_cache.clear()
        schedule_routes._controls_signature=None
        self.http=patch.object(schedule_routes.urllib.request,'urlopen',side_effect=lambda *a,**k:io.BytesIO(json.dumps({'routes':[{'duration':'901s','distanceMeters':5000}]}).encode()))
        self.provider=self.http.start();self.addCleanup(self.http.stop)
    def restart_worker(self):
        schedule_routes._cache.clear();schedule_routes._itinerary_cache.clear()
        self.store_mock.return_value=route_plans.SQLiteStore(self.path)
    def test_refresh_and_restart_and_expired_clock_never_recalculate(self):
        first=schedule_routes.estimate('Depot','1 Road');first['duration']=999
        with patch.object(schedule_routes.time,'monotonic',return_value=10**12):
            self.assertEqual(schedule_routes.estimate('Depot','1 Road')['duration'],30)
        self.restart_worker()
        self.assertEqual(schedule_routes.estimate(' DEPOT ','1   ROAD')['duration'],30)
        self.assertEqual(self.provider.call_count,1)
    def test_new_address_and_direction_are_distinct_but_timing_is_not_a_key(self):
        for pair in [('Depot','1 Road'),('Depot','1 Road'),('1 Road','Depot'),('Depot','2 Road')]:schedule_routes.estimate(*pair)
        self.assertEqual(self.provider.call_count,3)
    def test_itinerary_and_travel_blocks_share_saved_results_without_register_writes(self):
        state={'staffSettings':{'technicians':[{'name':'Alex','rego':''}]},'appointments':{'a':{'id':'a','date':'2026-10-30','technician':'Alex','technicians':['Alex'],'start':'09:00','duration':60,'client':'Visit','address':'1 Road','type':'Repair','notes':'','timing':'fixed'}}}
        before=json.dumps(state,sort_keys=True)
        for i in range(3):
            if i:self.restart_worker()
            data=schedule.read(state,'2026-10-30')
            self.assertEqual([r['duration'] for r in data['travelBlocks']],[30,30])
            self.assertEqual(data['routeTotals']['Alex']['distanceMeters'],10000)
        self.assertEqual(self.provider.call_count,2);self.assertEqual(json.dumps(state,sort_keys=True),before)
    def test_failed_route_is_not_retried_by_polling_or_restart(self):
        self.provider.side_effect=OSError('provider unavailable')
        self.assertIn('error',schedule_routes.estimate('Depot','1 Road'));self.restart_worker()
        self.assertIn('error',schedule_routes.estimate('Depot','1 Road'))
        self.assertEqual(self.provider.call_count,1)
    def test_deliberate_retry_is_allowed_and_failure_preserves_last_good_plan(self):
        self.assertEqual(schedule_routes.estimate('Depot','1 Road')['duration'],30)
        self.provider.side_effect=OSError('provider unavailable')
        self.assertIn('error',schedule_routes.estimate('Depot','1 Road',force=True))
        self.restart_worker();self.assertEqual(schedule_routes.estimate('Depot','1 Road')['duration'],30)
        self.assertEqual(self.provider.call_count,2)
    def test_simultaneous_workers_only_one_provider_request(self):
        spec=importlib.util.spec_from_file_location('second_route_worker',Path(schedule_routes.__file__))
        second=importlib.util.module_from_spec(spec);spec.loader.exec_module(second)
        entered=threading.Event();release=threading.Event()
        def calculate(*args,**kwargs):
            entered.set();self.assertTrue(release.wait(3));return io.BytesIO(b'{"routes":[{"duration":"901s","distanceMeters":5000}]}')
        self.provider.side_effect=calculate
        with patch.object(second,'configuration',return_value={'key':'test-only','depot':'Depot'}),ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(schedule_routes.estimate,'Depot','1 Road');self.assertTrue(entered.wait(3))
            waiting=pool.submit(second.estimate,'Depot','1 Road');self.assertTrue(waiting.result(timeout=3)['pending'])
            release.set();self.assertEqual(first.result(timeout=3)['duration'],30)
            self.assertEqual(second.estimate('Depot','1 Road')['duration'],30)
        self.assertEqual(self.provider.call_count,1)
    def test_shared_recalculation_invalidates_other_workers_without_google_retry(self):
        spec=importlib.util.spec_from_file_location('other_route_worker',Path(schedule_routes.__file__))
        second=importlib.util.module_from_spec(spec);spec.loader.exec_module(second)
        with patch.object(second,'configuration',return_value={'key':'test-only','depot':'Depot'}):
            second.observe_controls({})
            self.assertEqual(second.estimate('Depot','1 Road')['duration'],30)
            second.observe_controls({})
            with patch.object(self.backend,'read',side_effect=AssertionError('Unchanged polling must use memory')):
                self.assertEqual(second.estimate('Depot','1 Road')['duration'],30)
            self.provider.side_effect=lambda *a,**k:io.BytesIO(b'{"routes":[{"duration":"1801s","distanceMeters":8000}]}')
            self.assertEqual(schedule_routes.estimate('Depot','1 Road',force=True)['duration'],45)
            second.observe_controls({'travel-1':{'version':2,'duration':45}})
            self.assertEqual(second.estimate('Depot','1 Road')['duration'],45)
            self.assertEqual(self.provider.call_count,2)
    def test_crashed_calculation_requires_explicit_retry_not_paid_auto_retry(self):
        name=route_plans.key('Depot','1 Road')
        self.backend.write(name,0,{'status':'pending','createdAt':time.time()-100})
        result=schedule_routes.estimate('Depot','1 Road')
        self.assertEqual(result['defaultDuration'],15);self.assertIn('Recalculate',result['error']);self.provider.assert_not_called()
        self.assertEqual(schedule_routes.estimate('Depot','1 Road',force=True)['duration'],30);self.assertEqual(self.provider.call_count,1)
    def test_storage_outage_fails_closed_without_google(self):
        self.store_mock.side_effect=OSError('private storage failure')
        result=schedule_routes.estimate('Depot','1 Road')
        self.assertIn('Google Maps was not called',result['error']);self.provider.assert_not_called()
    def test_missing_locations_never_touch_provider_or_persistence(self):
        for address in ('','tbc','Location not confirmed'):
            self.assertTrue(schedule_routes.estimate('Depot',address)['locationMissing'])
        self.provider.assert_not_called();self.store_mock.assert_not_called()
    def test_bookings_only_read_does_not_wait_for_cloud_storage(self):
        self.store_mock.side_effect=AssertionError('Fast read must not load cloud objects')
        self.assertTrue(schedule_routes.estimate('Depot','1 Road',cache_only=True)['pending']);self.provider.assert_not_called();self.store_mock.assert_not_called()

class RouteStoreGenerationTests(unittest.TestCase):
    def test_stale_writer_cannot_replace_another_result(self):
        with tempfile.TemporaryDirectory() as folder:
            one=route_plans.SQLiteStore(Path(folder)/'cache.db');two=route_plans.SQLiteStore(Path(folder)/'cache.db')
            lease,_=route_plans.claim(one,'key',0,None)
            self.assertIsNone(route_plans.claim(two,'key',0,None)[0])
            self.assertTrue(route_plans.finish(one,'key',lease,{'duration':30}))
            self.assertIsNone(two.write('key',lease[0],{'status':'failed','result':{'error':'stale'}}))
            self.assertEqual(route_plans.result(two.read('key')[1])['duration'],30)

    def test_cloud_generation_guards_prevent_duplicate_claims_and_stale_overwrites(self):
        class NotFound(Exception):pass
        class PreconditionFailed(Exception):pass
        records={}
        class Blob:
            def __init__(self,name):self.name=name
            def reload(self,**kwargs):
                if self.name not in records:raise NotFound()
                self.generation=records[self.name][0]
            def download_as_bytes(self,if_generation_match,**kwargs):
                if records[self.name][0]!=if_generation_match:raise PreconditionFailed()
                return records[self.name][1].encode()
            def upload_from_string(self,value,if_generation_match,**kwargs):
                current=records.get(self.name,(0,None))[0]
                if current!=if_generation_match:raise PreconditionFailed()
                self.generation=current+1;records[self.name]=(self.generation,value)
        package=types.ModuleType('google');package.__path__=[]
        api=types.ModuleType('google.api_core');api.__path__=[]
        exceptions=types.ModuleType('google.api_core.exceptions');exceptions.NotFound=NotFound;exceptions.PreconditionFailed=PreconditionFailed
        backend=route_plans.CloudStore.__new__(route_plans.CloudStore);backend.bucket=types.SimpleNamespace(blob=Blob)
        with patch.dict(sys.modules,{'google':package,'google.api_core':api,'google.api_core.exceptions':exceptions}):
            self.assertEqual(backend.read('key'),(0,None))
            lease,_=route_plans.claim(backend,'key',0,None)
            self.assertIsNone(route_plans.claim(backend,'key',0,None)[0])
            self.assertTrue(route_plans.finish(backend,'key',lease,{'duration':45,'distanceMeters':9000}))
            self.assertIsNone(backend.write('key',lease[0],{'status':'failed','result':{}}))
            self.assertEqual(route_plans.result(backend.read('key')[1])['duration'],45)
