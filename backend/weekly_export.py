"""Read-only Excel equivalents of Labour payables reports; no extra runtime packages."""
import base64,datetime as dt,io,zipfile,copy
from xml.etree import ElementTree as ET
import stock_reports,weekly_report
from core import Problem
MIME='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
def mode_of(data):
 if not isinstance(data,dict) or data.get('mode','all') not in ('all','work'):raise Problem(400,'Choose a report type.')
 return data.get('mode','all')
def workbook(tables):
 raw=stock_reports.excel(tables);out=io.BytesIO();ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';tag=lambda n:'{'+ns+'}'+n
 with zipfile.ZipFile(io.BytesIO(raw)) as z,zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as target:
  for item in z.infolist():
   content=z.read(item)
   if item.filename.startswith('xl/worksheets/sheet') and item.filename.endswith('.xml'):
    tree=ET.fromstring(content);sheet=int(item.filename.split('sheet')[-1].split('.')[0])-1;title,headers,_=tables[sheet]
    for col,header in zip(tree.find(tag('cols')),headers):col.set('width','60' if header in ('Daily notes','Other leave description','Leave / notes','Value') else '28' if header in ('Staff member','Technician') else '24' if 'week' in header.lower() else '20' if header in ('Date','Hours type') else '14')
    tree.find(tag('sheetViews')+'/'+tag('sheetView')+'/'+tag('pane')).attrib.update({'xSplit':'1','ySplit':'1','topLeftCell':'B2','activePane':'bottomRight'})
    for row in tree.find(tag('sheetData')):
     for cell in row:
      if cell.get('t')=='inlineStr' and not ''.join(cell.itertext()):
       for child in list(cell):cell.remove(child)
       cell.attrib.pop('t',None)
      elif row.get('r')!='1' and cell.get('t')!='inlineStr':cell.set('s','2')
    ET.SubElement(tree,tag('pageMargins'),{'left':'.25','right':'.25','top':'.4','bottom':'.4','header':'.2','footer':'.2'})
    ET.SubElement(tree,tag('pageSetup'),{'orientation':'landscape','paperSize':'9','fitToWidth':'1','fitToHeight':'0'})
    content=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
   elif item.filename=='xl/styles.xml':
    tree=ET.fromstring(content);styles=tree.find(tag('cellXfs'));numeric=copy.deepcopy(styles[0]);numeric.set('numFmtId','2');numeric.set('applyNumberFormat','1');styles.append(numeric);styles.set('count',str(len(styles)));content=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
   target.writestr(item,content)
 return out.getvalue()
def pack(tables,filename):return {'filename':filename,'mime':MIME,'file':base64.b64encode(workbook(tables)).decode()}
def day_annotations(day):
 labels=[]
 for kind,label in [('sick','Sick'),('annual','Annual'),('other','Other')]:
  if day[kind]:labels.append(label+' '+weekly_report.number(day[kind])+'h')
 if day.get('otherDescription'):labels.append(day['otherDescription'])
 if day['note']:labels.append(day['note'])
 return '\n'.join(labels)

def weekly(state,data):
 mode=mode_of(data);week=data.get('week');rows=weekly_report.week_rows(state,week);metric='all' if mode=='all' else 'paid'
 dates=[(weekly_report.week_date(week)+dt.timedelta(days=i)).isoformat() for i in range(7)]
 headers=['Staff member','Hours type',*dates,'Total hours'];summary=[];detail=[]
 for row in rows:
  payable=[day[metric] for day in row['days']];charged=row['chargedHours']
  summary.extend([[row['name'],'Payable',*payable,sum(payable)],[row['name'],'Charged',*charged,sum(n or 0 for n in charged)]])
  annotations=[day_annotations(day) for day in row['days']]
  if any(annotations):summary.append([row['name'],'Leave / notes',*annotations,None])
  for i,day in enumerate(row['days']):detail.append([row['name'],day['date'],day['work'],day['sick'],day['annual'],day['other'],day[metric],charged[i],'Submitted' if row['submitted'] else 'Approved leave only' if day['approvedLeave'] else 'No submission',day['note'],day['otherDescription']])
 for kind in ('Payable','Charged'):
  totals=[sum((r['days'][i][metric] if kind=='Payable' else r['chargedHours'][i] or 0) for r in rows) for i in range(7)]
  summary.append(['Total',kind,*totals,sum(totals)])
 average=weekly_report.averages(state,week)
 averages=[[r['name'],r['allAverage'] if mode=='all' else r['paidAverage'],r['chargedAverage'],r['workWeeks'],r['chargedWeeks']] for r in average['rows']]
 info=[['Week starting',week],['Payable hours','Work, sick, annual and other approved leave' if mode=='all' else 'Work and sick leave; annual and other leave shown separately'],['Average period',average['start']+' to '+average['end']],['Average basis','13 completed weeks, including missing and zero weeks'],['Charged hours','Blank means not entered; zero means explicitly entered as zero'],['Report type','Saved register snapshot. Editing this file does not change the website.']]
 return pack([('Weekly hours',headers,summary),('Daily detail',['Staff member','Date','Work hours','Sick leave hours','Annual leave hours','Other leave hours','Payable hours','Charged hours','Submission','Daily notes','Other leave description'],detail),('13-week averages',['Staff member','Average payable / week','Average charged / week','Payable weeks recorded','Charged weeks recorded'],averages),('Report details',['Setting','Value'],info)],f'Trident-weekly-{mode}-hours-{week}.xlsx')
def period_annotations(state,result):
 first=weekly_report.week_date(result['start']);details=[]
 for offset in range(result['weeks']):
  for row in weekly_report.week_rows(state,(first+dt.timedelta(weeks=offset)).isoformat()):
   for day in row['days']:
    text=day_annotations(day)
    if text:details.append([row['name'],day['date'],text])
 return details

def period(state,data):
 mode=mode_of(data);result=weekly_report.selected_period(state,data);metric='all' if mode=='all' else 'paid'
 rows=[[r['name'],r[metric],r['charged'],r[metric+'Average'],r['chargedAverage'],r['workWeeks'],r['chargedWeeks']] for r in result['rows']]
 rows.append(['Total',*[sum(r[i] for r in rows) for i in range(1,5)],None,None])
 info=[['From Monday',result['start']],['Through Sunday',result['end']],['Weeks included',result['weeks']],['Average basis','Saved totals divided by all selected weeks, including missing and zero weeks'],['Payable hours','Work and all approved leave' if mode=='all' else 'Work and sick leave']]
 return pack([('Selected week averages',['Technician','Payable total','Charged total','Average payable / week','Average charged / week','Payable weeks recorded','Charged weeks recorded'],rows),('Report details',['Setting','Value'],info),('Other leave details',['Staff member','Date','Other leave hours','Other leave description'],[[d['name'],d['date'],d['hours'],d['description']] for d in weekly_report.period_leave_details(state,result)]),('Daily notes and leave',['Staff member','Date','Leave / notes'],period_annotations(state,result))],f"Trident-week-averages-{result['start']}-{result['endWeek']}.xlsx")
