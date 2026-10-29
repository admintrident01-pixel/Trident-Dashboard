import base64,copy,io,unittest
from pypdf import PdfReader
import stock,stock_reports,test_accounts
from core import Problem

def fixture():
    data=stock.empty()
    data['products']['p']={'id':'p','code':'BED-ETUDE','description':'Example bed - Etude Classic 4 Section Ultra Low'}
    data['assets']['a']={'id':'a','productId':'p','number':'QA-101','previousNumbers':[],'pool':'New stock','status':'Available','location':'Store','revision':1,'client':'','jobId':'','reference':'','numberHistory':[{'number':'QA-101','validFrom':'2026-10-15','addedAt':'2026-10-14','referenceType':'PO','reference':'PO-123'}]}
    return {'stock':data}

class AssetDetailPDFTests(unittest.TestCase):
    def render(self,state):
        result=stock_reports.create(state,{'scope':'asset_detail','format':'pdf','assetId':'a'})
        reader=PdfReader(io.BytesIO(base64.b64decode(result['file'])))
        return result,reader,'\n'.join(p.extract_text() for p in reader.pages)
    def test_a5_sheet_has_requested_fields_and_never_changes_any_stock_values(self):
        state=fixture();before=copy.deepcopy(state);result,pdf,text=self.render(state)
        self.assertEqual(len(pdf.pages),1)
        self.assertAlmostEqual(float(pdf.pages[0].mediabox.width),148/25.4*72,places=2)
        self.assertAlmostEqual(float(pdf.pages[0].mediabox.height),210/25.4*72,places=2)
        for expected in ('QA-101','BED-ETUDE','Example bed','Available','Yes','14 Oct 2026','PO-123','Not recorded','Store'):self.assertIn(expected,text)
        self.assertEqual(result['mime'],'application/pdf');self.assertEqual(result['name'],'Trident-asset-QA-101.pdf');self.assertEqual(state,before)
    def test_availability_is_yes_only_for_available_status(self):
        for status in stock.STATES:
            state=fixture();state['stock']['assets']['a']['status']=status
            _,_,text=self.render(state)
            self.assertIn('\nYes\n' if status=='Available' else '\nNo\n',text)
    def test_added_date_is_not_invented_from_current_label_or_export_date(self):
        state=fixture();asset=state['stock']['assets']['a']
        asset['numberHistory']=[{'number':'OLD','validFrom':None,'addedAt':None},{'number':'QA-101','addedAt':'2026-10-29'}]
        _,_,text=self.render(state);self.assertIn('Added to stock\nNot recorded',text);self.assertNotIn('29 Oct 2026',text)
        asset['numberHistory'][0]['addedAtText']='14/10'
        _,_,text=self.render(state);self.assertIn('14/10 (year not recorded)',text)
    def test_literal_markup_unicode_and_current_references_survive(self):
        state=fixture();asset=state['stock']['assets']['a'];asset.update(client='Māori & <Client>',referenceType='SO',reference='SO-456',jobId='JOB-789',status='Allocated',sourceReferences=[{'type':'PO','number':'SOURCE-1'}])
        _,_,text=self.render(state)
        for expected in ('Māori & <Client>','SO-456','JOB-789','PO SOURCE-1','No'):self.assertIn(expected,text)
    def test_long_description_and_references_wrap_without_losing_content(self):
        state=fixture();state['stock']['products']['p']['description']='Long example description '*50+'END OF DESCRIPTION'
        state['stock']['assets']['a']['reference']='REFERENCE-'+'x'*200
        _,pdf,text=self.render(state);self.assertIn('END OF DESCRIPTION',' '.join(text.split()))
        self.assertTrue(all(abs(float(p.mediabox.width)-148/25.4*72)<.01 for p in pdf.pages));self.assertLessEqual(len(pdf.pages),4)
    def test_export_api_remains_admin_only_and_is_a_read_not_a_commit(self):
        api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(fixture());before=copy.deepcopy(api.store.state);revision=api.store.revision
        body={'scope':'asset_detail','format':'pdf','assetId':'a'}
        self.assertEqual(api.call('/api/stock-report','POST',body,token='tech')[0],403)
        self.assertEqual(api.call('/api/stock-report','POST',body)[0],200)
        self.assertEqual(api.store.state,before);self.assertEqual(api.store.revision,revision)
    def test_missing_asset_or_non_pdf_format_fails_cleanly(self):
        for asset_id in ('missing',None,[]):
            with self.assertRaises(Problem):stock_reports.create(fixture(),{'scope':'asset_detail','format':'pdf','assetId':asset_id})
        with self.assertRaises(Problem):stock_reports.create(fixture(),{'scope':'asset_detail','format':'xlsx','assetId':'a'})
