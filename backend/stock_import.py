"""Read the supplied stock workbook using standard-library XLSX parsing."""
import base64, io, re, zipfile, hashlib, uuid, copy, datetime as dt, posixpath
from xml.etree import ElementTree as ET
from core import Problem
import stock
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def preview(raw,name='Stock workbook.xlsx'):
    if not isinstance(raw,bytes) or len(raw)>5*1024*1024:raise Problem(400,'Choose an XLSX file smaller than 5 MB.')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if sum(i.file_size for i in z.infolist())>30*1024*1024:raise Problem(400,'The expanded workbook is too large.')
            strings=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
            wb=ET.fromstring(z.read('xl/workbook.xml'));sheet=wb.find('s:sheets',NS)[0];rid=sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            relations=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'));target=next(r.get('Target') for r in relations if r.get('Id')==rid)
            path=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            tree=ET.fromstring(z.read(path));rows=[]
            for row in tree.findall('s:sheetData/s:row',NS):
                values={}
                for cell in row:
                    ref=cell.get('r','');column=''.join(c for c in ref if c.isalpha());node=cell.find('s:v',NS);value=node.text if node is not None else ''
                    if cell.get('t')=='s':value=strings[int(value)]
                    elif cell.get('t')=='inlineStr':value=''.join(cell.find('s:is',NS).itertext())
                    values[column]=value or ''
                if int(row.get('r'))>1 and values.get('A'):rows.append({'row':int(row.get('r')),'values':values})
            if not rows or not any(r['values'].get('B') for r in rows):raise Problem(400,'Expected product codes in A, descriptions in B and workbook quantity in E.')
    except Problem:raise
    except Exception:raise Problem(400,'This workbook could not be read. Use the supplied stock workbook layout.')
    codes={};products=[];unassigned=[]
    for row in rows:codes.setdefault(row['values']['A'].strip().casefold(),[]).append(row['row'])
    for row in rows:
        v=row['values'];issues=[];quantity=None
        if not v.get('B'):unassigned.append(row);continue
        try:
            if v.get('E'):quantity=int(v['E']);assert quantity>=0 and str(quantity)==v['E'].strip()
        except (ValueError,AssertionError):issues.append('Quantity is not a non-negative whole number')
        if quantity is None:issues.append('Missing quantity')
        if len(codes[v['A'].strip().casefold()])>1:issues.append('Repeated product code — keep source rows separate')
        products.append({'code':v['A'].strip(),'description':v['B'].strip(),'sourceRow':row['row'],'sourceQuantity':quantity,'quantityReviewed':False,'sourceNotes':{'currentStock':v.get('C',''),'sentToClients':v.get('D',''),'movements':v.get('G',''),'additional':v.get('H',''),'dateRaw':v.get('F','')},'reviewIssues':issues})
    return {'fingerprint':hashlib.sha256(raw).hexdigest(),'name':stock.text(name,'file name',250,True),'sheet':sheet.get('name'),'products':products,'unassignedRows':unassigned,'quantityMeaning':'Column E: opening stock-on-hand quantity','listedUnits':sum(r['sourceQuantity'] or 0 for r in products)}
def apply(state,candidate,actor,raw=None):
    if any(i['fingerprint']==candidate['fingerprint'] for i in state.get('stock',stock.empty())['imports']):raise Problem(409,'This workbook has already been imported. Its records remain available in Import review.')
    result=copy.deepcopy(state);data=result.setdefault('stock',stock.empty());key=str(uuid.uuid4())
    if raw is not None:data['workbookTemplate']=base64.b64encode(raw).decode()
    for row in candidate['products']:
        product=copy.deepcopy(row);product.update(id=str(uuid.uuid4()),importId=key)
        data['products'][product['id']]=product
    stamp=dt.datetime.now(dt.timezone.utc).isoformat()
    data['imports'].append({k:copy.deepcopy(v) for k,v in candidate.items() if k!='products'}|{'id':key,'importedAt':stamp,'importedBy':actor,'productCount':len(candidate['products'])})
    stock.event(data,'Workbook imported for review',actor,stamp[:10],importId=key,quantity=len(candidate['products']),notes='Column E is opening quantity. Asset numbers remain to be assigned.')
    return confirm_quantities(result,actor)


def confirm_quantities(state,actor):
    """One-time confirmation: column E is opening stock, not a second receipt.

    Keep missing quantities missing and original rows separate. Labelling opening
    units consumes this receipt's pending units, never adds another balance.
    """
    result=copy.deepcopy(state);data=result.get('stock')
    if not data or data.get('sourceFormat')=='handoff_asset_register':return result
    stamp=dt.datetime.now(dt.timezone.utc).isoformat()
    for row in data['products'].values():
        if not row.get('sourceRow') or row.get('openingQuantityConfirmed') or row.get('quantityBasis')=='listed_assets':continue
        qty=row.get('sourceQuantity')
        if type(qty) is not int or qty<0:continue
        row.update(openingQuantityConfirmed=True,quantityReviewed=True)
        if qty:
            key=str(uuid.uuid4())
            data['receipts'][key]={'id':key,'productId':row['id'],'quantity':qty,'pool':'Existing stock','client':'Starting workbook','reference':'Opening stock','jobId':'','date':'2026-10-09','notes':'Column E confirmed by the user as opening stock quantity. Asset numbers still need matching.','assetIds':[],'openingBalance':True,'refurbComplete':False,'technician':'','refurbCompletedAt':'','revision':1}
            row['openingReceiptId']=key
        stock.event(data,'Opening quantity confirmed',actor,stamp[:10],productId=row['id'],quantity=qty,notes='Column E is the opening stock-on-hand quantity.')
    for imported in data['imports']:imported['quantityMeaning']='Column E: confirmed opening stock-on-hand quantity'
    return result

def export(state,template=None):
    """Retain the supplied workbook's layout/styles; write literal cells, never formulas.

    Column E is current stock on hand. Original opening quantities remain in the
    database; asset notes and movement history are retained in their original columns.
    """
    data=state.get('stock',stock.empty())
    if data.get('sourceFormat')=='handoff_asset_register':
        import stock_handoff
        raw=base64.b64decode(data['workbookTemplate'])
        return stock_handoff.export(state,raw)
    if data.get('workbookTemplate'):template=base64.b64decode(data['workbookTemplate'])
    if not template:raise Problem(409,'The starting workbook format has not been saved yet.')
    preview(template) # validate before opening the archive
    ns=NS['s'];tag=lambda name:'{'+ns+'}'+name
    ET.register_namespace('',ns)
    def cell(row,column,value,style=None):
        ref=f'{column}{row.get("r")}';node=next((c for c in row if c.get('r')==ref),None)
        if node is None:node=ET.SubElement(row,tag('c'),{'r':ref})
        for child in list(node):node.remove(child)
        if style is not None and not node.get('s'):node.set('s',style)
        node.set('t','inlineStr');t=ET.SubElement(ET.SubElement(node,tag('is')),tag('t'))
        t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=str(value or '')[:32767]
    def join(*parts):return '\n\n'.join(str(p) for p in parts if p)
    with zipfile.ZipFile(io.BytesIO(template)) as original:
        wb=ET.fromstring(original.read('xl/workbook.xml'));relations=ET.fromstring(original.read('xl/_rels/workbook.xml.rels'))
        rid=wb.find('s:sheets',NS)[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        target=next(r.get('Target') for r in relations if r.get('Id')==rid)
        path=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        sheet_xml=original.read(path)
        namespaces=dict(pair for _,pair in ET.iterparse(io.BytesIO(sheet_xml),events=['start-ns']))
        for prefix,uri in namespaces.items():
            if not re.fullmatch(r'ns\d+',prefix):ET.register_namespace(prefix,uri)
        tree=ET.fromstring(sheet_xml);sheetdata=tree.find('s:sheetData',NS)
        rows={int(r.get('r')):r for r in sheetdata};last=max(rows)
        styles={c.get('r').rstrip('0123456789'):c.get('s') for c in rows.get(2,[]) if c.get('s')}
        for prod in data['products'].values():
            index=prod.get('sourceRow')
            if not index:last+=1;index=last
            row=rows.get(index)
            if row is None:row=ET.SubElement(sheetdata,tag('row'),{'r':str(index)});rows[index]=row
            assets=[a for a in data['assets'].values() if a['productId']==prod['id']]
            source=prod.get('sourceNotes',{})
            if not prod.get('sourceRow'):
                cell(row,'A',prod['code'],styles.get('A'));cell(row,'B',prod['description'],styles.get('B'))
            if assets:
                counts={status:[a for a in assets if a['status']==status] for status in stock.STATES}
                soh='Confirmed stock on hand: '+str(len(counts['Available']))+' available; '+str(len(counts['Allocated']))+' allocated.'
                for status in ('Incoming','Available','Allocated','Refurbishing','Awaiting new asset number','Repair','Retired'):
                    if counts[status]:soh+='\n'+status+': '+', '.join(a['number']+' ('+a['pool']+')' for a in counts[status])
                labels='\n'.join(a['number']+' (current): '+ '; '.join(h['number']+' ['+(h.get('validFrom') or 'start not recorded')+' to '+(h.get('validTo') or 'current')+'] Added: '+(h.get('addedAt') or 'not recorded')+'; '+(h.get('referenceType') or 'Reference')+': '+(h.get('reference') or 'not recorded') for h in stock.number_history(data,a)) for a in assets)
                cell(row,'C',join(source.get('currentStock'),soh,'Asset number validity (end date exclusive):\n'+labels),styles.get('C'))
                delivered='\n'.join(a['number']+' · '+a['client']+' · '+a.get('referenceType','PO')+' '+a['reference']+' · Job '+a.get('jobId','')+' · Delivered '+a.get('dispatchedAt','') for a in counts['With client'])
                cell(row,'D',join(source.get('sentToClients'),'Current delivered assets:\n'+(delivered or 'None')),styles.get('D'))
            movements=[m for m in data['movements'] if m.get('productId')==prod['id']]
            if movements:
                lines=[' · '.join(str(v) for v in [m['date'],m['kind'],m.get('number'),m.get('client'),m.get('reference'),m.get('jobId'),m.get('technician'),m.get('notes')] if v) for m in movements]
                cell(row,'G',join(source.get('movements'),'App movements:\n'+'\n'.join(lines),'Client allocations:\n'+'\n'.join(g['client']+' · '+g.get('referenceType','PO')+' '+g['reference']+' · Job '+g['jobId']+' · '+entry.get('allocatedAt','')+' to '+(entry.get('returnedAt') or entry.get('cancelledAt') or 'current') for g in data['allocations'].values() for asset_id,entry in g['assetStates'].items() if data['assets'].get(asset_id,{}).get('productId')==prod['id'])),styles.get('G'))
            balance=stock.balances(data,prod['id'])
            if prod.get('openingQuantityConfirmed') or not prod.get('sourceRow') or assets:
                cell(row,'E',str(balance['onHandQuantity']),styles.get('E'))
                e=next(c for c in row if c.get('r')==f'E{index}');e.set('t','n')
                for child in list(e):e.remove(child)
                ET.SubElement(e,tag('v')).text=str(balance['onHandQuantity'])
            note='Column E: current stock on hand, including allocated units still in store. '+str(balance['awaitingOpeningNumbers'])+' opening units await asset numbers.' if prod.get('openingQuantityConfirmed') else 'Opening quantity missing: confirm this product separately.' if prod.get('sourceRow') else 'Added in Trident Dashboard. Column E is current stock on hand.'
            cell(row,'H',join(source.get('additional'),note,prod.get('reviewNote')),styles.get('H'))
        dimension=tree.find('s:dimension',NS)
        if dimension is not None:dimension.set('ref',f'A1:H{max(rows)}')
        sheet_bytes=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
        # Excel's mc:Ignorable references unused revision namespaces too. Retain them.
        opening=sheet_bytes.split(b'>',2)[1]
        missing=b''.join((' xmlns'+(':'+prefix if prefix else '')+'="'+uri+'"').encode() for prefix,uri in namespaces.items() if ('xmlns'+(':'+prefix if prefix else '')+'=').encode() not in opening)
        position=sheet_bytes.index(b'>',sheet_bytes.index(b'<worksheet'))
        sheet_bytes=sheet_bytes[:position]+missing+sheet_bytes[position:]
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as result:
            for item in original.infolist():result.writestr(item,sheet_bytes if item.filename==path else original.read(item.filename))
    return output.getvalue()
