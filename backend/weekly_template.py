"""Fill the clean, authored workbook template using the live report snapshot."""
import base64,copy,datetime as dt,io,zipfile,re,json,textwrap
from pathlib import Path
from xml.etree import ElementTree as ET
from functools import lru_cache
import weekly_report

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
tag=lambda name:'{'+NS+'}'+name
@lru_cache(maxsize=1)
def template():return (Path(__file__).parent/'weekly_hours_template.xlsx').read_bytes()

@lru_cache(maxsize=1)
def report_format():
 return json.loads((Path(__file__).parent/'weekly_report_format.json').read_text(encoding='utf-8'))

def add_reference_styles(content):
 """Append the uploaded format without changing styles used by the other sheets."""
 tree=ET.fromstring(content);reference=report_format()['styles'];maps={}
 for name in ('fonts','fills','borders'):
  target=tree.find(tag(name));maps[name]=[]
  for item in ET.fromstring(reference[name]):
   maps[name].append(len(target));target.append(copy.deepcopy(item))
  target.set('count',str(len(target)))
 formats=tree.find(tag('numFmts'))
 if formats is None:
  formats=ET.Element(tag('numFmts'));tree.insert(0,formats)
 numbers={}
 for item in ET.fromstring(reference['numFmts']):
  existing=next((f for f in formats if f.get('formatCode')==item.get('formatCode')),None)
  number=existing.get('numFmtId') if existing is not None else str(max([163]+[int(f.get('numFmtId')) for f in formats])+1)
  numbers[item.get('numFmtId')]=number
  if existing is None:
   new=copy.deepcopy(item);new.set('numFmtId',number);formats.append(new)
 formats.set('count',str(len(formats)))
 styles=tree.find(tag('cellXfs'));indices=[]
 for item in ET.fromstring(reference['cellXfs']):
  new=copy.deepcopy(item)
  for key,name in (('fontId','fonts'),('fillId','fills'),('borderId','borders')):
   new.set(key,str(maps[name][int(new.get(key,'0'))]))
  new.set('numFmtId',numbers.get(new.get('numFmtId'),new.get('numFmtId','0')))
  indices.append(str(len(styles)));styles.append(new)
 styles.set('count',str(len(styles)))
 return ET.tostring(tree,encoding='utf-8',xml_declaration=True),indices

def apply_reference_layout(tree):
 reference=report_format();tree.find(tag('sheetFormatPr')).attrib=reference['sheetFormat'].copy()
 columns=tree.find(tag('cols'))
 for col in list(columns):
  if int(col.get('min'))<=4:columns.remove(col)
 for index,col in enumerate(reference['columns']):columns.insert(index,ET.Element(tag('col'),col))
 for name in ('pageMargins','pageSetup'):
  element=tree.find(tag(name))
  if element is not None:tree.remove(element)
 ET.SubElement(tree,tag('pageMargins'),reference['pageMargins'])

def row_height(row):
 """Keep the template's 15pt rows; expand only when a wrapped value needs it."""
 widths=[41,12,13,13,3,16,16,16,16,55]
 return min(409.5,15*max([1]+[sum(max(1,len(textwrap.wrap(line,width=max(1,width-2)))) for line in str(value).split('\n'))
                     for value,width in zip(row,widths) if isinstance(value,str)]))

def compact_labour_columns(tree):
 """Remove the two obsolete sum columns and their spacer, retaining cell styles."""
 mapping={'A':'A','B':'B','F':'C','G':'D','H':'E','I':'F','J':'G'}
 for row in tree.find(tag('sheetData')):
  for cell in list(row):
   match=re.fullmatch(r'([A-Z]+)(\d+)',cell.get('r',''))
   if not match or match[1] not in mapping:
    row.remove(cell);continue
   cell.set('r',mapping[match[1]]+match[2])
   formula=cell.find(tag('f'))
   if formula is not None:
    formula.text=re.sub(r'([A-Z]+)(\d+)',lambda m:mapping.get(m[1],m[1])+m[2],formula.text or '')
 columns=tree.find(tag('cols'));columns.clear()
 for index,width in enumerate((41,12,16,16,16,16,55),1):
  ET.SubElement(columns,tag('col'),{'min':str(index),'max':str(index),'width':str(width),'customWidth':'1'})
 dimension=tree.find(tag('dimension'))
 if dimension is not None:dimension.set('ref','A1:G'+str(len(tree.find(tag('sheetData')))))

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
   if day.get('leaveFrom'):notes.append(('Sick leave' if day['sick'] else 'Annual leave' if day['annual'] else 'Leave')+' '+day['leaveFrom']+'–'+day['leaveTo'])
   if day.get('leaveFrom') and day.get('leaveLunch') is not None:notes.append('Unpaid lunch excluded: '+weekly_report.number(day['leaveLunch'])+'h')
   if entry.get('start') and entry.get('finish') and entry.get('status')=='Work':
    def clock(value):
     if not value:return None
     return value
    start=clock(entry.get('start'));finish=clock(entry.get('finish'))
   elif entry.get('status')=='Work' and entry.get('hours',0)>0:notes.append('Work start / finish not recorded in this historical entry')
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
  style_content,reference_styles=add_reference_styles(source.read('xl/styles.xml'))
  for item in source.infolist():
   content=style_content if item.filename=='xl/styles.xml' else source.read(item)
   match=re.fullmatch(r'xl/worksheets/sheet(\d+)\.xml',item.filename)
   if match:
    index=int(match[1])-1;title,headers,values=tables[index];tree=ET.fromstring(content);data=tree.find(tag('sheetData'))
    old={int(r.get('r')):{re.sub(r'\d','',c.get('r')):c.get('s','0') for c in r} for r in data}
    data.clear()
    for n,row in enumerate([headers,*values],1):
     subtotal=index==0 and n>1 and row[0]=='Weekly total';styles=old.get(1 if n==1 else 9 if subtotal else 2,{})
     element=ET.SubElement(data,tag('row'),{'r':str(n)})
     if index==0:
      # First four columns reproduce the upload. Existing extra fields use the same plain style.
      styles={chr(65+c):reference_styles[1 if n==1 else [2,3,4,5,0,4,4,4,4,2][c]] for c in range(10)}
      height=row_height(row)
      if height>15:element.attrib.update({'ht':str(height),'customHeight':'1'})
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
    if index==0:
     apply_reference_layout(tree)
     compact_labour_columns(tree)
    content=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
   target.writestr(item,content)
 return {'filename':filename,'mime':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','file':base64.b64encode(output.getvalue()).decode()}
