"""Load a verified, decoded stock handoff; preserve uncertainty and the source template."""
import base64,copy,datetime as dt,hashlib,io,re,uuid,zipfile
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo
from core import Problem
import stock

SOURCE_URL='https://docs.google.com/spreadsheets/d/1LDDT_PcILLGMRu4p6BULH6oS6MR5QrAPvbF7og3qLR4/edit'

def apply(state,snapshot,template,actor):
    rows=snapshot.get('values',[])
    if not rows or rows[0][:4]!=['Product code','Condition','Description','Original stock notes']:raise Problem(400,'Expected the decoded handoff columns.')
    result=copy.deepcopy(state);data=stock.empty();result['stock']=data
    stamp=dt.datetime.now(dt.timezone.utc).isoformat();date=dt.datetime.now(ZoneInfo('Pacific/Auckland')).date().isoformat()
    fingerprint=hashlib.sha256(template).hexdigest();import_id=str(uuid.uuid5(uuid.NAMESPACE_URL,SOURCE_URL+'|'+fingerprint))
    data.update(sourceFormat='handoff_asset_register',workbookTemplate=base64.b64encode(template).decode(),sourceSnapshot=copy.deepcopy(snapshot))
    parent='';all_labels=set();seen_products=set()
    for row_number,raw in enumerate(rows[1:],2):
        row=[*raw,*['']*max(0,11-len(raw))];code=str(row[0]).strip()
        if code:parent=code
        if not re.fullmatch(r'\d{6}',parent):raise Problem(400,'Missing parent product code in the handoff.')
        condition=str(row[1]).strip();description=str(row[2]);note=str(row[3]);cells=[str(c) for c in row[4:] if c]
        if condition not in ('','NEW','REFURB') or not description:raise Problem(400,'Invalid product condition or description.')
        if (parent,condition) in seen_products:raise Problem(400,'Repeated parent/condition row in the handoff.')
        seen_products.add((parent,condition));pid=str(uuid.uuid5(uuid.NAMESPACE_URL,SOURCE_URL+'|product|'+parent+'|'+condition))
        issues=['Quantity covers explicitly listed assets only; total stock is not independently confirmed.']
        if not cells:issues=['No assets explicitly listed; stock quantity is unknown, not confirmed zero.']
        if parent=='100067' and condition=='NEW':issues.append('19/08 has no asset directly attached in the original note; date remains unassigned.')
        prod={'id':pid,'code':parent,'condition':condition,'description':description,'sourceRow':row_number,'sourceQuantity':len(cells) if cells else None,'quantityBasis':'listed_assets','quantityReviewed':False,'openingQuantityConfirmed':False,'importId':import_id,'reviewIssues':issues,'sourceNotes':{'currentStock':note,'sentToClients':'','movements':'','additional':'','dateRaw':''},'sourceAssetCells':cells}
        data['products'][pid]=prod
        if not cells:continue
        rid=str(uuid.uuid5(uuid.NAMESPACE_URL,pid+'|receipt'));pool='New stock' if condition=='NEW' else 'Trident refurb stock' if condition=='REFURB' else 'Existing stock'
        receipt={'id':rid,'productId':pid,'quantity':len(cells),'pool':pool,'client':'','reference':'','referenceType':'PO','jobId':'','date':date,'dateMeaning':'Imported on; acquisition date may be unknown','notes':note,'assetIds':[],'refurbComplete':condition=='REFURB','technician':'','refurbCompletedAt':None,'revision':1,'handoffImport':True}
        data['receipts'][rid]=receipt
        for cell in cells:
            lines=cell.splitlines();number=lines[0].strip()
            if not re.fullmatch(r'\d{5,10}',number):raise Problem(400,'Invalid decoded asset number.')
            added_line=next((l[6:].strip() for l in lines[1:] if l.startswith('Added:')),'date not recorded')
            added=None;added_text=None
            if re.fullmatch(r'\d{1,2}/\d{1,2}',added_line):
                dt.datetime.strptime(added_line+'/2000','%d/%m/%Y');added_text=added_line
            elif added_line!='date not recorded':
                try:added=dt.datetime.strptime(added_line,'%d/%m/%Y').date().isoformat()
                except ValueError:raise Problem(400,'Unsupported added date in the handoff.')
            refs=[{'type':kind,'number':ref} for kind,ref in re.findall(r'\b(PO|SO)\s*(\d+)\b',cell)]
            replaces=re.findall(r'replaces\s+(\d+)',cell,re.I);earlier=re.findall(r'previously\s+(\d+)',cell,re.I);previous=[*earlier,*replaces]
            for label in [*previous,number]:
                if label.casefold() in all_labels:raise Problem(409,'A current or past number appears more than once in the handoff.')
                all_labels.add(label.casefold())
            reference_type=refs[0]['type'] if len(refs)==1 else 'Reference'
            reference=refs[0]['number'] if len(refs)==1 else ' / '.join(r['type']+' '+r['number'] for r in refs)
            history=[{'number':n,'validFrom':None,'validTo':None,'addedAt':None,'referenceType':'Reference','reference':''} for n in previous]
            history.append({'number':number,'validFrom':None,'validTo':None,'addedAt':added,'addedAtText':added_text,'referenceType':reference_type,'reference':reference,'referenceContext':'Source note; precise event link unverified' if len(refs)>1 else ''})
            aid=str(uuid.uuid5(uuid.NAMESPACE_URL,SOURCE_URL+'|asset|'+number))
            asset={'id':aid,'number':number,'previousNumbers':previous,'numberHistory':history,'receiptId':rid,'productId':pid,'pool':pool,'status':'Available','location':'Store','client':'','reference':'','jobId':'','allocationId':'','lastAllocationId':'','refurbTechnician':'','refurbCompletedAt':None,'revision':1,'sourceCondition':condition,'sourceStockReady':True,'sourceReferences':refs,'sourceAssetCell':cell,'sourceNotes':note}
            data['assets'][aid]=asset;receipt['assetIds'].append(aid)
    data['imports'].append({'id':import_id,'fingerprint':fingerprint,'name':'Complete setup handoff — verified live Sheet1','sheet':'Sheet1','sourceUrl':SOURCE_URL,'importedAt':stamp,'importedBy':actor,'productCount':len(data['products']),'listedUnits':len(data['assets']),'unassignedRows':[],'quantityMeaning':'Explicitly listed current assets. Blank rows and missing dates remain unknown.'})
    stock.event(data,'Stock replaced from verified handoff',actor,date,quantity=len(data['assets']),notes='Current numbers only; old numbers retained as aliases. Dates without a year and blank quantities were not inferred.')
    return result

def export(state,template):
    """Retain the handoff workbook, merged parents and original rich-text notes."""
    data=stock.read(state);ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';tag=lambda n:'{'+ns+'}'+n;ET.register_namespace('',ns)
    with zipfile.ZipFile(io.BytesIO(template)) as original:
        path='xl/worksheets/sheet1.xml';tree=ET.fromstring(original.read(path));sheet=tree.find(tag('sheetData'));rows={int(r.get('r')):r for r in sheet};last_source=max(p.get('sourceRow') or 1 for p in data['products'].values())
        def column(n):
            text=''
            while n:n,r=divmod(n-1,26);text=chr(65+r)+text
            return text
        def set_cell(row,col,value,style=None):
            ref=column(col)+row.get('r');node=next((c for c in row if c.get('r')==ref),None)
            if node is None:node=ET.SubElement(row,tag('c'),{'r':ref})
            for child in list(node):node.remove(child)
            if style is not None:node.set('s',style)
            node.set('t','inlineStr');t=ET.SubElement(ET.SubElement(node,tag('is')),tag('t'));t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=str(value)[:32767]
        largest=7
        for p in data['products'].values():
            index=p.get('sourceRow')
            if not index:last_source+=1;index=last_source
            row=rows.get(index)
            if row is None:row=ET.SubElement(sheet,tag('row'),{'r':str(index)});rows[index]=row
            if not p.get('sourceRow'):
                for col,value in enumerate([p['code'],p.get('condition',''),p['description'],p.get('sourceNotes',{}).get('currentStock','')],1):set_cell(row,col,value)
            assets=[a for a in data['assets'].values() if a['productId']==p['id']]
            style=next((c.get('s') for c in row if c.get('r')=='E'+str(index)),None)
            largest=max(largest,len(assets))
            for index_asset in range(max(7,len(assets))):
                value=''
                if index_asset<len(assets):
                    a=assets[index_asset];h=a['numberHistory'][-1];value=a['number']+'\nAdded: '+stock.label_added(h)+'\nStatus: '+a['status']
                    if h.get('reference'):value+='\n'+stock.label_reference(h)
                    if a['previousNumbers']:value+='\nPrevious: '+', '.join(a['previousNumbers'])
                    if a.get('reference'):value+='\nClient: '+a.get('client','')+'; '+a.get('referenceType','PO')+' '+a['reference']+'; Job '+a.get('jobId','')
                set_cell(row,index_asset+5,value,style)
            for i in range(7,largest):set_cell(rows[1],i+5,'Asset '+str(i+1)+' / added to stock')
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as result:
            for item in original.infolist():result.writestr(item,ET.tostring(tree,encoding='utf-8',xml_declaration=True) if item.filename==path else original.read(item.filename))
        return out.getvalue()
