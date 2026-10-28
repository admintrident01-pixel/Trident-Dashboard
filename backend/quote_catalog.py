"""Read-only quote summaries; workbook and full quote APIs remain authoritative."""
import copy,datetime as dt,functools,json,math,re
from core import Problem,decode,workbook_info
import quote_settings

FIELDS={'number':'A','date':'B','by':'C','type':'D','to':'E','recipientEmail':'F','address':'G','orgLocality':'H','client':'I','clientAddress':'J','clientLocality':'K','job':'L','ref':'M','equipment':'N','vehicle':'O','rego':'P','message':'Q','notes':'R'}
LIST_FIELDS=('number','client','to','job','type','by','date')

def quote_date(value,filename=''):
 text=str(value or '')
 try:
  if text and re.fullmatch(r'\d+(?:\.\d+)?',text):return (dt.date(1899,12,30)+dt.timedelta(days=float(text))).isoformat()
 except (ValueError,OverflowError):pass
 if text:return text[:10]
 match=re.search(r' - (\d{2})-(\d{2})-(\d{4})\.pdf$',filename)
 return f'{match[3]}-{match[2]}-{match[1]}' if match else ''

def legacy_quote(number,row):
 fields={key:str(row.get(column,'') or '') for key,column in FIELDS.items()}
 fields['number']=str(number);fields['date']=quote_date(row.get('B'),row.get('AC',''))
 text=row.get('S','');items=[]
 try:
  value=json.loads(text)
  if isinstance(value,list):items=value
 except (ValueError,TypeError):pass
 if not items:
  pattern=r'(?:^|\n\n)\d+\. ([\s\S]*?)\nQuantity: ([\d.]+); Unit price excl GST: ([\d.]+); Amount NZD: [\d.]+(?=\n\n|$)'
  items=[{'description':m[1],'qty':float(m[2]),'rate':float(m[3])} for m in re.finditer(pattern,text)]
 if not items:items=[{'description':text or fields['job'] or 'Quote item','qty':1,'rate':float(row.get('T') or 0)}]
 return {'id':row.get('AF') or None,'revision':int(row.get('AG') or 0),'state':row.get('AE') if row.get('AE') in ('Draft','Deleted') else 'Finalised','legacy':True,'data':{'version':1,'fields':fields,'lines':items},'pdfFilename':row.get('AC',''),'updatedAt':''}

@functools.lru_cache(maxsize=2)
def workbook_data(workbook):
 start,rows=workbook_info(decode(workbook,10*1024*1024))
 defaults=quote_settings.read({'workbook':workbook})
 defaults={'version':1,**defaults,'quoteRegister':{'start':start,'rows':[],'hasSheet':True}}
 return start,rows,defaults

@functools.lru_cache(maxsize=2)
def indexed(workbook,quotes_json):
 start,rows,defaults=workbook_data(workbook)
 quotes=json.loads(quotes_json)
 by_number={int(q['data']['fields']['number']):q for q in quotes}
 for number,row in rows.items():
  if number not in by_number:by_number[number]=legacy_quote(number,row)
 # Deleted and purged numbers remain reserved even though absent from the list.
 next_number=max([start-1,*rows,*by_number])+1
 active=[q for q in by_number.values() if q['state']!='Deleted']
 last=next((by_number[n] for n in reversed(rows) if by_number[n]['state']=='Finalised'),None)
 if last is None:last=next((q for q in reversed(active) if q['state']=='Finalised'),None)
 return by_number,active,defaults,next_number,last

def index(state):return indexed(state['workbook'],json.dumps(list(state.get('quotes',{}).values()),sort_keys=True,separators=(',',':')))

def summary(q,pdfs):
 return {**{k:q[k] for k in ('id','revision','state','pdfFilename','updatedAt','legacy','createdByName') if k in q},'summary':True,'hasPdf':q.get('pdfFilename') in pdfs,'data':{'fields':{k:q['data']['fields'].get(k,'') for k in LIST_FIELDS}}}

def listing(state,params):
 by_number,active,defaults,next_number,last=index(state)
 def arg(name,default=''):return params.get(name,[default])[0]
 try:page=max(1,int(arg('page','1')));size=int(arg('size','10'));sort=int(arg('sort','0'))
 except (ValueError,TypeError):raise Problem(400,'Choose a valid quote page and sort order.')
 if size not in (10,20,50,100) or sort not in range(7):raise Problem(400,'Choose a valid quote page and sort order.')
 status=arg('status','All');direction=arg('direction','desc');search=arg('search').strip().casefold()
 if status not in ('All','Draft','Finalised') or direction not in ('asc','desc') or len(search)>1000:raise Problem(400,'Choose a valid quote filter.')
 selected=[q for q in active if (status=='All' or q['state']==status) and (not search or search in ' '.join(str(v) for v in q['data']['fields'].values()).casefold())]
 def value(q):
  f=q['data']['fields'];values=[int(f['number']),f.get('client') or f.get('to',''),f.get('job',''),f.get('type',''),q.get('createdByName') or f.get('by',''),f.get('date',''),'Draft' if q['state']=='Draft' else 'Completed']
  v=values[sort]
  return v if sort==0 else tuple((1,int(p)) if p.isdigit() else (0,p) for p in re.split(r'(\d+)',str(v).casefold()))
 selected.sort(key=lambda q:int(q['data']['fields']['number']),reverse=True)
 selected.sort(key=value,reverse=direction=='desc')
 total=len(selected);pages=max(1,math.ceil(total/size));page=min(page,pages);offset=(page-1)*size
 result={'quotes':[summary(q,state.get('pdfs',{})) for q in selected[offset:offset+size]],'total':total,'page':page,'size':size,'pages':pages,'counts':{'drafts':sum(q['state']=='Draft' for q in active),'completed':sum(q['state']=='Finalised' for q in active)},'nextNumber':next_number,'lastQuote':summary(last,state.get('pdfs',{})) if last else None}
 if arg('defaults')=='1':result['defaults']=copy.deepcopy(defaults)
 return result

def detail(state,params):
 try:number=int(params.get('number',[''])[0])
 except (ValueError,TypeError):raise Problem(400,'Choose a valid quote number.')
 q=index(state)[0].get(number)
 if not q or q['state']=='Deleted':raise Problem(404,'This quote no longer exists. Refresh the quote list.')
 return {'quote':copy.deepcopy(q)}
