import base64,copy,io,json,unittest,zipfile
from xml.etree import ElementTree as ET
from unittest.mock import patch
import quote_catalog,quote_settings,test_accounts
from core import Problem

NS=quote_settings.NS;RNS=quote_settings.RNS
HEADERS=['Quote number','Quote date','Quoted by','Quote type','Quote to / organisation','Recipient email','Organisation postal / street address','Organisation town / city / postcode','Client name','Client postal / street address','Client town / city / postcode','Job details','Reference / approval number','Equipment / model','Vehicle make / model','Registration','Introduction / scope','Additional notes','Line items','Subtotal NZD','GST percent','GST NZD','Total NZD','Currency','Quote validity (days)','Payment account name','Bank','Account number','PDF filename','Confirmed at','Status','Quote ID','Revision']
def column(n):
 result=''
 while n:n,r=divmod(n-1,26);result=chr(65+r)+result
 return result

def workbook(legacy=None):
 """Disposable QA-only workbook, never used to initialise production."""
 sheets={'Business Details':{1:{'A':'Setting','B':'Value'}},'Quote Types':{1:dict(zip(['A','B','C','D','E','F'],quote_settings.TYPE_HEADERS))},'Default Items':{1:dict(zip(['A','B','C','D'],quote_settings.ITEM_HEADERS))},'Email Details':{1:{'A':'Setting','B':'Value'},2:{'A':'Subject prefix','B':'QA quote'},3:{'A':'Email message','B':'QA only'}},'Quote Register':{1:{'A':'Starting quote number'},2:{'A':1750},5:{column(i):v for i,v in enumerate(HEADERS,1)}}}
 for i,(label,key) in enumerate(quote_settings.LABELS.items(),2):sheets['Business Details'][i]={'A':label,'B':quote_settings.BASE[key]}
 for i,name in enumerate(['Equipment repair','Vehicle service','Assessment','Other'],2):sheets['Quote Types'][i]={'A':name,'B':'Equipment' if i==2 else 'Vehicle' if i==3 else 'Other','C':'QA scope','D':'QA author','E':'QA job','F':'QA notes'}
 sheets['Default Items'][2]={'A':'Equipment repair','B':'QA labour','C':1,'D':100}
 for i,(number,row) in enumerate((legacy or {}).items(),6):sheets['Quote Register'][i]={'A':number,**row}
 wb=ET.Element('{'+NS+'}workbook');body=ET.SubElement(wb,'{'+NS+'}sheets');rels=ET.Element('Relationships',xmlns='http://schemas.openxmlformats.org/package/2006/relationships');entries={}
 for i,(name,rows) in enumerate(sheets.items(),1):
  ET.SubElement(body,'{'+NS+'}sheet',{'name':name,'sheetId':str(i),'{'+RNS+'}id':'rId'+str(i)})
  ET.SubElement(rels,'Relationship',{'Id':'rId'+str(i),'Type':RNS+'/worksheet','Target':'worksheets/sheet'+str(i)+'.xml'})
  doc=ET.Element('{'+NS+'}worksheet');data=ET.SubElement(doc,'{'+NS+'}sheetData')
  for number,values in rows.items():
   row=ET.SubElement(data,'{'+NS+'}row',r=str(number))
   for col,value in values.items():
    c=ET.SubElement(row,'{'+NS+'}c',r=col+str(number))
    if isinstance(value,(float,int)):ET.SubElement(c,'{'+NS+'}v').text=str(value)
    else:c.set('t','inlineStr');ET.SubElement(ET.SubElement(c,'{'+NS+'}is'),'{'+NS+'}t').text=str(value)
  entries['xl/worksheets/sheet'+str(i)+'.xml']=ET.tostring(doc)
 entries['xl/workbook.xml']=ET.tostring(wb);entries['xl/_rels/workbook.xml.rels']=ET.tostring(rels)
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for name,data in entries.items():z.writestr(name,data)
 return out.getvalue()

class QuotePerformanceTests(unittest.TestCase):
 def setUp(self):
  quote_catalog.indexed.cache_clear();quote_catalog.workbook_data.cache_clear()
  self.state={'workbook':base64.b64encode(workbook({1750:{'I':'Legacy client','B':45953,'S':'1. Repair\nQuantity: 2; Unit price excl GST: 10; Amount NZD: 20','T':20,'AC':'Legacy.pdf'},2000:{'AE':'Deleted'}})).decode(),'quotes':{},'pdfs':{'Legacy.pdf':'private-key'}}
  for n in range(1751,1871):self.state['quotes'][str(n)]={'id':'id-'+str(n),'state':'Draft' if n%2 else 'Finalised','revision':2,'pdfFilename':'','createdAt':'keep','createdByName':'Creator '+str(n%10),'data':{'fields':{'number':str(n),'client':'Client '+str(n),'by':'Printed author','job':'Repair','type':'Equipment repair','date':'2026-10-29','notes':'hidden-search-'+str(n)},'lines':[{'description':'Large private detail','qty':1,'rate':42}],'calculation':{'preserve':'markup'}}}
 def test_first_page_is_small_and_has_no_full_quotes_or_workbook(self):
  before=copy.deepcopy(self.state);result=quote_catalog.listing(self.state,{'defaults':['1']})
  self.assertEqual(len(result['quotes']),10);self.assertEqual(result['total'],121);self.assertEqual(result['nextNumber'],2001)
  self.assertNotIn('workbook',result);self.assertNotIn('lines',result['quotes'][0]['data']);self.assertNotIn('notes',result['quotes'][0]['data']['fields'])
  self.assertEqual(result['defaults']['types'][0]['name'],'Equipment repair');self.assertEqual(self.state,before)
 def test_search_covers_non_displayed_fields_and_all_pages(self):
  result=quote_catalog.listing(self.state,{'search':['hidden-search-1753'],'status':['Draft']})
  self.assertEqual(result['total'],1);self.assertEqual(result['quotes'][0]['data']['fields']['number'],'1753')
  self.assertEqual(quote_catalog.listing(self.state,{'page':['2'],'size':['10']})['quotes'][0]['data']['fields']['number'],'1860')
 def test_detail_preserves_identity_calculation_and_legacy_fields(self):
  self.assertEqual(quote_catalog.detail(self.state,{'number':['1754']})['quote'],self.state['quotes']['1754'])
  q=quote_catalog.detail(self.state,{'number':['1750']})['quote'];self.assertTrue(q['legacy']);self.assertEqual(q['data']['fields']['date'],'2025-10-23')
  self.assertEqual(q['data']['lines'],[{'description':'Repair','qty':2,'rate':10}])
  with self.assertRaises(Problem):quote_catalog.detail(self.state,{'number':['2000']})
 def test_sort_creator_and_status_and_invalid_requests(self):
  result=quote_catalog.listing(self.state,{'sort':['4'],'direction':['asc'],'status':['Draft']})
  self.assertEqual(result['quotes'][0]['createdByName'],'Creator 1');self.assertEqual(result['total'],60)
  for params in [{'size':['10000']},{'page':['oops']},{'status':['Deleted']},{'sort':['7']}]:
   with self.assertRaises(Problem):quote_catalog.listing(self.state,params)
 def test_index_is_reused_but_refreshes_after_external_changes(self):
  quote_catalog.listing(self.state,{})
  with patch.object(quote_catalog,'workbook_info',side_effect=AssertionError('Repeated parsing')):
   quote_catalog.listing(self.state,{'page':['2']})
   self.state['quotes']['1754']['data']['fields']['client']='Changed by another user'
   self.assertEqual(quote_catalog.detail(self.state,{'number':['1754']})['quote']['data']['fields']['client'],'Changed by another user')
  self.state['pdfs'].clear();self.assertFalse(quote_catalog.listing(self.state,{'search':['Legacy client']})['quotes'][0]['hasPdf'])
 def test_endpoints_remain_admin_only_and_timings_contain_no_data(self):
  api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(self.state)
  for path in ['/api/quote-dashboard','/api/quote-detail']:
   self.assertEqual(api.call(path,token='tech')[0],403);self.assertEqual(api.call(path,token='')[0],401)
  status,data,headers=api.call('/api/quote-dashboard');self.assertEqual(status,200);self.assertIn('database_read;dur=',headers['Server-Timing']);self.assertIn('quote_index;dur=',headers['Server-Timing'])
  self.assertNotIn('Legacy',headers['Server-Timing']);self.assertEqual(api.store.revision,1)
 def test_preflight_can_be_reused_without_caching_business_data_or_allowing_other_origins(self):
  api=test_accounts.AccountsAPI();api.setUp()
  status,_,headers=api.call('/api/quote-dashboard',method='OPTIONS',token='')
  self.assertEqual(status,200);self.assertEqual(headers['Access-Control-Max-Age'],'600');self.assertEqual(headers['Access-Control-Allow-Origin'],api.app.origin)
  self.assertEqual(api.call('/api/quote-dashboard',method='OPTIONS',origin='https://other.example')[0],403)
  api.store.state.update(self.state);self.assertEqual(api.call('/api/quote-dashboard')[2]['Cache-Control'],'no-store')

if __name__=='__main__':unittest.main()
