"""Fill the clean, authored workbook template using the live report snapshot."""
import base64,copy,datetime as dt,io,zipfile,re
from pathlib import Path
from xml.etree import ElementTree as ET
from functools import lru_cache
import weekly_report

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
tag=lambda name:'{'+NS+'}'+name
@lru_cache(maxsize=1)
def template():return (Path(__file__).parent/'weekly_hours_template.xlsx').read_bytes()

def labour_rows(state,week,rows,metric):
 latest={}
 for sheet in sorted(state.get('timesheets',{}).values(),key=lambda s:s.get('updatedAt') or s.get('submittedAt','')):
  if sheet.get('weekStart')==week:latest[sheet['technician'].casefold()]=sheet
 users=list(state.get('users',{}).values());result=[]
 for person in rows:
  name=person['name'];sheet=latest.get(name.casefold());owners=[u for u in users if (u.get('technician') or '').casefold()==name.casefold()]
  owner=next((u for u in owners if u.get('active')),owners[0] if owners else {})
  display=name+(' <'+owner['email']+'>' if owner.get('email') else '')
  for i,day in enumerate(person['days']):
   entry=sheet['days'][i] if sheet else {};recorded=bool(sheet or day['approvedLeave']);start=finish=None
   notes=[]
   for kind,label in [('sick','Sick'),('annual','Annual'),('other','Other')]:
    if day[kind]:notes.append(label+' '+weekly_report.number(day[kind])+'h')
   if day.get('otherDescription'):notes.append(day['otherDescription'])
   if day.get('leaveFrom'):notes.append('Leave '+day['leaveFrom']+'–'+day['leaveTo'])
   if entry.get('method')=='times':
    def clock(value):
     if not value:return None
     h,m=value.split(':');return int(h)+int(m)/60
    start=clock(entry.get('start'));finish=clock(entry.get('finish'))
   elif recorded:start=entry.get('status','Approved leave') if entry.get('status','Work')!='Work' else 'Direct hours' if sheet else 'Approved leave'
   if day['note']:notes.append(day['note'])
   if not recorded:notes.append('No submission')
   lunch=entry.get('lunchHours')
   if lunch is None and entry.get('status')=='Work' and isinstance(entry.get('unpaidLunch'),bool):lunch=.5 if entry['unpaidLunch'] else 0
   serial=(dt.date.fromisoformat(day['date'])-dt.date(1899,12,30)).days
   result.append([display,serial,person['chargedHours'][i],None,None,start,finish,day[metric] if recorded else None,lunch,'\n'.join(notes)])
  first=len(result)+2-7;last=len(result)+1
  # The two totals have a single transparent SUM, with cached source totals.
  result.append(['Weekly total',None,('SUM(C'+str(first)+':C'+str(last)+')',sum(v or 0 for v in person['chargedHours'])),None,None,None,None,('SUM(H'+str(first)+':H'+str(last)+')',sum(d[metric] for d in person['days'])),None,None])
  result.extend([[None]*10,[None]*10])
 return result

def create(state,week,rows,metric,tables,filename):
 first=('Labour Report',['Name','Date','Hours (sum)','Total (sum)','','Start','Finish','Payable hours','Lunch hours','Notes'],labour_rows(state,week,rows,metric))
 tables=[first,*tables];output=io.BytesIO()
 with zipfile.ZipFile(io.BytesIO(template())) as source,zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as target:
  for item in source.infolist():
   content=source.read(item)
   match=re.fullmatch(r'xl/worksheets/sheet(\d+)\.xml',item.filename)
   if match:
    index=int(match[1])-1;title,headers,values=tables[index];tree=ET.fromstring(content);data=tree.find(tag('sheetData'))
    old={int(r.get('r')):{re.sub(r'\d','',c.get('r')):c.get('s','0') for c in r} for r in data}
    data.clear()
    for n,row in enumerate([headers,*values],1):
     subtotal=index==0 and n>1 and row[0]=='Weekly total';styles=old.get(1 if n==1 else 9 if subtotal else 2,{})
     element=ET.SubElement(data,tag('row'),{'r':str(n)})
     for col,value in enumerate(row):
      letter=chr(65+col);cell=ET.SubElement(element,tag('c'),{'r':letter+str(n),'s':styles.get(letter,'0')})
      if value is None:continue
      if isinstance(value,tuple):ET.SubElement(cell,tag('f')).text=value[0];ET.SubElement(cell,tag('v')).text=str(value[1])
      elif isinstance(value,(float,int)) and not isinstance(value,bool):ET.SubElement(cell,tag('v')).text=str(value)
      else:
       cell.set('t','inlineStr');text=ET.SubElement(ET.SubElement(cell,tag('is')),tag('t'));text.set('{http://www.w3.org/XML/1998/namespace}space','preserve');text.text=str(value)
    dimension=tree.find(tag('dimension'))
    if dimension is not None:dimension.set('ref','A1:'+chr(64+len(headers))+str(len(values)+1))
    pane=tree.find(tag('sheetViews')+'/'+tag('sheetView')+'/'+tag('pane'))
    if pane is not None:pane.attrib.update({'xSplit':'1','ySplit':'1','topLeftCell':'B2','activePane':'bottomRight','state':'frozen'})
    for name in ('autoFilter','pageMargins','pageSetup'):
     existing=tree.find(tag(name))
     if existing is not None:tree.remove(existing)
    ET.SubElement(tree,tag('pageMargins'),{'left':'.25','right':'.25','top':'.4','bottom':'.4','header':'.2','footer':'.2'})
    ET.SubElement(tree,tag('pageSetup'),{'orientation':'landscape','paperSize':'9','fitToWidth':'1','fitToHeight':'0'})
    content=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
   target.writestr(item,content)
 return {'filename':filename,'mime':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','file':base64.b64encode(output.getvalue()).decode()}
