import copy,io,unittest,zipfile
from xml.etree import ElementTree as ET
import stock,stock_handoff,stock_import,stock_reports
from core import Problem

def snapshot():
    return {'values':[['Product code','Condition','Description','Original stock notes','Asset 1 / added to stock'],['100001','NEW','Test equipment','original notes','9910001\nAdded: 19/08\nPO123456'],['','REFURB','Test equipment','old to new','9910002\nAdded: date not recorded\nReplaces 9910003; previously 9910004'],['100002','','Unlisted equipment','No explicit asset']]}

class HandoffTests(unittest.TestCase):
    def setUp(self):self.original={'quotes':{'1':{'business':'retained'}},'timesheets':{'example':'retained'},'stock':stock.empty()};self.state=stock_handoff.apply(self.original,snapshot(),b'fixture template','local-admin')
    def test_current_only_counts_and_nonstock_preserved(self):
        for key in ('quotes','timesheets'):self.assertEqual(self.original[key],self.state[key])
        data=stock.read(self.state);self.assertEqual(len(data['products']),3);self.assertEqual(len(data['assets']),2)
        self.assertEqual(data['summary']['Available stock'],2);self.assertEqual(data['summary']['Awaiting asset numbers'],0)
        asset=next(a for a in data['assets'].values() if a['number']=='9910002');self.assertEqual(asset['previousNumbers'],['9910004','9910003']);self.assertTrue(stock.ready_refurb(asset))
    def test_unknown_condition_quantity_and_year_remain_unknown(self):
        a=next(a for a in self.state['stock']['assets'].values() if a['number']=='9910001')
        self.assertIsNone(a['numberHistory'][-1]['validFrom']);self.assertIsNone(a['numberHistory'][-1]['addedAt']);self.assertEqual(a['numberHistory'][-1]['addedAtText'],'19/08')
        blank=next(p for p in self.state['stock']['products'].values() if p['code']=='100002');self.assertEqual(blank['condition'],'');self.assertIsNone(blank['sourceQuantity'])
        self.assertFalse(stock.quantity_known(self.state['stock'],blank));self.assertEqual(stock.label_added(a['numberHistory'][-1]),'19/08 (year not recorded)')
        self.assertEqual(a['numberHistory'][-1]['reference'],'123456');self.assertEqual(a['reference'],'');self.assertEqual(self.state['stock']['allocations'],{})
    def test_restart_confirmation_does_not_create_duplicate_opening_stock(self):self.assertEqual(stock_import.confirm_quantities(self.state,'restart'),self.state)
    def test_dates_and_unknown_rows_in_reports(self):
        report=stock_reports.tables(self.state,'accessable_soh');self.assertIn('19/08 (year not recorded)',str(report[-1]))
        summary=report[1][2];blank=next(r for r in summary if r[0]=='100002');self.assertEqual(blank[2],'Not recorded');self.assertEqual(blank[6],'Quantity needs review')
        self.assertIn('[NEW]',str(summary));self.assertIn('REFURB',str(stock_reports.tables(self.state,'refurbed')))
    def test_duplicates_are_rejected_and_source_untouched(self):
        before=copy.deepcopy(self.original);bad=snapshot();bad['values'][2][4]='9910001\nAdded: date not recorded'
        with self.assertRaises(Problem):stock_handoff.apply(self.original,bad,b'x','actor')
        self.assertEqual(self.original,before)
    def test_can_add_dated_past_number_without_inventing_current_start(self):
        a=next(iter(self.state['stock']['assets'].values()));result=stock.action(self.state,{'action':'past_history','date':'2026-10-15','assetIds':[a['id']],'revisions':{a['id']:1},'pastNumbers':[{'currentNumber':a['number'],'number':'9910099','validFrom':'2020-01-01','validTo':'2021-01-01','referenceType':'Reference','reference':'KNOWN-REF'}]},'admin')
        updated=result['stock']['assets'][a['id']];self.assertIsNone(updated['numberHistory'][-1]['validFrom']);self.assertEqual(stock.read(result)['summary']['Available stock'],2)
    def test_new_and_refurb_variants_share_parent_code(self):
        result=stock.action(self.state,{'action':'product','code':'100001','condition':'','description':'Unspecified variant'},'admin')
        self.assertEqual(len(result['stock']['products']),4)
        with self.assertRaises(Problem):stock.action(self.state,{'action':'product','code':'100001','condition':'NEW','description':'Duplicate'},'admin')
