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
    for sheet in sorted(state.get('timesheets',{}).values(),key=lambda s:s.get('updatedAt') or s.get('submittedAt','')):
        if sheet['weekStart']==week: latest[sheet['technician'].casefold()]=sheet
    approved={}
    names={r['name'].casefold():r['name'] for r in timesheets.settings(state)['technicians']}
    for key,sheet in latest.items(): names.setdefault(key,sheet['technician'])
    for request in leave.approved(state):
        for date in request['dates']:
            if date in dates:
                key=request['technician'].casefold()
                names.setdefault(key,request['technician']);approved[(key,date)]=request
    charged=state.get('weeklyChargedHours',{}).get(week,{})
    for key,entry in charged.items():names.setdefault(key,entry['name'])
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
            days.append({'date':date,'work':work,'sick':sick,'annual':annual,'other':other,'paid':work+sick,'all':work+sick+annual+other,'approvedLeave':bool(request),'note':notes.get(key,{}).get(date,entry.get('notes',''))})
        rows.append({'name':name,'submitted':bool(sheet),'days':days,'chargedHours':[charged.get(key,{}).get('days',{}).get(date) for date in dates]})
    return rows

def read(state,week,comparison=None):
    start=week_date(week)
    previous=comparison or (start-dt.timedelta(days=7)).isoformat();week_date(previous)
    return {'week':week,'rows':week_rows(state,week),'previousWeek':previous,'previous':week_rows(state,previous),'averages':averages(state,week)}


def averages(state,week):
    end=week_date(week);first=end-dt.timedelta(weeks=13);totals={}
    for offset in range(13):
        for row in week_rows(state,(first+dt.timedelta(weeks=offset)).isoformat()):
            key=row['name'].casefold();item=totals.setdefault(key,{'name':row['name'],'paid':0,'all':0,'charged':0,'workWeeks':0,'chargedWeeks':0})
            if row['submitted'] or any(day['approvedLeave'] for day in row['days']):
                item['paid']+=sum(day['paid'] for day in row['days']);item['all']+=sum(day['all'] for day in row['days']);item['workWeeks']+=1
            if any(value is not None for value in row['chargedHours']):
                item['charged']+=sum(value or 0 for value in row['chargedHours']);item['chargedWeeks']+=1
    for row in week_rows(state,week):totals.setdefault(row['name'].casefold(),{'name':row['name'],'paid':0,'all':0,'charged':0,'workWeeks':0,'chargedWeeks':0})
    return {'start':first.isoformat(),'end':(end-dt.timedelta(days=1)).isoformat(),'weeks':13,'rows':[{'name':item['name'],'paidAverage':item['paid']/13,'allAverage':item['all']/13,'chargedAverage':item['charged']/13,'workWeeks':item['workWeeks'],'chargedWeeks':item['chargedWeeks']} for item in totals.values()]}

def save_charged(state,data):
    week=data.get('week');start=week_date(week);entries=data.get('charged')
    if not isinstance(entries,list) or len(entries)>1400:raise Problem(400,'Enter valid charged hours.')
    names={row['name'].casefold():row['name'] for row in week_rows(state,week)};dates={(start+dt.timedelta(days=i)).isoformat() for i in range(7)};seen=set();result=copy.deepcopy(state)
    records=result.setdefault('weeklyChargedHours',{}).setdefault(week,{})
    for entry in entries:
        if not isinstance(entry,dict):raise Problem(400,'Invalid charged hours.')
        name=entry.get('technician');date=entry.get('date');value=entry.get('hours')
        if not isinstance(name,str) or name.casefold() not in names or date not in dates or (name.casefold(),date) in seen:raise Problem(400,'Choose one staff member/date in this week per charged entry.')
        key=name.casefold();seen.add((key,date));record=records.setdefault(key,{'name':names[key],'days':{}})
        if value is None or value=='':record['days'].pop(date,None)
        else:
            if isinstance(value,bool):raise Problem(400,'Charged hours must use 0.25-hour increments from 0 to 24.')
            try:hours=float(value)
            except (ValueError,TypeError):raise Problem(400,'Enter valid charged hours.')
            if not 0<=hours<=24 or hours*4!=int(hours*4):raise Problem(400,'Charged hours must use 0.25-hour increments from 0 to 24.')
            record['days'][date]=hours
    result['weeklyChargedHours'][week]={key:value for key,value in records.items() if value['days']}
    return result

def save_report(state,data):
    updates=data.get('updates') if isinstance(data,dict) else None
    if not isinstance(updates,list) or not 1<=len(updates)<=2:raise Problem(400,'Save one or two report weeks.')
    seen=set();result=state
    for update in updates:
        if not isinstance(update,dict) or update.get('week') in seen:raise Problem(400,'Choose distinct report weeks.')
        seen.add(update.get('week'));week_date(update.get('week'))
        if 'notes' in update:result=save_notes(result,update)
        if 'charged' in update:result=save_charged(result,update)
        if 'notes' not in update and 'charged' not in update:raise Problem(400,'Enter report changes.')
    return result

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
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, LongTable
    week=data.get('week');rows=week_rows(state,week)
    mode=data.get('mode','all')
    if mode not in ('work','all'): raise Problem(400,'Choose a report type.')
    metric='paid' if mode=='work' else 'all'
    output=io.BytesIO();page=A4;width=page[0]-64
    styles=getSampleStyleSheet()
    styles['Title'].fontSize=16;styles['Title'].leading=18;styles['Title'].spaceAfter=6
    styles['Heading2'].fontSize=11;styles['Heading2'].leading=13;styles['Heading2'].spaceBefore=6;styles['Heading2'].spaceAfter=4
    styles['Normal'].fontSize=8;styles['Normal'].leading=10
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
        charged=row['chargedHours'];cells.append([para(row['name']+' — Charged hours')]+[para(number(value) if value is not None else '—','Hours') for value in charged]+[para(number(sum(value or 0 for value in charged)),'Hours')])
    totals=[sum(r['days'][i][metric] for r in rows) for i in range(7)]
    cells.append([para('Total payable hours')]+[para(number(n),'Hours') for n in totals]+[para(number(sum(totals)),'Hours')])
    charged_totals=[sum(row['chargedHours'][i] or 0 for row in rows) for i in range(7)]
    cells.append([para('Total charged hours')]+[para(number(value),'Hours') for value in charged_totals]+[para(number(sum(charged_totals)),'Hours')])
    table=LongTable(cells,colWidths=[110]+[(width-150)/7]*7+[40],repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eef8')),('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#e7eef8')),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#ccd5e2')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
    table.setStyle(TableStyle([('BACKGROUND',(0,index),(-1,index),colors.HexColor('#e0e3e8')) for index in range(2,len(rows)*2+1,2)]+[('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#e0e3e8'))]))
    story.extend([table,Spacer(1,12)])
    average=averages(state,week);story.append(Paragraph('Three-month weekly averages',styles['Heading2']));story.append(para('13 completed weeks: '+day_label(average['start'])+' to '+day_label(average['end'])+'. Totals divided by all 13 weeks; missing and zero weeks included.'))
    average_cells=[[para(label) for label in ['Staff member','Average payable/week','Average charged/week','Payable weeks','Charged weeks']]]
    for item in average['rows']:
        value=item['paidAverage'] if mode=='work' else item['allAverage'];average_cells.append([para(item['name']),para(number(value) if value is not None else '—'),para(number(item['chargedAverage']) if item['chargedAverage'] is not None else '—'),para(str(item['workWeeks'])),para(str(item['chargedWeeks']))])
    average_table=LongTable(average_cells,colWidths=[110]+[(width-110)/4]*4,repeatRows=1,hAlign='LEFT');average_table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eef8')),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#ccd5e2')),('VALIGN',(0,0),(-1,-1),'TOP')]));story.extend([Spacer(1,6),average_table,Spacer(1,12)])
    note_rows=[[para('Staff member'),para('Date'),para('Daily note')]]
    for row in rows:
        for day in row['days']:
            if day['note']: note_rows.append([para(row['name']),para(day_label(day['date'])),para(day['note'])])
    if len(note_rows)>1:
        story.append(Paragraph('Daily notes',styles['Heading2']))
        notes=LongTable(note_rows,colWidths=[110,65,width-175],repeatRows=1,hAlign='LEFT',splitInRow=1)
        notes.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eef8')),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#ccd5e2')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        story.append(notes)
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#52677e'));canvas.drawString(32,19,'Trident - '+title+' - '+day_label(week));canvas.drawRightString(page[0]-32,19,'Page '+str(doc.page))
    doc=SimpleDocTemplate(output,pagesize=page,rightMargin=32,leftMargin=32,topMargin=26,bottomMargin=34,title=title,author='Trident Community Equipment')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return {'filename':f'Trident-weekly-{mode}-hours-{week}.pdf','pdf':base64.b64encode(output.getvalue()).decode()}


def period(state,start,end):
    first=week_date(start);last=week_date(end)
    weeks=(last-first).days//7+1
    if not 1<=weeks<=52:raise Problem(400,'Choose an end week on or after the start, within 52 weeks.')
    totals={}
    for offset in range(weeks):
        for row in week_rows(state,(first+dt.timedelta(weeks=offset)).isoformat()):
            item=totals.setdefault(row['name'].casefold(),{'name':row['name'],'paid':0,'all':0,'charged':0,'workWeeks':0,'chargedWeeks':0})
            for metric in ('paid','all'):item[metric]+=sum(day[metric] for day in row['days'])
            item['charged']+=sum(value or 0 for value in row['chargedHours'])
            item['workWeeks']+=int(row['submitted'] or any(day['approvedLeave'] for day in row['days']))
            item['chargedWeeks']+=int(any(value is not None for value in row['chargedHours']))
    return {'start':start,'endWeek':end,'end':(last+dt.timedelta(days=6)).isoformat(),'weeks':weeks,'rows':list(totals.values())}


def selected_period(state,data):
    result=period(state,data.get('start'),data.get('end'))
    for row in result['rows']:
        row['paidAverage']=row['paid']/result['weeks']
        row['allAverage']=row['all']/result['weeks']
        row['chargedAverage']=row['charged']/result['weeks']
    return result

def period_pdf(state,data):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,LongTable,TableStyle
    result=selected_period(state,data);mode=data.get('mode','all')
    if mode not in ('work','all'):raise Problem(400,'Choose a report type.')
    metric='all' if mode=='all' else 'paid';styles=getSampleStyleSheet();output=io.BytesIO();styles['Normal'].fontSize=8;styles['Normal'].leading=10
    def cell(text):return Paragraph(escape(str(text)),styles['Normal'])
    story=[Paragraph('Trident - Selected week averages',styles['Title']),cell(day_label(result['start'])+' to '+day_label(result['end'])+' ('+str(result['weeks'])+' weeks)'),Spacer(1,10),cell('Payable hours: '+('work and all leave' if mode=='all' else 'work and sick hours')+'. Weekly averages divide saved totals by all '+str(result['weeks'])+' selected weeks, including weeks with no records.'),Spacer(1,12)]
    cells=[[cell(x) for x in ['Technician','Payable total','Charged total','Average payable / week','Average charged / week','Payable weeks recorded','Charged weeks recorded']]]
    totals=[0]*4
    for row in result['rows']:
        values=[row[metric],row['charged'],row[metric+'Average'],row['chargedAverage']]
        totals=[x+y for x,y in zip(totals,values)]
        cells.append([cell(row['name'])]+[cell(number(x)) for x in values]+[cell(row['workWeeks']),cell(row['chargedWeeks'])])
    cells.append([cell('Total')]+[cell(number(x)) for x in totals]+[cell(''),cell('')])
    table=LongTable(cells,colWidths=[110]+[(A4[0]-56-110)/6]*6,repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eef8')),('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#e7eef8')),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#ccd5e2')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story.append(table);doc=SimpleDocTemplate(output,pagesize=A4,leftMargin=28,rightMargin=28,topMargin=26,bottomMargin=26,title='Trident selected week averages');doc.build(story)
    return {'filename':f"Trident-week-averages-{result['start']}-{result['endWeek']}.pdf",'pdf':base64.b64encode(output.getvalue()).decode()}
