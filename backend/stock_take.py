"""Read-only, print-friendly physical stock take worksheets."""
import io,zipfile,copy,math
from pathlib import Path
from xml.etree import ElementTree as ET
import stock,stock_standard

TITLE='Stock take Sheet'
QHEAD=['Product code','Condition','Description','Asset numbers','Expected','Counted','Difference','Notes']
AHEAD=['Product code','Condition','Description','Current asset number','Expected stage / location','Found','Actual location / discrepancies']
ONSITE=('Available','Allocated','Incoming','Refurbishing','Awaiting new asset number','Repair')

def rows(state):
    snap=stock_standard.snapshot(state);quantities=[];assets=[]
    for p,items,known in snap['groups']:
        pending=sum(max(0,r['quantity']-len(r['assetIds'])) for r in snap['data']['receipts'].values() if r['productId']==p['id'] and not r.get('openingBalance'))
        other=pending+sum(a['status'] in ONSITE and a['status'] not in ('Available','Allocated') for a in items)
        quantities.append([p['code'],stock_standard.condition(p),p['description'],'\n'.join(a['number'] for a in items if a['status'] in ONSITE),p['onHandQuantity']+other if known else 'Not recorded','','',''])
        for a in items:
            if a['status'] not in ONSITE:continue
            label=a['number']+('\nEarlier: '+', '.join(a.get('previousNumbers',[])) if a.get('previousNumbers') else '')
            assets.append([p['code'],stock_standard.condition(p),p['description'],label,a['status']+'\n'+(a.get('location') or 'Location not recorded'),'[ ]',''])
    return quantities,assets

def excel(state,date):
    q=stock_standard.q;cell=stock_standard.cell;col=stock_standard.col
    quantities,assets=rows(state)
    checklist=[[row[0]+' '+row[1]+'\n'+row[2],row[3],row[4],row[5],row[6]] for row in assets]
    asset_headers=['Product / condition','Current asset number','Expected stage / location','Found','Actual location / discrepancies']
    asset_rows=[*checklist,['UNLISTED ASSETS / CORRECTIONS','','','',''],*([['']*5]*10)]
    with zipfile.ZipFile(Path(__file__).with_name('stock_take_template.xlsx')) as z:content={n:z.read(n) for n in z.namelist()}
    styles=ET.fromstring(content['xl/styles.xml']);formats=styles.find(q('cellXfs'))
    tilted=copy.deepcopy(formats[9]);alignment=tilted.find(q('alignment'))
    if alignment is None:alignment=ET.SubElement(tilted,q('alignment'))
    alignment.set('textRotation','45');alignment.set('wrapText','1');alignment.set('vertical','center');tilted.set('applyAlignment','1')
    asset_style=len(formats);formats.append(tilted);formats.set('count',str(len(formats)))
    content['xl/styles.xml']=ET.tostring(styles,encoding='utf-8',xml_declaration=True)
    for i,(headers,values) in enumerate([(QHEAD,quantities),(asset_headers,asset_rows)],1):
        key=f'xl/worksheets/sheet{i}.xml';tree=ET.fromstring(content[key]);sheet=tree.find(q('sheetData'));old={int(r.get('r')):r for r in sheet}
        header_styles=[int(c.get('s','0')) for c in old[7]];body_styles=[int(c.get('s','0')) for c in old[8]]
        for r in list(sheet):
            if int(r.get('r'))>=7:sheet.remove(r)
        summary='Snapshot '+date+' (Auckland). Count physically at Trident. Client-held and retired assets are excluded.'
        for number,text in [(1,'Trident Community Equipment - '+TITLE),(2,summary),(5,'Count all stock at Trident, including receiving/workshop and allocated items still onsite. Not recorded means unknown, not zero.')]:
            row=old[number];style=int(row[0].get('s','0'));row[:]=[cell('A'+str(number),text,style)];row.set('ht','36' if number in (2,5) else '26');row.set('customHeight','1')
        for j,values_row in enumerate([headers,*values],7):
            row=ET.SubElement(sheet,q('row'),{'r':str(j),'ht':str(32 if j==7 else 56 if i==2 else max(54,min(160,32+18*len(str(values_row[3]).splitlines())))),'customHeight':'1'})
            for k,value in enumerate(values_row,1):row.append(cell(col(k)+str(j),value,asset_style if i==1 and j>7 and k==4 else (header_styles if j==7 else body_styles)[min(k-1,len(header_styles if j==7 else body_styles)-1)]))
        if i==2:
            section_row=8+len(assets)
            for row in sheet:
                if int(row.get('r'))==section_row:row.set('ht','26')
            merge=tree.find(q('mergeCells'))
            ET.SubElement(merge,q('mergeCell'),{'ref':f'A{section_row}:E{section_row}'})
            merge.set('count',str(len(merge)))
        for merged in tree.findall(q('mergeCells')+'/'+q('mergeCell')):
            ref=merged.get('ref');end=ref.split(':')[-1];merged.set('ref',ref.split(':')[0]+':'+col(len(headers))+''.join(c for c in end if c.isdigit()))
        columns=tree.find(q('cols'))
        if i==1:
            columns[:]=[]
            for k,width in enumerate([10,12,36,38,9,9,10,30],1):ET.SubElement(columns,q('col'),{'min':str(k),'max':str(k),'width':str(width),'customWidth':'1'})
        dim=tree.find(q('dimension'))
        if dim is not None:dim.set('ref',f'A1:{col(len(headers))}{7+len(values)}')
        for name in ('autoFilter','pageMargins','pageSetup','headerFooter'):
            n=tree.find(q(name))
            if n is not None:tree.remove(n)
        ET.SubElement(tree,q('pageMargins'),{'left':'.25','right':'.25','top':'.35','bottom':'.45','header':'.15','footer':'.2'})
        ET.SubElement(tree,q('pageSetup'),{'paperSize':'9','orientation':'landscape','fitToWidth':'1','fitToHeight':'0'})
        pr=tree.find(q('sheetPr'))
        if pr is None:pr=ET.Element(q('sheetPr'));tree.insert(0,pr)
        setup=pr.find(q('pageSetUpPr'))
        if setup is None:setup=ET.SubElement(pr,q('pageSetUpPr'))
        setup.set('fitToPage','1')
        footer=ET.SubElement(tree,q('headerFooter'));ET.SubElement(footer,q('oddFooter')).text='&LTrident - Stock take Sheet&CCount date: ______________&RPage &P of &N'
        content[key]=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
    book=ET.fromstring(content['xl/workbook.xml']);names=book.find(q('definedNames'))
    if names is None:
        names=ET.Element(q('definedNames'));book.insert(list(book).index(book.find(q('sheets')))+1,names)
    for i,(name,count,last) in enumerate([('Quantity count',len(quantities),'H'),('Asset checklist',len(asset_rows),'E')]):
        ET.SubElement(names,q('definedName'),{'name':'_xlnm.Print_Area','localSheetId':str(i)}).text=f"'{name}'!$A$1:${last}${7+count}"
        ET.SubElement(names,q('definedName'),{'name':'_xlnm.Print_Titles','localSheetId':str(i)}).text=f"'{name}'!$1:$7"
    content['xl/workbook.xml']=ET.tostring(book,encoding='utf-8',xml_declaration=True)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for key,value in content.items():z.writestr(key,value)
    return out.getvalue()

def pdf(state,date):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4,landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Flowable
    from reportlab.graphics.shapes import Drawing,Rect
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from xml.sax.saxutils import escape
    quantities,assets=rows(state);out=io.BytesIO();page=landscape(A4)
    doc=SimpleDocTemplate(out,pagesize=page,leftMargin=24,rightMargin=24,topMargin=24,bottomMargin=32,title=TITLE,author='Trident Community Equipment')
    body=ParagraphStyle('body',fontName='Helvetica',fontSize=8,leading=10,textColor=colors.HexColor('#172C46'))
    heading=ParagraphStyle('heading',parent=body,fontName='Helvetica-Bold',fontSize=14,leading=18,spaceAfter=6)
    bold=ParagraphStyle('bold',parent=body,fontName='Helvetica-Bold')
    compact_header=ParagraphStyle('compact-header',parent=bold,fontSize=7.2,leading=9)
    def para(v,style=body):return Paragraph(escape(str(v).replace('—','-').replace('–','-').replace('‑','-')).replace('\n','<br/>'),style)
    class AssetBlocks(Flowable):
        def __init__(self,labels,width):
            Flowable.__init__(self);self.width=width;self.blocks=[];x=0;y=0;line=0
            for label in labels:
                label=str(label);font=min(7.5,70/max(1,stringWidth(label,'Helvetica',1)));w=max(30,stringWidth(label,'Helvetica',font)+10);h=14;bound=(w+h)/math.sqrt(2)
                if x and x+bound>width:y+=line+5;x=0;line=0
                self.blocks.append((label,font,w,h,x,bound,y));x+=bound+6;line=max(line,bound)
            self.height=y+line+4
        def draw(self):
            canvas=self.canv
            for label,font,w,h,x,bound,y in self.blocks:
                canvas.saveState();canvas.translate(x+bound/2,self.height-y-bound/2-2);canvas.rotate(45)
                canvas.setStrokeColor(colors.HexColor('#8295AB'));canvas.setLineWidth(.5);canvas.setFillColor(colors.HexColor('#F3F6FA'));canvas.roundRect(-w/2,-h/2,w,h,2,stroke=1,fill=1)
                canvas.setFillColor(colors.HexColor('#172C46'));canvas.setFont('Helvetica',font);canvas.drawCentredString(0,-font*.33,label);canvas.restoreState()
    def table(headers,values,widths,height=34):
        def value(v):
            if isinstance(v,Flowable):return v
            if v=='[ ]':
                d=Drawing(12,12);d.add(Rect(1,1,10,10,fillColor=None,strokeColor=colors.black,strokeWidth=.7));return d
            return para(v)
        t=Table([[para(h,compact_header if h in ('Expected','Counted','Difference') else bold) for h in headers],*[[value(v) for v in row] for row in values]],colWidths=widths,minRowHeights=[30]+[height]*len(values),repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E8EDF2')),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#BFC8D3')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));return t
    story=[para('Trident Community Equipment - '+TITLE,heading),para('Snapshot '+date+' (Auckland time)    |    Technician: ____________________    Count date: ______________'),Spacer(1,6),para('Checked by: ____________________    Signature: ____________________    Review date: ______________'),Spacer(1,6),para('Count stock in store, receiving and workshop, including allocated stock still onsite. Client-held and retired assets are excluded. Not recorded means unknown. Difference = Counted - Expected. Count each product/condition once; continued rows only extend its asset list.'),Spacer(1,8),para('1. Quantity count',heading)]
    widths=[44,52,176,255,43,41,47,doc.width-658]
    grid=[]
    for row in quantities:
        labels=row[3].splitlines();chunks=[labels[i:i+12] for i in range(0,len(labels),12)] or [[]]
        for index,chunk in enumerate(chunks):
            part=list(row)
            if index:part[4]='';part[5]='See first row';part[7]='Asset list continued'
            part[3]=AssetBlocks(chunk,widths[3]-10) if chunk else para('No recorded asset numbers')
            grid.append(part)
    story.append(table(QHEAD,grid,widths,48))
    story.extend([PageBreak(),para('2. Asset checklist',heading),para('Tick Found after checking the physical label. Earlier numbers identify the same item. Record missing, damaged or moved assets below.'),Spacer(1,8)])
    checklist=[[row[0]+' '+row[1]+'\n'+row[2],row[3],row[4],row[5],row[6]] for row in assets]
    story.append(table(['Product / condition','Current asset number','Expected stage / location','Found','Actual location / discrepancies'],checklist,[240,110,140,38,doc.width-528],36))
    story.extend([PageBreak(),para('3. Unlisted assets / corrections',heading),para('Record unlisted stock or label corrections. Include these units in the counted quantities where applicable.'),Spacer(1,8),table(QHEAD,[['']*8 for _ in range(8)],widths,43)])
    def footer(canvas,document):
        canvas.setFillColor(colors.HexColor('#52657A'));canvas.setFont('Helvetica',8);canvas.drawString(24,16,'Technician: ____________________    Count date: ____________________');canvas.drawRightString(page[0]-24,16,f'Stock take Sheet | Page {document.page}')
    doc.build(story,onFirstPage=footer,onLaterPages=footer);return out.getvalue()
