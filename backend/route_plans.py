"""Durable, generation-checked travel plans shared by server workers.

Separate from the business register: reading/calculating a journey must not change
booking revisions, identities, history or Undo/Redo. No credentials are stored.
"""
import copy, hashlib, json, os, sqlite3, threading, time, uuid
from pathlib import Path
from contextlib import closing

PREFIX='routing-plans/v1/'
_stores={}
_store_lock=threading.Lock()

def key(origin,destination):
    values=[' '.join(v.split()).casefold() for v in (origin,destination)]
    return hashlib.sha256(json.dumps(values+['DRIVE','TRAFFIC_UNAWARE','NZ']).encode()).hexdigest()

class MemoryStore:
    def __init__(self):self.rows={};self.lock=threading.Lock()
    def read(self,name):
        with self.lock:return copy.deepcopy(self.rows.get(name,(0,None)))
    def write(self,name,generation,value):
        with self.lock:
            if self.rows.get(name,(0,None))[0]!=generation:return None
            self.rows[name]=(generation+1,copy.deepcopy(value));return generation+1

class SQLiteStore:
    def __init__(self,path):
        self.path=str(path)
        with closing(sqlite3.connect(self.path)) as db,db:db.execute('CREATE TABLE IF NOT EXISTS route_plans(name TEXT PRIMARY KEY,generation INTEGER,value TEXT)')
    def read(self,name):
        with closing(sqlite3.connect(self.path)) as db:row=db.execute('SELECT generation,value FROM route_plans WHERE name=?',(name,)).fetchone()
        return (row[0],json.loads(row[1])) if row else (0,None)
    def write(self,name,generation,value):
        with closing(sqlite3.connect(self.path)) as db,db:
            if generation:
                changed=db.execute('UPDATE route_plans SET generation=generation+1,value=? WHERE name=? AND generation=?',(json.dumps(value),name,generation)).rowcount
            else:changed=db.execute('INSERT OR IGNORE INTO route_plans VALUES(?,1,?)',(name,json.dumps(value))).rowcount
        return generation+1 if changed else None

class CloudStore:
    def __init__(self,bucket):
        from google.cloud import storage
        self.bucket=storage.Client().bucket(bucket)
    def read(self,name):
        from google.api_core.exceptions import NotFound,PreconditionFailed
        blob=self.bucket.blob(PREFIX+name+'.json')
        for attempt in range(3):
            try:
                blob.reload(timeout=5);generation=int(blob.generation)
                return generation,json.loads(blob.download_as_bytes(if_generation_match=generation,timeout=5))
            except NotFound:return 0,None
            except PreconditionFailed:
                if attempt==2:raise
    def write(self,name,generation,value):
        from google.api_core.exceptions import PreconditionFailed
        blob=self.bucket.blob(PREFIX+name+'.json')
        try:
            blob.upload_from_string(json.dumps(value),content_type='application/json',if_generation_match=generation,timeout=5)
            return int(blob.generation)
        except PreconditionFailed:return None

def store():
    local=os.environ.get('TRIDENT_LOCAL_DATA');bucket=os.environ.get('PDF_BUCKET')
    identity=('local',local) if local else ('cloud',bucket) if bucket else ('memory',None)
    with _store_lock:
        if identity not in _stores:
            if local:
                Path(local).mkdir(parents=True,exist_ok=True)
                _stores[identity]=SQLiteStore(Path(local)/'routing-plans.sqlite3')
            elif bucket:_stores[identity]=CloudStore(bucket)
            else:_stores[identity]=MemoryStore()
        return _stores[identity]

def result(record):
    if not record:return None
    if record.get('status') in ('ready','failed'):return copy.deepcopy(record['result'])
    previous=copy.deepcopy(record.get('previous') or {})
    if time.time()-record.get('createdAt',0)<60:return {**previous,'pending':True}
    return {**previous,'error':'The previous travel calculation did not finish. Choose Recalculate to try again.','defaultDuration':previous.get('duration',15)}

def claim(backend,name,generation,record,force=False):
    # A crashed or failed calculation is never automatically charged again.
    # Only a deliberate recalculation may replace an existing plan.
    if record and (not force or record.get('status')=='pending' and time.time()-record.get('createdAt',0)<60):return None,result(record)
    previous=(record or {}).get('result') if (record or {}).get('status')=='ready' else (record or {}).get('previous')
    value={'status':'pending','createdAt':time.time(),'requestId':str(uuid.uuid4()),**({'previous':previous} if previous else {})}
    claimed=backend.write(name,generation,value)
    if claimed is None:return None,result(backend.read(name)[1]) or {'pending':True}
    return (claimed,value),None

def finish(backend,name,lease,value):
    generation,pending=lease
    # A failed explicit retry must not erase the last successful travel plan.
    saved=pending['previous'] if 'duration' not in value and pending.get('previous') else value
    record={'status':'ready' if 'duration' in saved else 'failed','createdAt':pending['createdAt'],'calculatedAt':time.time(),'result':saved}
    return backend.write(name,generation,record)
