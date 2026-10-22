"""Disposable HTTP integration check; never reads or copies business records.

Default: a new temporary SQLite register with simulated storage latency.
Optional hosted check: --bigquery-table PROJECT.DATASET.trident_leave_test_UUIDHEX
creates only that new, expiring synthetic table and removes it afterwards. It
requires normal Google credentials and never uses the configured production table.
"""
import argparse,concurrent.futures,datetime as dt,json,os,re,threading,time,uuid
from socketserver import ThreadingMixIn
from urllib.request import Request,urlopen
from wsgiref.simple_server import WSGIServer,WSGIRequestHandler,make_server
from app import Application
from storage import SQLiteStore,BigQueryStore
from test_support import TestDirectory

class ThreadedServer(ThreadingMixIn,WSGIServer):daemon_threads=True
class QuietHandler(WSGIRequestHandler):
 def log_message(self,*args):pass

class DelayedStore:
 def __init__(self,store,delay):self.store=store;self.delay=delay;self.lock=threading.Lock();self.lose_ack=True;self.conflicts=0
 def read(self):time.sleep(self.delay);return self.store.read()
 def commit(self,revision,state):
  time.sleep(self.delay);committed=self.store.commit(revision,state)
  with self.lock:
   if not committed:self.conflicts+=1
   if committed and self.lose_ack and state.get('leaveOperations'):
    self.lose_ack=False;raise TimeoutError('Synthetic lost database acknowledgement after commit')
  return committed

def synthetic_state():
 users={f'admin{i}@example.invalid':{'email':f'admin{i}@example.invalid','name':f'Synthetic admin {i}','technician':f'Synthetic staff {i}','role':'admin','active':True,'verified':True} for i in range(3)}
 return {'users':users,'staffSettings':{'technicians':[{'name':f'Synthetic staff {i}','rego':''} for i in range(3)]},'quotes':{},'pdfs':{},'leaveRequests':{},'appointments':{},'reminderSettings':{'leaveRecipients':[]}}

def run(store):
 app=Application(store,object(),lambda token:f'admin{token}@example.invalid',origin='http://127.0.0.1',local=True)
 server=make_server('127.0.0.1',0,app,server_class=ThreadedServer,handler_class=QuietHandler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 url=f'http://127.0.0.1:{server.server_port}';durations=[];start=time.perf_counter()
 def post(path,body,actor):
  began=time.perf_counter();req=Request(url+path,data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+str(actor),'Origin':'http://127.0.0.1','Content-Type':'application/json','If-Match':'"0"'},method='POST')
  with urlopen(req,timeout=115) as response:result=json.load(response)
  durations.append(round(time.perf_counter()-began,3));return result
 requests=[{'technician':f'Synthetic staff {i}','leaveType':'Annual leave','startDate':'2027-02-01','endDate':'2027-02-01','startTime':'08:00','endTime':'16:00','hoursPerDay':8,'reason':'Disposable integration fixture','operationId':uuid.uuid4().hex} for i in range(3)]
 barrier=threading.Barrier(4)
 def submit(i):barrier.wait(timeout=15);return post('/api/leave',requests[i],i)
 def unrelated():
  barrier.wait(timeout=15)
  for serial in range(2):
   for attempt in range(20):
    revision,state=store.read();state['appointments']['synthetic-booking']={'id':'synthetic-booking','date':'2027-02-01','start':'17:00','duration':30,'technician':'Synthetic staff 0','client':'Synthetic client','notes':f'Unrelated save {serial}'};state['reminderJob']={'syntheticRun':serial}
    if store.commit(revision,state):break
   else:raise AssertionError('Unrelated writer exhausted its bounded retries')
 try:
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
   futures=[pool.submit(submit,i) for i in range(3)];other=pool.submit(unrelated);created=[future.result() for future in futures];other.result()
  assert len({row['request']['id'] for row in created})==3
  decisions=[{'id':row['request']['id'],'revision':1,'status':'Approved','decisionNotes':'Synthetic approval','operationId':uuid.uuid4().hex} for row in created]
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:approved=list(pool.map(lambda i:post('/api/leave-decision',decisions[i],i),range(3)))
  _,before=store.read()
  for i in range(3):
   assert post('/api/leave',requests[i],i)['replayed']
   assert post('/api/leave-decision',decisions[i],i)['replayed']
  _,after=store.read()
  assert before==after,'Replays changed stored values or queued extra mail'
  assert len(after['leaveRequests'])==3 and all(r['status']=='Approved' and r['revision']==2 for r in after['leaveRequests'].values())
  assert len(after['leaveOperations'])==6
  assert len(after['mailOutbox'])==6 and all(m['status']=='preview' for m in after['mailOutbox'].values())
  assert after['appointments']['synthetic-booking']['notes']=='Unrelated save 1' and after['reminderJob']=={'syntheticRun':1}
  assert not store.lose_ack,'Uncertain commit acknowledgement fixture was not exercised'
  return {'passed':True,'admins':3,'created':3,'approved':3,'receiptReplays':6,'mailEvents':6,'allMailPreviewOnly':True,'unrelatedWritesPreserved':True,'uncertainCommitRecovered':True,'storageConflictsRetried':store.conflicts,'httpRequestSeconds':{'min':min(durations),'max':max(durations)},'elapsedSeconds':round(time.perf_counter()-start,3)}
 finally:server.shutdown();server.server_close();thread.join(timeout=5)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--delay-ms',type=float,default=250);parser.add_argument('--bigquery-table');args=parser.parse_args()
 if not 0<=args.delay_ms<=2000:parser.error('--delay-ms must be between 0 and 2000')
 # This check must never publish live events or send real email.
 os.environ['SCHEDULE_LIVE_SECRET']=''
 if args.bigquery_table:
  if not re.fullmatch(r'[A-Za-z0-9_-]+\.[A-Za-z0-9_]+\.trident_leave_test_[a-f0-9]{32}',args.bigquery_table):parser.error('Cloud test table must end in trident_leave_test_ followed by a new UUID hex value')
  os.environ['BIGQUERY_TABLE']=args.bigquery_table;actual=BigQueryStore();table=actual.bq.Table(args.bigquery_table,schema=[actual.bq.SchemaField('id','STRING'),actual.bq.SchemaField('revision','INT64'),actual.bq.SchemaField('state','JSON')]);table.expires=dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=1)
  # Existing tables are an error, even if their names satisfy the guard.
  actual.client.create_table(table,exists_ok=False)
  try:
   actual.initialise(synthetic_state());result=run(DelayedStore(actual,args.delay_ms/1000));result.update(storage='isolated synthetic BigQuery table',latency='hosted HTTP/storage measurements with additional injected delay',injectedDelayPerReadAndCommitMs=args.delay_ms)
  finally:actual.client.delete_table(args.bigquery_table,not_found_ok=True)
 else:
  directory=TestDirectory()
  try:
   actual=SQLiteStore(str(directory.path/'state.db'));actual.initialise(synthetic_state());result=run(DelayedStore(actual,args.delay_ms/1000));result.update(storage='disposable SQLite',latency='simulated storage latency; not a cloud measurement',injectedDelayPerReadAndCommitMs=args.delay_ms)
  finally:directory.cleanup()
 print(json.dumps(result,indent=2))

if __name__=='__main__':main()
