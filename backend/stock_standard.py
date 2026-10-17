"""Template-inspired stock snapshot: chart, quantities, then current asset labels."""
import io, math, re, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
import stock

TITLE='Standard SOH Accessable report'
COLORS=('3676C8','E8B337','8A9AAE')
QUANTITY_HEADERS=['Product code','Condition','Description','Incoming','Refurbishment','Available','Allocated in store','Stock on hand','Delivered','Minimum','Shortfall']
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
CNS='http://schemas.openxmlformats.org/drawingml/2006/chart'
ANS='http://schemas.openxmlformats.org/drawingml/2006/main'
def q(name):return '{'+NS+'}'+name
def col(index):
    value=''
    while index:index,n=divmod(index-1,26);value=chr(65+n)+value
    return value
def clean(value):return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(value))[:32767]
def condition(p):return p.get('condition') or 'Unspecified'

def snapshot(state):
    data=stock.read(state)
    products=sorted(data['products'].values(),key=lambda p:(p['code'].casefold(),{'NEW':0,'REFURB':1,'':-1}.get(p.get('condition',''),2)))
    assets=sorted(data['assets'].values(),key=lambda a:a['number'].casefold())
    quantities=[];groups=[];chart={}
    for p in products:
        items=[a for a in assets if a['productId']==p['id']]
        known=stock.quantity_known(data,p);minimum=p.get('minimumStock')
        quantities.append([p['code'],condition(p),p['description'],p['incomingQuantity'],p['refurbingQuantity']+sum(a['status']=='Awaiting new asset number' for a in items),p['availableQuantity'] if known else 'Not recorded',p['allocatedQuantity'],p['onHandQuantity'] if known else 'Not recorded',p['deliveredQuantity'],minimum if minimum is not None else 'Not set',max(0,minimum-p['availableQuantity']) if minimum is not None and known else 'Not recorded' if minimum is not None else 'Not set'])
        groups.append((p,items,known))
        if known and p['onHandQuantity']:
            group=chart.setdefault(p['code'],{'code':p['code'],'description':p['description'],'values':[0,0,0]})
            group['values'][{'NEW':0,'REFURB':1}.get(p.get('condition'),2)]+=p['onHandQuantity']
    chart=sorted(chart.values(),key=lambda g:g['code'].casefold())
    return {'data':data,'groups':groups,'quantities':quantities,'chart':chart,'unknown':sum(not known for _,_,known in groups),'onHand':sum(p['onHandQuantity'] for p in products),'available':sum(p['availableQuantity'] for p in products),'allocated':sum(p['allocatedQuantity'] for p in products),'delivered':sum(p['deliveredQuantity'] for p in products)}

def asset_cell(a):
    history=a['numberHistory'];current=history[-1]
    lines=[a['number'],'Added: '+stock.label_added(current),'Status: '+a['status']]
    if current.get('reference'):lines.append(stock.label_reference(current))
    if a.get('reference'):lines.append('Client order: '+a.get('referenceType','PO')+' '+a['reference'])
    if a.get('client'):lines.append('Client: '+a['client'])
    for h in reversed(history[:-1]):
        lines.append('Earlier: '+h['number']+' | '+(h.get('validFrom') or 'Start not recorded')+' to '+(h.get('validTo') or 'End not recorded'))
        if h.get('reference'):lines.append(stock.label_reference(h))
    return '\n'.join(lines)

def cell(address,value,style=0):
    c=ET.Element(q('c'),{'r':address,'s':str(style)})
    if type(value) in (int,float):ET.SubElement(c,q('v')).text=str(value)
    else:
        c.set('t','inlineStr');ET.SubElement(ET.SubElement(c,q('is')),q('t')).text=clean(value)
    return c

def chart_xml(raw,rows,start):
    tree=ET.fromstring(raw);c=lambda n:'{'+CNS+'}'+n
    bar=tree.find('.//'+c('barChart'))
    if bar is None:raise ValueError('The standard report requires a native bar chart.')
    bar.find(c('barDir')).set('val','bar')
    grouping=bar.find(c('grouping'))
    if grouping is None:grouping=ET.SubElement(bar,c('grouping'))
    grouping.set('val','stacked')
    overlap=bar.find(c('overlap'))
    if overlap is None:overlap=ET.SubElement(bar,c('overlap'))
    overlap.set('val','100')
    for i,ser in enumerate(bar.findall(c('ser'))):
        for name in ('cat','val','tx'):
            old=ser.find(c(name))
            if old is not None:ser.remove(old)
        tx=ET.SubElement(ser,c('tx'));ET.SubElement(tx,c('v')).text=['NEW','REFURB','Unspecified'][i]
        cat=ET.SubElement(ET.SubElement(ser,c('cat')),c('strRef'));ET.SubElement(cat,c('f')).text=f"'Stock overview'!$A${start+1}:$A${start+max(1,len(rows))}"
        cache=ET.SubElement(cat,c('strCache'));ET.SubElement(cache,c('ptCount'),{'val':str(len(rows))})
        values=ET.SubElement(ET.SubElement(ser,c('val')),c('numRef'));letter=chr(66+i);ET.SubElement(values,c('f')).text=f"'Stock overview'!${letter}${start+1}:${letter}${start+max(1,len(rows))}"
        nums=ET.SubElement(values,c('numCache'));ET.SubElement(nums,c('formatCode')).text='0';ET.SubElement(nums,c('ptCount'),{'val':str(len(rows))})
        for j,row in enumerate(rows):
            ET.SubElement(ET.SubElement(cache,c('pt'),{'idx':str(j)}),c('v')).text=row[0]
            ET.SubElement(ET.SubElement(nums,c('pt'),{'idx':str(j)}),c('v')).text=str(row[i+1])
    for axis in tree.findall('.//'+c('valAx')):
        unit=axis.find(c('majorUnit'))
        if unit is None:unit=ET.SubElement(axis,c('majorUnit'))
        unit.set('val',str(max(1,math.ceil(max((sum(row[1:]) for row in rows),default=1)/8))))
    for axis in tree.findall('.//'+c('catAx')):
        orientation=axis.find(c('scaling')+'/'+c('orientation'))
        if orientation is not None:orientation.set('val','maxMin')
    order=['idx','order','tx','spPr','invertIfNegative','pictureOptions','dPt','dLbls','trendline','errBars','cat','val','shape','extLst']
    for ser in bar.findall(c('ser')):ser[:]=sorted(ser,key=lambda e:order.index(e.tag.split('}')[-1]) if e.tag.split('}')[-1] in order else 99)
    order=['barDir','grouping','varyColors','ser','dLbls','gapWidth','gapDepth','overlap','serLines','axId','extLst'];bar[:]=sorted(bar,key=lambda e:order.index(e.tag.split('}')[-1]) if e.tag.split('}')[-1] in order else 99)
    return ET.tostring(tree,encoding='utf-8',xml_declaration=True)

def excel(state,date):
    snap=snapshot(state);chart_rows=[[g['code']+' - '+g['description'],*g['values']] for g in snap['chart']]
    max_assets=max(7,max((len(items) for _,items,_ in snap['groups']),default=0))
    asset_headers=['Product code','Condition','Description','Numbered assets',*[f'Asset {i+1} / added to stock' for i in range(max_assets)]]
    asset_rows=[[p['code'],condition(p),p['description'],len(items) if known else 'Not recorded',*[asset_cell(a) for a in items]] for p,items,known in snap['groups']]
    template=Path(__file__).with_name('standard_soh_template.xlsx').read_bytes()
    content={}
    with zipfile.ZipFile(io.BytesIO(template)) as z:
        content={i.filename:z.read(i.filename) for i in z.infolist()}
    for i,(headers,rows,start) in enumerate([(['Product','NEW','REFURB','Unspecified'],chart_rows,36),(QUANTITY_HEADERS,snap['quantities'],6),(asset_headers,asset_rows,6)],1):
        key=f'xl/worksheets/sheet{i}.xml';tree=ET.fromstring(content[key]);sheet=tree.find(q('sheetData'))
        old={int(row.get('r')):row for row in sheet}
        style=lambda r,c:next((int(x.get('s','0')) for x in old[r] if x.get('r')==col(c)+str(r)),0)
        header_styles=[style(start,j+1) for j in range(min(len(headers),11))]
        body_styles=[style(start+1,j+1) for j in range(min(len(headers),11))]
        new_style=style(start+2,2);refurb_style=style(start+3,2)
        for row in list(sheet):
            if int(row.get('r'))>=start:sheet.remove(row)
        # All placeholder content is replaced on every export.
        for number,value in [(1,'Trident Community Equipment'),(2,TITLE),(3,'As at '+date+' (Auckland time)'),(4,f"{snap['onHand']} on hand | {snap['available']} available | {snap['allocated']} allocated in store | {snap['delivered']} delivered. {snap['unknown']} product/condition rows have unconfirmed quantities.")]:
            row=old[number];sample=row[0];row.clear();row.set('r',str(number));row.append(cell('A'+str(number),value,int(sample.get('s','0'))))
        for j,values in enumerate([headers,*rows],start):
            r=ET.SubElement(sheet,q('row'),{'r':str(j),'ht':str(34 if j==start or i==2 else min(250,max(44,max((str(v).count('\n')+1)*13 for v in values)))),'customHeight':'1'})
            for k,value in enumerate(values,1):
                styles=header_styles if j==start else body_styles;st=styles[min(k-1,len(styles)-1)]
                if j>start and i>1 and k==2:st=new_style if value=='NEW' else refurb_style if value=='REFURB' else st
                r.append(cell(col(k)+str(j),value,st))
        dimension=tree.find(q('dimension'))
        if dimension is not None:dimension.set('ref',f'A1:{col(max(11,len(headers)))}{start+len(rows)}')
        for name in ('autoFilter','pageSetup'):
            node=tree.find(q(name))
            if node is not None:tree.remove(node)
        if i>1:
            af=ET.Element(q('autoFilter'),{'ref':f'A{start}:{col(len(headers))}{start+len(rows)}'});tree.insert(list(tree).index(sheet)+1,af)
        setup=ET.Element(q('pageSetup'),{'orientation':'landscape','paperSize':'9','fitToWidth':'1','fitToHeight':'0'})
        drawing=tree.find(q('drawing'));tree.insert(list(tree).index(drawing) if drawing is not None else len(tree),setup)
        cols=tree.find(q('cols'))
        if i==3 and max_assets>7:
            ET.SubElement(cols,q('col'),{'min':'12','max':str(4+max_assets),'width':'28','customWidth':'1'})
        content[key]=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
    chart_key=next(k for k in content if re.fullmatch(r'xl/(?:drawings/)?charts/chart\d+\.xml',k))
    content[chart_key]=chart_xml(content[chart_key],chart_rows,36)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for key,value in content.items():z.writestr(key,value)
    return out.getvalue()

def pdf(state,date):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4,landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
    from reportlab.graphics.shapes import Drawing,Rect,String,Line
    snap=snapshot(state);out=io.BytesIO();page=landscape(A4)
    doc=SimpleDocTemplate(out,pagesize=page,rightMargin=28,leftMargin=28,topMargin=28,bottomMargin=32,title=TITLE,author='Trident Community Equipment')
    body=ParagraphStyle('body',fontName='Helvetica',fontSize=8,leading=11,textColor=colors.HexColor('#17365F'))
    heading=ParagraphStyle('heading',parent=body,fontName='Helvetica-Bold',fontSize=12,leading=16,spaceAfter=8)
    title=ParagraphStyle('title',parent=heading,fontSize=19,leading=23)
    white=ParagraphStyle('white',parent=body,fontName='Helvetica-Bold',textColor=colors.white)
    def para(v,style=body):return Paragraph(escape(str(v)).replace('\n','<br/>'),style)
    def table(headers,rows,widths):
        t=Table([[para(h,white) for h in headers],*[[para(v) for v in row] for row in rows]],colWidths=widths,repeatRows=1,hAlign='LEFT',splitInRow=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#17365F')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F2F6FA')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#CAD7E7'))]));
        if 'Condition' in headers:
            ci=headers.index('Condition')
            for ri,row in enumerate(rows,1):
                if row[ci] in ('NEW','REFURB'):t.setStyle(TableStyle([('BACKGROUND',(ci,ri),(ci,ri),colors.HexColor('#E5EFFF' if row[ci]=='NEW' else '#FFF0B8'))]))
        return t
    story=[para('Trident Community Equipment',title),para(TITLE+' | '+date+' | Auckland time'),Spacer(1,12)]
    story.extend([table(['Stock on hand','Available','Allocated in store','Delivered'],[[snap['onHand'],snap['available'],snap['allocated'],snap['delivered']]],[doc.width/4]*4),Spacer(1,14)])
    for start in range(0,max(1,len(snap['chart'])),16):
        if start:story.extend([PageBreak(),para('Stock on hand by product and condition (continued)',heading)])
        else:story.append(para('Stock on hand by product and condition',heading))
        groups=snap['chart'][start:start+16];h=max(150,len(groups)*19+55);drawing=Drawing(doc.width,h);left=305;plot=doc.width-left-32
        maximum=max((sum(g['values']) for g in snap['chart']),default=1);axis_max=max(1,maximum);step=max(1,math.ceil(axis_max/8))
        for n in range(0,axis_max+1,step):
            x=left+plot*n/axis_max;drawing.add(Line(x,20,x,h-25,strokeColor=colors.HexColor('#DFE6EE'),strokeWidth=.5));drawing.add(String(x,6,str(n),fontName='Helvetica',fontSize=8,fillColor=colors.HexColor('#62758C')))
        for j,g in enumerate(groups):
            y=h-38-j*19;label=g['code']+'  '+g['description'];label=label if len(label)<=58 else label[:55]+'...'
            drawing.add(String(0,y+2,label,fontName='Helvetica',fontSize=8,fillColor=colors.HexColor('#17365F')))
            x=left
            for n,color in zip(g['values'],COLORS):
                if n:drawing.add(Rect(x,y,plot*n/axis_max,12,strokeColor=None,fillColor=colors.HexColor('#'+color)));x+=plot*n/axis_max
            drawing.add(String(x+5,y+2,str(sum(g['values'])),fontName='Helvetica-Bold',fontSize=8,fillColor=colors.HexColor('#17365F')))
        for j,label in enumerate(('NEW','REFURB','Unspecified')):
            x=left+j*110;drawing.add(Rect(x,h-12,8,8,fillColor=colors.HexColor('#'+COLORS[j]),strokeColor=None));drawing.add(String(x+13,h-11,label,fontName='Helvetica',fontSize=8,fillColor=colors.HexColor('#17365F')))
        story.extend([drawing,Spacer(1,8)])
        story.append(para(f"Only products with recorded stock on hand are charted. {snap['unknown']} product/condition rows have unconfirmed quantities. Stock on hand includes allocated units still in store; delivered items are excluded."))
    story.extend([PageBreak(),para('Stock quantities',heading),para('Each row is one product and condition. Available stock excludes allocated orders. Minimums come from Stock settings; shortfall is the available quantity needed to reach the minimum. Unconfirmed quantities remain Not recorded.'),Spacer(1,10)])
    weights=[50,58,190,53,52,51,60,52,50,48,53];scale=doc.width/sum(weights)
    story.append(table(['Product code','Condition','Description','Incoming','Refurb','Available','Allocated in store','Stock on hand','Delivered','Minimum','Shortfall'],snap['quantities'],[x*scale for x in weights]))
    def footer(canvas,document):
        canvas.setFillColor(colors.HexColor('#62758C'));canvas.setFont('Helvetica',8);canvas.drawString(28,15,'Trident Community Equipment');canvas.drawRightString(page[0]-28,15,f'Page {document.page}')
    doc.build(story,onFirstPage=footer,onLaterPages=footer);return out.getvalue()
