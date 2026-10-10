"""Weekly work/leave totals, daily admin notes and a downloadable PDF."""
import base64, copy, datetime as dt, io
from xml.sax.saxutils import escape
import leave, timesheets
from core import Problem

def week_date(value):
    date=leave.day(value)
    if date.weekday()!=0: raise Problem(400,'Choose a Monday for week starting.')
    return date

def week_rows(state, week):
    start=week_date(week)
    dates=[(start+dt.timedelta(days=i)).isoformat() for i in range(7)]
    latest={}
    for sheet in sorted(state.get('timesheets',{}).values(),key=lambda s:s.get('submittedAt','')):
        if sheet['weekStart']==week: latest[sheet['technician'].casefold()]=sheet
    approved={}
    names={r['name'].casefold():r['name'] for r in timesheets.settings(state)['technicians']}
    for key,sheet in latest.items(): names.setdefault(key,sheet['technician'])
    for request in leave.approved(state):
        for date in request['dates']:
            if date in dates:
                key=request['technician'].casefold()
                names.setdefault(key,request['technician']);approved[(key,date)]=request
    notes=state.get('weeklyReportNotes',{}).get(week,{})
    rows=[]
    for key,name in names.items():
        sheet=latest.get(key);days=[]
        for i,date in enumerate(dates):
            entry=sheet['days'][i] if sheet else {'status':'Work','hours':0}
            request=approved.get((key,date))
            status=request['leaveType'] if request else entry['status']
            hours=float(request['hoursPerDay'] if request else entry['hours'])
            work=hours if status=='Work' else 0
            sick=hours if status=='Sick leave' else 0
            annual=hours if status=='Annual leave' else 0
            other=hours if status=='Other' else 0
            days.append({'date':date,'work':work,'sick':sick,'annual':annual,'other':other,'paid':work+sick,'all':work+sick+annual+other,'approvedLeave':bool(request),'note':notes.get(key,{}).get(date,'')})
        rows.append({'name':name,'submitted':bool(sheet),'days':days})
    return rows

def read(state,week):
    start=week_date(week)
    return {'week':week,'rows':week_rows(state,week),'previousWeek':(start-dt.timedelta(days=7)).isoformat(),'previous':week_rows(state,(start-dt.timedelta(days=7)).isoformat())}

def save_notes(state,data):
    week=data.get('week');week_date(week)
    notes=data.get('notes')
    if not isinstance(notes,list) or len(notes)>1400: raise Problem(400,'Enter valid daily notes.')
    allowed={r['name'].casefold() for r in week_rows(state,week)}
    valid_dates={(week_date(week)+dt.timedelta(days=i)).isoformat() for i in range(7)}
    cleaned={};seen=set()
    for row in notes:
        if not isinstance(row,dict): raise Problem(400,'Invalid daily note.')
        name=row.get('technician');date=row.get('date');note=row.get('note')
        if not isinstance(name,str) or name.casefold() not in allowed or date not in valid_dates or not isinstance(note,str) or len(note)>2000: raise Problem(400,'Each note needs a staff member, a date in this week and up to 2000 characters.')
        key=(name.casefold(),date)
        if key in seen: raise Problem(400,'Enter only one note per person per day.')
        seen.add(key)
        if note.strip(): cleaned.setdefault(name.casefold(),{})[date]=note.strip()
    result=copy.deepcopy(state)
    result.setdefault('weeklyReportNotes',{})[week]=cleaned
    return result

def number(n): return f'{n:.2f}'.rstrip('0').rstrip('.')
def day_label(date): return dt.date.fromisoformat(date).strftime('%d/%m/%Y')

def pdf(state,data):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, LongTable
    week=data.get('week');rows=week_rows(state,week)
    mode=data.get('mode','work')
    if mode not in ('work','all'): raise Problem(400,'Choose a report type.')
    metric='paid' if mode=='work' else 'all'
    output=io.BytesIO();page=landscape(A4);width=page[0]-64
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Cell',fontName='Helvetica',fontSize=8,leading=10))
    styles.add(ParagraphStyle(name='Hours',parent=styles['Cell'],alignment=TA_CENTER))
    title='Weekly work and sick hours' if mode=='work' else 'Weekly work and leave hours'
    def para(text,style='Cell'): return Paragraph(escape(text).replace('\n','<br/>'),styles[style])
    story=[Paragraph('Trident Community Equipment',styles['Title']),Paragraph(title,styles['Heading2']),Paragraph('Week starting '+day_label(week),styles['Normal']),Spacer(1,10),para('Work and sick hours count toward the total. Annual and other leave are shown separately.' if mode=='work' else 'Totals include work, sick, annual and other approved leave.'),Spacer(1,10)]
    dates=[(week_date(week)+dt.timedelta(days=i)).isoformat() for i in range(7)]
    header=[para('Staff member')]+[para(dt.date.fromisoformat(d).strftime('%a\n%d/%m'),'Hours') for d in dates]+[para('Total','Hours')]
    cells=[header]
    for row in rows:
        values=[para(row['name'])]
        for day in row['days']:
            text=number(day[metric])
            for kind,label in [('sick','Sick'),('annual','Annual'),('other','Other')]:
                if day[kind]: text+='\n'+label+' '+number(day[kind])+'h'
            values.append(para(text,'Hours'))
        total_text=number(sum(d[metric] for d in row['days']))
        for kind,label in [('sick','Sick'),('annual','Annual'),('other','Other')]:
            total=sum(d[kind] for d in row['days'])
            if total: total_text+='\n'+label+' '+number(total)+'h'
        values.append(para(total_text,'Hours'));cells.append(values)
    totals=[sum(r['days'][i][metric] for r in rows) for i in range(7)]
    cells.append([para('Total')]+[para(number(n),'Hours') for n in totals]+[para(number(sum(totals)),'Hours')])
    table=LongTable(cells,colWidths=[155]+[(width-211)/7]*7+[56],repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eef8')),('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#e7eef8')),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#ccd5e2')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story.extend([table,Spacer(1,12)])
    note_rows=[[para('Staff member'),para('Date'),para('Daily note')]]
    for row in rows:
        for day in row['days']:
            if day['note']: note_rows.append([para(row['name']),para(day_label(day['date'])),para(day['note'])])
    if len(note_rows)>1:
        story.append(Paragraph('Daily notes',styles['Heading2']))
        notes=LongTable(note_rows,colWidths=[155,80,width-235],repeatRows=1,hAlign='LEFT',splitInRow=1)
        notes.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eef8')),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#ccd5e2')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        story.append(notes)
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#52677e'));canvas.drawString(32,19,'Trident - '+title+' - '+day_label(week));canvas.drawRightString(page[0]-32,19,'Page '+str(doc.page))
    doc=SimpleDocTemplate(output,pagesize=page,rightMargin=32,leftMargin=32,topMargin=26,bottomMargin=34,title=title,author='Trident Community Equipment')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return {'filename':f'Trident-weekly-{mode}-hours-{week}.pdf','pdf':base64.b64encode(output.getvalue()).decode()}
