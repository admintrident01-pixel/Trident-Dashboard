"""Read-only stock reports. Original workbook export remains available separately."""
import base64, datetime as dt, io, re, zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo
from core import Problem
import stock, stock_import

SCOPES={'stock_take':'Stock take Sheet','standard_soh':'Standard SOH Accessable report','accessable_soh':'New Accessable SOH report','products':'All products','intake':'Incoming stock','refurbing':'Refurbishment','refurbed':'Refurbed stock','assets':'Stock on hand','allocations':'Stock allocated to clients','delivered':'Stock delivered to clients','history':'Movement history','asset_history':'Asset and client history'}

def tables(state,scope):
    data=stock.read(state);assets=list(data['assets'].values());products=data['products']
    description=lambda key:products.get(key,{}).get('description','')+((' ['+products[key]['condition']+']') if products.get(key,{}).get('condition') else '')
    if scope=='accessable_soh':
        def product_fields(key):
            p=products.get(key,{})
            return [p.get('code','Not recorded'),description(key)]
        def order(a):
            group=data['allocations'].get(a.get('allocationId'),{})
            entry=group.get('assetStates',{}).get(a['id'],{})
            active=entry.get('status') in ('Allocated','With client')
            reference=a.get('reference') or (group.get('reference') if active else '')
            return reference,group if active else {}
        summary=[];register=[]
        stage_names={'Available':'Available - in store','Allocated':'Allocated - in store','With client':'Delivered to client','Incoming':'Incoming stock','Refurbishing':'Refurbing stock','Awaiting new asset number':'Refurbishment - needs new number','Repair':'Under repair','Retired':'Retired - not in stock'}
        for p in products.values():
            known=stock.quantity_known(data,p)
            available=p['availableQuantity'] if known else 'Not recorded'
            minimum=p.get('minimumStock')
            level='Quantity needs review' if not known else 'Out of stock' if available==0 else 'Minimum not set' if minimum is None else 'Low stock' if available<minimum else 'Stock available'
            holding='Not set' if minimum is None else f'Minimum: {minimum}\nShortfall: '+(str(max(0,minimum-available)) if known else 'Not recorded')
            summary.append([p['code'],description(p['id']),available,p['allocatedQuantity'],p['deliveredQuantity'],p['awaitingOpeningNumbers'],level,holding])
        priority={'Out of stock':0,'Low stock':1,'Quantity needs review':2,'Minimum not set':3,'Stock available':4}
        summary.sort(key=lambda r:(priority[r[6]],r[0].casefold()))
        for a in sorted(assets,key=lambda a:(products[a['productId']]['code'].casefold(),a['number'].casefold())):
            ref,g=order(a)
            context=' | '.join(v for v in [a.get('client') or g.get('client',''),((a.get('referenceType') or g.get('referenceType','PO'))+' '+ref) if ref else '',a.get('jobId') or g.get('jobId','')] if v)
            old_numbers=', '.join(h['number'] for h in a['numberHistory'] if h['number']!=a['number'])
            register.append([*product_fields(a['productId']),a['number'],1,stage_names.get(a['status'],a['status']),a['pool'],context,old_numbers or 'None'])
        for r in data['receipts'].values():
            pending=max(0,r['quantity']-len(r['assetIds']))
            if pending:
                stage='Available - opening stock' if r.get('openingBalance') else 'Refurbing stock' if r['pool']=='Trident refurb stock' and not r.get('refurbComplete') else 'Refurbed - needs new number' if r['pool']=='Trident refurb stock' else 'Incoming stock'
                register.append([*product_fields(r['productId']),'Not assigned',pending,stage,r['pool'],r.get('reference',''),'Not recorded'])
        level_counts={label:sum(r[6]==label for r in summary) for label in priority}
        guide=[['Report date',dt.datetime.now(ZoneInfo('Pacific/Auckland')).date().isoformat()],['Available to allocate',str(sum(p['availableQuantity'] for p in products.values()))+' recorded units in store, not reserved for an order. Does not include delivered items.'],['Low-stock rule','Each product/condition uses its saved minimum from Stock settings. Available units below that minimum are Low stock; at the minimum is sufficient. Zero is Out of stock. Blank minimums are Not set; 0 means no minimum holding is required. Shortfall is the quantity needed to reach the minimum; unconfirmed quantities remain unknown.'],['Products needing attention',f"{level_counts['Out of stock']} out of stock; {level_counts['Low stock']} low stock; {level_counts['Quantity needs review']} with unconfirmed quantities."],['Stock on hand','Available plus allocated units still in store. Delivered stock is shown separately. Completed refurbs are included once their new asset number is assigned; do not add them again.'],['Asset numbers','The register lists every recorded asset at every stage, including retired items clearly marked as not in stock. Each numbered asset has quantity 1. Old numbers identify the same unit, not additional stock.'],['Missing numbers',str(sum(max(0,r['quantity']-len(r['assetIds'])) for r in data['receipts'].values()))+' units have no assigned asset number. Historical source notes are not verified current asset numbers.'],['Quantity needs review','Unconfirmed opening quantities are shown as Not recorded, never assumed to be zero. Other stage counts reflect recorded movements.'],['Orders','Current allocations include both reserved and delivered stock. Client PO history also retains cancelled and returned orders; do not add historical quantities to current stock.']]
        if data.get('sourceFormat')=='handoff_asset_register':guide.insert(1,['Stock count basis','Counts cover explicitly listed current assets only. Blank product rows are unknown, not confirmed zero. Low-stock flags refer to the recorded units; check completeness before ordering. Partial added dates retain their day/month without assuming a year. Source PO/SO references are separate historical evidence, not current client allocations; the same asset may appear under multiple references and must not be counted twice.'])
        unallocated=[];allocated=[];client_orders=[];supplier_receipts=[]
        for a in assets:
            ref,g=order(a)
            # A delivered item can still be unallocated when no order is recorded.
            if a['status'] in ('Available','Allocated','With client'):
                if not ref:
                    unallocated.append([*product_fields(a['productId']),a['number'],1,'Delivered' if a['status']=='With client' else 'In store'])
                else:
                    allocated.append([*product_fields(a['productId']),a['number'],1,a.get('client') or g.get('client',''),(a.get('referenceType') or g.get('referenceType','PO'))+' '+ref,a.get('jobId') or g.get('jobId',''),'Delivered' if a['status']=='With client' else 'Not delivered'])
        for p in products.values():
            if p['awaitingOpeningNumbers']:
                unallocated.append([p['code'],description(p['id']),'Not assigned',p['awaitingOpeningNumbers'],'In store'])
        # PO history retains the asset number valid at allocation, even after return/relabel.
        for g in data['allocations'].values():
            if g.get('referenceType','PO')!='PO':continue
            for key,entry in g['assetStates'].items():
                a=data['assets'].get(key,{})
                client_orders.append([g['reference'],g['client'],*product_fields(a.get('productId')),entry.get('number') or a.get('number','Not recorded'),1,entry.get('allocatedAt') or g['date'],entry['status']])
        for r in data['receipts'].values():
            if r.get('openingBalance') or r['pool']=='Trident refurb stock' or r.get('referenceType','PO')!='PO' or not r.get('reference'):continue
            for key in r['assetIds']:
                a=data['assets'].get(key,{})
                original=next((m.get('number') for m in data['movements'] if m.get('receiptId')==r['id'] and m.get('assetId')==key and m['kind']=='Asset registered'),None)
                supplier_receipts.append([r['reference'],r.get('client',''),*product_fields(r['productId']),original or a.get('number','Not recorded'),1,r['date']])
            pending=max(0,r['quantity']-len(r['assetIds']))
            if pending:supplier_receipts.append([r['reference'],r.get('client',''),*product_fields(r['productId']),'Not assigned',pending,r['date']])
        return [
            ('Report guide',['Item','Explanation'],guide),
            ('Stock summary',['Product code','Product','Available to allocate','Allocated in store','Delivered','Awaiting asset numbers','Stock level','Minimum / shortfall'],summary),
            ('All stock asset numbers',['Product code','Product','Current asset number','Quantity','Stock stage','Stock type','Client / order / job','Previous asset numbers'],register),
            ('Unallocated stock - including deliveries',['Product code','Product','Asset number','Quantity','Delivery status'],unallocated),
            ('Current order allocations - including deliveries',['Product code','Product','Asset number','Quantity','Client','SO / PO','Job ID','Delivery status'],allocated),
            ('Client purchase orders received',['PO number','Client','Product code','Product','Asset at allocation','Quantity','Order date','Order status'],client_orders),
            ('Supplier purchase order receipts',['PO number','Supplier / source','Product code','Product','Asset at receipt','Quantity','Received date'],supplier_receipts),('Dated asset number history',['Current asset','Product code','Asset number','Valid from','Valid until','Asset added','Reference type','Reference'],[[a['number'],products[a['productId']]['code'],h['number'],h.get('validFrom') or 'Not recorded',h.get('validTo') or ('Current' if h['number']==a['number'] else 'Not recorded'),stock.label_added(h),h.get('referenceType') or 'Not recorded',stock.label_reference(h)] for a in assets for h in reversed(a['numberHistory'])]),*([('Recorded source PO / SO references',['Type','Reference','Product code','Product','Current asset','Quantity','Added date','Relationship'],[[r['type'],r['number'],products[a['productId']]['code'],description(a['productId']),a['number'],1,stock.label_added(a['numberHistory'][-1]),'Source note; precise event link unverified' if a['numberHistory'][-1].get('referenceContext') else 'Recorded added-to-stock reference'] for a in assets for r in a.get('sourceReferences',[])])] if data.get('sourceFormat')=='handoff_asset_register' else [])]
    if scope=='products':
        rows=[]
        for p in products.values():
            known=stock.quantity_known(data,p)
            rows.append([p['code'],description(p['id']),p['incomingQuantity'],p['refurbingQuantity']+sum(a['productId']==p['id'] and a['status']=='Awaiting new asset number' for a in assets),p['onHandQuantity'] if known else 'Not recorded',p['allocatedQuantity'],p['deliveredQuantity']])
        return [('All products',['Product code','Description','Incoming','Refurbishment','Stock on hand','Allocated','Delivered'],rows)]
    if scope=='history':
        return [('Movement history',['Date','Movement','Asset','Product','Client','SO / PO','Job ID','Notes'],[[m['date'],m['kind'],m.get('number',''),description(m.get('productId')),m.get('client',''),((m.get('referenceType') or 'PO')+' '+m.get('reference','')).strip() if m.get('reference') else '',m.get('jobId',''),m.get('notes','')] for m in reversed(data['movements'])])]
    if scope=='asset_history':
        return [('Current assets',['Current asset','Product','Status','Client','SO / PO','Job ID'],[[a['number'],description(a['productId']),a['status'],a.get('client',''),((a.get('referenceType') or 'PO')+' '+a.get('reference','')).strip() if a.get('reference') else '',a.get('jobId','')] for a in assets]),('Asset number validity',['Current asset','Asset number','Valid from','Valid until','Asset added','Reference type','Reference'],[[a['number'],h['number'],h.get('validFrom') or 'Not recorded',h.get('validTo') or ('Current' if h['number']==a['number'] else 'Not recorded'),stock.label_added(h),h.get('referenceType') or 'Not recorded',stock.label_reference(h)] for a in assets for h in reversed(a['numberHistory'])]),('Client allocations',['Current asset','Client','From','Until','SO / PO','Job ID','Status'],[[a['number'],h['client'],h.get('allocatedAt',''),h.get('returnedAt') or h.get('cancelledAt') or 'Current',h['referenceType']+' '+h['reference'],h['jobId'],h['status']] for a in assets for h in reversed(a['clientHistory'])])]
    matches={'intake':lambda a:a['status']=='Incoming','refurbing':lambda a:a['status'] in ('Refurbishing','Awaiting new asset number'),'refurbed':lambda a:stock.ready_refurb(a),'assets':lambda a:a['status'] in ('Available','Allocated'),'allocations':lambda a:a['status']=='Allocated','delivered':lambda a:a['status']=='With client'}
    rows=[[a['number'],description(a['productId']),a['status'],a.get('client',''),((a.get('referenceType') or 'PO')+' '+a.get('reference','')).strip() if a.get('reference') else '',a.get('jobId',''),a.get('allocatedAt',''),a.get('dispatchedAt',''),a.get('refurbTechnician',''),a.get('refurbCompletedAt','')] for a in assets if matches[scope](a)]
    result=[(SCOPES[scope],['Asset','Product','Status','Client','SO / PO','Job ID','Allocated','Delivered','Refurb tech','Refurbed'],rows)]
    if scope in ('assets','intake','refurbing'):
        pending=[[description(r['productId']),r['quantity']-len(r['assetIds']),r['date'],r.get('client',''),r.get('reference','')] for r in data['receipts'].values() if r['quantity']>len(r['assetIds']) and (bool(r.get('openingBalance')) if scope=='assets' else r['pool']=='Trident refurb stock' if scope=='refurbing' else r['pool']!='Trident refurb stock' and not r.get('openingBalance'))]
        result.append(('Opening stock awaiting numbers' if scope=='assets' else 'Refurbishment pickups awaiting numbers' if scope=='refurbing' else 'Incoming receipts awaiting numbers',['Product','Quantity','Date','Source','Reference'],pending))
    return result

def excel(report_tables):
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';tag=lambda name:'{'+ns+'}'+name
    ET.register_namespace('',ns)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        sheets=[];relationships=[];overrides=[]
        for index,(title,headers,rows) in enumerate(report_tables,1):
            name=re.sub(r'[\\/*?:\[\]]','-',title)[:31];sheets.append(f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>');relationships.append(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>');overrides.append(f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
            tree=ET.Element(tag('worksheet'));views=ET.SubElement(tree,tag('sheetViews'));view=ET.SubElement(views,tag('sheetView'),{'workbookViewId':'0'});ET.SubElement(view,tag('pane'),{'ySplit':'1','topLeftCell':'A2','activePane':'bottomLeft','state':'frozen'})
            cols=ET.SubElement(tree,tag('cols'))
            for c,header in enumerate(headers,1):ET.SubElement(cols,tag('col'),{'min':str(c),'max':str(c),'width':'100' if header=='Explanation' else '45' if header in ('Description','Product','Notes','Other stages','Client / order / job','Previous asset numbers') else '24','customWidth':'1'})
            sheet=ET.SubElement(tree,tag('sheetData'))
            for r,values in enumerate([headers,*rows],1):
                row=ET.SubElement(sheet,tag('row'),{'r':str(r)})
                for c,value in enumerate(values):
                    cell=ET.SubElement(row,tag('c'),{'r':chr(65+c)+str(r),'s':'1' if r==1 else '0'})
                    if type(value) in (int,float):ET.SubElement(cell,tag('v')).text=str(value)
                    else:
                        cell.set('t','inlineStr');t=ET.SubElement(ET.SubElement(cell,tag('is')),tag('t'));t.text=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(value or ''))[:32767]
            ET.SubElement(tree,tag('autoFilter'),{'ref':f'A1:{chr(64+len(headers))}{max(1,len(rows)+1)}'})
            z.writestr(f'xl/worksheets/sheet{index}.xml',ET.tostring(tree,encoding='utf-8',xml_declaration=True))
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join(overrides)+'</Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml','<workbook xmlns="'+ns+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(sheets)+'</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(relationships)+'<Relationship Id="styles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/styles.xml','<styleSheet xmlns="'+ns+'"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF17365F"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    return out.getvalue()

def pdf(report_tables,title,date):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4,landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,KeepTogether
    page_size=landscape(A4) if title==SCOPES['accessable_soh'] else A4
    out=io.BytesIO();doc=SimpleDocTemplate(out,pagesize=page_size,rightMargin=28,leftMargin=28,topMargin=32,bottomMargin=36,title='Trident Stock - '+title,author='Trident Dashboard')
    styles={name:ParagraphStyle(name,fontName='Helvetica-Bold' if name!='body' else 'Helvetica',fontSize=size,leading=size+3,textColor=colors.HexColor('#17365f')) for name,size in [('title',17),('heading',11),('body',7.5),('header',7.5)]};styles['header'].textColor=colors.white
    def para(value,style='body'):
        v=str(value) if value is not None else 'Not recorded'
        for char in ('—','–','→'):v=v.replace(char,'-')
        return Paragraph(escape(v).replace('\n','<br/>'),styles[style])
    story=[para('Trident Dashboard - Stock report','title'),Spacer(1,6),para(title+' | '+date+' | Auckland time'),Spacer(1,16)]
    styles['heading'].spaceAfter=6
    for label,headers,rows in report_tables:
        story.append(para(label,'heading'))
        if not rows:story.extend([para('No records in this section.'),Spacer(1,14)]);continue
        # Wide asset detail reports become readable per-item cards in portrait.
        if len(headers)>8:
            for values in rows:
                lines=[[para(headers[i],'heading'),para(v)] for i,v in enumerate(values)]
                t=Table(lines,colWidths=[110,doc.width-110],hAlign='LEFT',splitInRow=1);t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#eef3f9')),('LINEBELOW',(0,-1),(-1,-1),.4,colors.HexColor('#cad7e7')),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6)]));story.extend([t,Spacer(1,12)])
        else:
            weights=[4 if h=='Explanation' else 2.8 if h in ('Description','Product','Notes') else 1.35 if h in ('Client','SO / PO','Movement','Product code') else 1 for h in headers];total=sum(weights)
            t=Table([[para(h,'header') for h in headers],*[[para(v) for v in r] for r in rows]],colWidths=[doc.width*w/total for w in weights],repeatRows=1,splitInRow=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#17365f')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f2f5fa')]),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#d6e0ec')),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));
            if label=='Stock summary':
                for row_index,row in enumerate(rows,1):
                    shade={'Out of stock':'#fde8e7','Low stock':'#fff0d5','Quantity needs review':'#fff6d9','Minimum not set':'#eef3f9','Stock available':'#e2f2e8'}[row[6]]
                    t.setStyle(TableStyle([('BACKGROUND',(6,row_index),(6,row_index),colors.HexColor(shade))]))
            story.extend([t,Spacer(1,14)])
    if story and isinstance(story[-1],Spacer):story.pop()
    def footer(canvas,document):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#627a93'));canvas.drawString(28,19,'Trident Dashboard');canvas.drawRightString(page_size[0]-28,19,f'Page {document.page}');canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer);return out.getvalue()

def asset_detail_pdf(state,asset_id):
    """Black landscape label in the top half of A4; overflow keeps the lower half blank."""
    from pathlib import Path
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
    data=stock.read(state)
    if not isinstance(asset_id,str) or asset_id not in data['assets']:raise Problem(404,'This asset no longer exists. Refresh stock and try again.')
    asset=data['assets'][asset_id];product=data['products'].get(asset['productId'],{})
    # The first label is the oldest known number. A later relabel date is not
    # evidence of when the physical item was originally added to stock.
    first=(asset.get('numberHistory') or [{}])[0]
    fonts=Path(__file__).parent/'fonts'
    for name,file in [('TridentAsset','LiberationSans-Regular.ttf'),('TridentAssetBold','LiberationSans-Bold.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(fonts/file)))
    styles={k:ParagraphStyle('asset-'+k,fontName='TridentAsset' if k=='body' else 'TridentAssetBold',fontSize=size,leading=size+4,textColor=colors.black) for k,size in [('heading',17),('identity',36),('body',10),('label',8.5)]}
    def para(value,style='body'):
        text=str(value).strip() if value is not None else ''
        text=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',text) or 'Not recorded'
        return Paragraph(escape(text).replace('\n','<br/>'),styles[style])
    def dated(value):
        try:return dt.date.fromisoformat(value).strftime('%d %b %Y')
        except (TypeError,ValueError):return value or 'Not recorded'
    added=dated(first.get('addedAt')) if first.get('addedAt') else stock.label_added(first)
    reference=lambda value:((value.get('referenceType') or 'Reference')+' '+value['reference']) if value.get('reference') else 'Not recorded'
    rows=[('Product code',product.get('code')),('Available','Yes' if asset['status']=='Available' else 'No'),('Status',asset['status']),('Location',asset.get('location')),('Stock type',asset.get('pool')),('Added to stock',added),('Added reference',stock.label_reference(first)),('Client',asset.get('client')),('Current SO / PO',reference(asset)),('Trident job ID',asset.get('jobId'))]
    for label,key in [('Allocated from','allocatedAt'),('Delivered','dispatchedAt'),('Refurb completed','refurbCompletedAt')]:
        if asset.get(key):rows.append((label,dated(asset[key])))
    for label,key in [('Refurb technician','refurbTechnician'),('Collection client','pickupClient'),('Collection reference','pickupReference'),('Collection job ID','pickupJobId')]:
        if asset.get(key):rows.append((label,asset[key]))
    if asset.get('sourceReferences'):rows.append(('Source references','\n'.join(((r.get('type') or 'Reference')+' '+r['number']) for r in asset['sourceReferences'] if r.get('number'))))
    date=dt.datetime.now(ZoneInfo('Pacific/Auckland')).strftime('%d %b %Y, %I:%M %p')
    out=io.BytesIO();cut=A4[1]/2
    doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=28,rightMargin=28,topMargin=26,bottomMargin=cut+34,title='Asset '+asset['number'],author='Trident Dashboard')
    # Both identifiers use the same size. Long codes may wrap, rather than being
    # clipped or losing their distinguishing suffix. Ordinary numbers stay large.
    widest=max(pdfmetrics.stringWidth(str(v or 'Not recorded'),'TridentAssetBold',36) for v in (asset['number'],product.get('code')))
    size=max(18,min(36,36*(doc.width/2-22)/max(1,widest)))
    styles['identity'].fontSize=size;styles['identity'].leading=size+4
    identities=Table([[para('ASSET NUMBER','label'),para('PRODUCT CODE','label')],[para(asset['number'],'identity'),para(product.get('code'),'identity')]],colWidths=[doc.width/2]*2,hAlign='LEFT',splitInRow=1)
    identities.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('LEFTPADDING',(1,0),(1,-1),16),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,-1),(-1,-1),.5,colors.black)]))
    details=rows[1:];left,right=details[:5],details[5:];pairs=[];rules=[]
    for index in range(max(len(left),len(right))):
        cells=[]
        for part,offset in ((left,0),(right,3)):
            if offset:cells.append('')
            if index<len(part):
                label,value=part[index];cells.extend([para(label,'label'),para(value)])
                rules.append(('LINEBELOW',(offset,index),(offset+1,index),.35,colors.black))
            else:cells.extend(['',''])
        pairs.append(cells)
    half=(doc.width-24)/2
    table=Table(pairs,colWidths=[105,half-105,24,105,half-105],hAlign='LEFT',splitInRow=1,minRowHeights=[31]*len(pairs))
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),*rules]))
    def footer(canvas,document):
        canvas.saveState();canvas.setStrokeColor(colors.black);canvas.setFillColor(colors.black)
        canvas.setLineWidth(.35);canvas.setDash(3,3);canvas.line(20,cut,A4[0]-20,cut)
        canvas.setFont('TridentAsset',6.5)
        canvas.drawString(28,cut+18,'Printed '+date+' NZ time')
        canvas.drawRightString(A4[0]-28,cut+18,'Top half of A4 | '+str(document.page));canvas.restoreState()
    story=[para(product.get('description'),'heading'),Spacer(1,12),identities,Spacer(1,12),table]
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    name=re.sub(r'[^A-Za-z0-9_-]+','-',asset['number']).strip('-')[:80] or 'details'
    return {'name':'Trident-asset-'+name+'.pdf','mime':'application/pdf','file':base64.b64encode(out.getvalue()).decode()}

def create(state,p,template=None):
    scope=p.get('scope');format=p.get('format')
    if scope=='asset_detail':
        if format!='pdf':raise Problem(400,'Asset details are available as a PDF.')
        return asset_detail_pdf(state,p.get('assetId'))
    if format not in ('xlsx','pdf') or scope not in ('workbook',*SCOPES):raise Problem(400,'Choose a valid report and format.')
    date=dt.datetime.now(ZoneInfo('Pacific/Auckland')).date().isoformat()
    if scope=='stock_take':
        import stock_take
        raw=stock_take.excel(state,date) if format=='xlsx' else stock_take.pdf(state,date)
    elif scope=='standard_soh':
        import stock_standard
        raw=stock_standard.excel(state,date) if format=='xlsx' else stock_standard.pdf(state,date)
    elif scope=='workbook':
        if format!='xlsx':raise Problem(400,'The original workbook layout is available in Excel. Choose a report section for PDF.')
        raw=stock_import.export(state,template)
    else:
        report_tables=tables(state,scope);raw=excel(report_tables) if format=='xlsx' else pdf(report_tables,SCOPES[scope],date)
    return {'name':f"{SCOPES[scope] if scope in ('stock_take','standard_soh','accessable_soh') else 'Trident-stock-'+scope}-{date}.{format}",'mime':'application/pdf' if format=='pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','file':base64.b64encode(raw).decode()}
