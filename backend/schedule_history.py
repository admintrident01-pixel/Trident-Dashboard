"""Recoverable schedule edits, scoped to the signed-in administrator and day."""
import copy,datetime as dt,hashlib,json
from core import Problem
COLLECTIONS=('appointments','travelBlocks','scheduleLinks','scheduleHiddenTravel','scheduleColumnOrders')

def etag(state):
 # Include versions and history so a change followed by a reversal still refreshes clients.
 keys=COLLECTIONS+('deletedLunchIds','leaveRequests','staffSettings','scheduleSettings','timeSettings','scheduleNoteSeries','scheduleHistory')
 payload=json.dumps({k:state.get(k,{}) for k in keys},sort_keys=True,separators=(',',':'))
 return '"schedule-'+hashlib.sha256(payload.encode()).hexdigest()+'"'
def clean(value):
 if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k not in ('version','updatedAt','updatedBy','createdAt')}
 if isinstance(value,list):return [clean(v) for v in value]
 return value
def signature(state):
 keys=COLLECTIONS+('deletedLunchIds','leaveRequests','staffSettings','scheduleSettings','timeSettings','scheduleNoteSeries')
 return hashlib.sha256(json.dumps(clean({k:state.get(k,{}) for k in keys}),sort_keys=True,separators=(',',':')).encode()).hexdigest()
def stacks(state,email,date):return state.get('scheduleHistory',{}).get(email,{}).get(date,{'undo':[],'redo':[]})
def record(before,state,email,date,label):
 changes=[]
 for collection in COLLECTIONS:
  a=before.get(collection,{});b=state.get(collection,{})
  for key in a.keys()|b.keys():
   if a.get(key)!=b.get(key):changes.append({'collection':collection,'key':key,'before':a.get(key),'after':b.get(key)})
 if not changes:return state
 result=copy.deepcopy(state);old=stacks(before,email,date);undo=old['undo']
 if undo and undo[-1]['afterHash']!=signature(before):undo=[]
 entry={'changes':changes,'beforeHash':signature(before),'afterHash':signature(state),'label':label}
 result.setdefault('scheduleHistory',{}).setdefault(email,{})[date]={'undo':undo[-29:]+[entry],'redo':[]}
 return result
def apply(state,email,date,action):
 if action not in ('undo','redo'):raise Problem(400,'Choose Undo or Redo.')
 history=stacks(state,email,date);items=history[action]
 if not items:raise Problem(409,'There is nothing to '+action+' for this day.')
 entry=items[-1];expected=entry['afterHash' if action=='undo' else 'beforeHash']
 if signature(state)!=expected:raise Problem(409,'The schedule changed since this action. Undo/Redo cannot overwrite newer changes.')
 result=copy.deepcopy(state);target='before' if action=='undo' else 'after'
 for change in entry['changes']:
  rows=result.setdefault(change['collection'],{});value=copy.deepcopy(change[target]);old=rows.get(change['key'])
  if value is None:rows.pop(change['key'],None)
  else:
   if isinstance(value,dict) and change['collection'] in ('appointments','travelBlocks'):
    value.update(version=max((old or {}).get('version',0),value.get('version',0))+1,updatedAt=dt.datetime.now(dt.timezone.utc).isoformat(),updatedBy=email)
   rows[change['key']]=value
 updated=copy.deepcopy(history);updated[action].pop();updated['redo' if action=='undo' else 'undo'].append(entry)
 result.setdefault('scheduleHistory',{}).setdefault(email,{})[date]=updated
 return result
def read(state,date,user):
 import schedule
 result=schedule.read(state,date);history=stacks(state,user['email'],date);current=signature(state)
 result['history']={name:{'available':bool(history[name]) and history[name][-1]['afterHash' if name=='undo' else 'beforeHash']==current,'label':history[name][-1]['label'] if history[name] else ''} for name in ('undo','redo')}
 return result
