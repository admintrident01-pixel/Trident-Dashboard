import base64,copy,io,unittest,zipfile
from xml.etree import ElementTree as ET
import stock,stocktake_sessions as takes,stock_reports,stock_standard,stock_take
from test_stocktake_sessions import StocktakeTests
from pypdf import PdfReader

def workbook_rows(raw):
 ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  strings=[]
  if 'xl/sharedStrings.xml' in z.namelist():strings=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
  result=[]
  for name in z.namelist():
   if not name.startswith('xl/worksheets/sheet') or not name.endswith('.xml'):continue
   for row in ET.fromstring(z.read(name)).findall('s:sheetData/s:row',ns):
    values={}
    for c in row:
     value=''.join(c.find('s:is',ns).itertext()) if c.get('t')=='inlineStr' else c.findtext('s:v','',ns)
     if c.get('t')=='s':value=strings[int(value)]
     values[''.join(ch for ch in c.get('r') if ch.isalpha())]=value
    result.append(values)
  return result

class StocktakeExportTests(unittest.TestCase):
 def fixture(self):
  f=StocktakeTests();f.setUp();return f
 def assert_exports(self,result,pid,expected):
  product=stock.read(result)['products'][pid];code=product['code'];before=copy.deepcopy(result)
  # Compare actual generated workbooks, not just report helper totals.
  for scope,column in [('products','E'),('standard_soh','H'),('stock_take','E')]:
   if scope=='stock_take':wanted=next(r['expected'] for r in takes.snapshot(result) if r['id']==pid)
   else:wanted=expected
   raw=base64.b64decode(stock_reports.create(result,{'scope':scope,'format':'xlsx'})['file'])
   rows=workbook_rows(raw)
   self.assertTrue(any(r.get('A')==code and r.get(column)==str(wanted) for r in rows),(scope,code,wanted))
  for scope in ['products','standard_soh','stock_take','accessable_soh','asset_history']:
   raw=base64.b64decode(stock_reports.create(result,{'scope':scope,'format':'pdf'})['file'])
   text='\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(raw)).pages)
   self.assertIn(''.join((product['description'] if scope=='asset_history' else code).split()),''.join(text.split()),scope)
   if scope=='standard_soh':
    quantity_row=next(r for r in stock_standard.snapshot(result)['quantities'] if r[0]==code)
    self.assertIn(''.join(''.join(str(v).split()) for v in quantity_row),''.join(text.split()))
  self.assertEqual(result,before,'Exports must never mutate the register')
 def test_found_missing_extra_and_unnumbered_flow_to_actual_exports(self):
  f=self.fixture();f.start();e=f.entry(4);e[f.pid].update(decisions={f.ids[0]:'found',f.ids[1]:'missing'},numbers=['EXTRA-A'],notes='Two unnumbered items found')
  original=copy.deepcopy(f.state);result=f.complete(e);data=stock.read(result)
  self.assertEqual(data['products'][f.pid]['onHandQuantity'],4)
  self.assertEqual(data['products'][f.pid]['deliveredQuantity'],1)
  self.assertEqual(data['assets'][f.ids[1]]['status'],'Retired');self.assertEqual(data['assets'][f.ids[1]]['number'],'MISSING')
  self.assertEqual(result['stockTakes'][takes.read(original,'admin')['draft']['id']]['summary'][0]['counted'],4)
  self.assert_exports(result,f.pid,4)
 def test_zero_and_repeated_stocktake_do_not_duplicate_stock(self):
  f=self.fixture();f.start();e=f.entry(0);e[f.pid]['decisions']={f.ids[0]:'missing',f.ids[1]:'retire'}
  result=f.complete(e);self.assertEqual(stock.balances(result['stock'],f.pid)['onHandQuantity'],0)
  f.state=result;f.start();result=f.complete({f.pid:dict(count=0,decisions={},numbers=[],notes='Counted again')})
  self.assertEqual(len(result['stock']['assets']),3);self.assert_exports(result,f.pid,0)
 def test_new_product_appears_in_live_register_and_exports(self):
  f=self.fixture();d=f.start();f.state=takes.action(f.state,dict(action='add_product',id=d['id'],version=d['version'],code='NEW-CODE',description='New counted product',condition='NEW'),'admin')
  d=takes.read(f.state,'admin')['draft'];pid=d['rows'][-1]['id'];e=f.entry();e[pid]=dict(count=2,decisions={},numbers=['NEW-A'],notes='One unnumbered')
  result=f.complete(e);new=next(p['id'] for p in result['stock']['products'].values() if p['code']=='NEW-CODE');self.assert_exports(result,new,2)
 def test_completed_refurb_pending_items_are_consistent_between_count_and_worksheet(self):
  f=self.fixture();f.state=stock.action(f.state,dict(action='receive',productId=f.pid,pool='Existing stock',quantity=3,date='2026-10-15'),'admin')
  rid=list(f.state['stock']['receipts'])[-1];f.state['stock']['receipts'][rid].update(pool='Trident refurb stock',refurbComplete=True)
  expected=next(r['expected'] for r in takes.snapshot(f.state) if r['id']==f.pid)
  actual=next(r[4] for r in stock_take.rows(f.state)[0] if r[0]=='1234567')
  self.assertEqual(actual,expected,'Printed expected count must match the stocktake screen')

if __name__=='__main__':unittest.main()
