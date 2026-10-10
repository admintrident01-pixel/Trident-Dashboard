import copy, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import labour
from core import Problem
import test_accounts

class LabourSettingsTests(unittest.TestCase):
    def test_requested_defaults(self):
        items=labour.read({})['items']
        self.assertEqual([r['cost'] for r in items if r['category']=='labour'],[91,95,110])
        self.assertEqual([r['cost'] for r in items if r['category']=='travel'],[91,95,110])
        self.assertEqual(next(r['cost'] for r in items if r['category']=='mileage'),1.2)
        self.assertEqual(next(r['cost'] for r in items if r['category']=='consumables'),20)
    def test_custom_rates_persist_without_changing_quotes(self):
        state={'quotes':{'1754':{'saved':'quote'}},'workbook':'unchanged','pdfs':{'file':'private'}}
        cfg=labour.read(state);cfg['items'][0]['cost']=25;cfg['items'][0]['margin']=20
        cfg['items'].append({'id':'battery','category':'parts','name':'Replacement battery','cost':160,'margin':25})
        result=labour.save(state,cfg)
        self.assertEqual(labour.read(result),cfg)
        self.assertEqual(state,{'quotes':{'1754':{'saved':'quote'}},'workbook':'unchanged','pdfs':{'file':'private'}})
        self.assertEqual(result['quotes'],state['quotes'])
        self.assertEqual(result['workbook'],state['workbook'])
    def test_settings_validation(self):
        valid=labour.defaults()
        for field,value in [('cost',-1),('margin',100),('margin',float('nan')),('cost',True),('name',''),('category','other')]:
            cfg=copy.deepcopy(valid);cfg['items'][0][field]=value
            with self.assertRaises(Problem,msg=field):labour.save({},cfg)
        with self.assertRaises(Problem):labour.save({}, {'items':valid['items'][1:]})
        duplicate=copy.deepcopy(valid);duplicate['items'].append(duplicate['items'][0])
        with self.assertRaises(Problem):labour.save({},duplicate)
    def test_api_access_and_conflicts(self):
        api=test_accounts.AccountsAPI();api.setUp()
        self.assertEqual(api.call('/api/labour-settings',token='tech')[0],403)
        self.assertEqual(api.call('/api/labour-settings','POST',labour.defaults(),token='tech')[0],403)
        self.assertEqual(api.call('/api/labour-settings')[0],200)
        self.assertEqual(api.call('/api/labour-settings','POST',labour.defaults(),match=False)[0],409)
        self.assertEqual(api.call('/api/labour-settings','POST',labour.defaults())[0],200)

if __name__=='__main__':unittest.main()
