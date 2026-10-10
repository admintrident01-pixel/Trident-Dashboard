import copy,json,os,re,sqlite3
from pathlib import Path
from contextlib import closing
from core import Problem
class SQLiteStore:
 def __init__(self,path):self.path=path
 def read(self):
  with closing(sqlite3.connect(self.path)) as c, c:row=c.execute('SELECT revision,state FROM app_state WHERE id=1').fetchone()
  if not row:raise Problem(503,'Upload your initial workbook using the setup script.')
  return row[0],json.loads(row[1])
 def commit(self,revision,state):
  with closing(sqlite3.connect(self.path)) as c, c:
   return c.execute('UPDATE app_state SET revision=revision+1,state=? WHERE id=1 AND revision=?',(json.dumps(state),revision)).rowcount==1
 def initialise(self,state):
  with closing(sqlite3.connect(self.path)) as c, c:
   c.execute('CREATE TABLE IF NOT EXISTS app_state(id INTEGER PRIMARY KEY,revision INTEGER,state TEXT)');c.execute('INSERT INTO app_state VALUES(1,1,?)',(json.dumps(state),))
class BigQueryStore:
 def __init__(self):
  from google.cloud import bigquery
  self.bq=bigquery;self.client=bigquery.Client();self.table=os.environ['BIGQUERY_TABLE']
  if not re.fullmatch(r'[a-zA-Z0-9_-]+\.[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+',self.table):raise ValueError('Invalid BigQuery table')
 def read(self):
  rows=list(self.client.query(f"SELECT revision,TO_JSON_STRING(state) AS state FROM `{self.table}` WHERE id='main'").result())
  if len(rows)!=1:raise Problem(503,'Initialise the online workbook once using the setup script.')
  return rows[0].revision,json.loads(rows[0].state)
 def commit(self,revision,state):
  payload=json.dumps(state)
  if len(payload)>8*1024*1024:raise Problem(413,'Online register has reached its configured size limit. Contact the administrator before adding more quotes.')
  config=self.bq.QueryJobConfig(query_parameters=[self.bq.ScalarQueryParameter('state','STRING',payload),self.bq.ScalarQueryParameter('revision','INT64',revision)])
  job=self.client.query(f"UPDATE `{self.table}` SET revision=revision+1,state=PARSE_JSON(@state) WHERE id='main' AND revision=@revision",job_config=config);job.result();return job.num_dml_affected_rows==1
 def initialise(self,state):
  # Run once, before deploying. Concurrent initialisation is not supported.
  if list(self.client.query(f"SELECT id FROM `{self.table}` LIMIT 1").result()):raise ValueError('Online storage already initialised; refusing to overwrite it.')
  config=self.bq.QueryJobConfig(query_parameters=[self.bq.ScalarQueryParameter('state','STRING',json.dumps(state))])
  self.client.query(f"INSERT INTO `{self.table}` (id,revision,state) VALUES ('main',1,PARSE_JSON(@state))",job_config=config).result()
class LocalObjects:
 def __init__(self,path):self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True)
 def put(self,key,data):p=self.path/key;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 def get(self,key):return (self.path/key).read_bytes()
 def delete(self,key):(self.path/key).unlink(missing_ok=True)
class CloudObjects:
 def __init__(self):
  from google.cloud import storage
  self.bucket=storage.Client().bucket(os.environ['PDF_BUCKET'])
 def put(self,key,data):self.bucket.blob(key).upload_from_string(data,content_type='application/pdf',if_generation_match=0)
 def get(self,key):return self.bucket.blob(key).download_as_bytes()
 def delete(self,key):self.bucket.blob(key).delete()
