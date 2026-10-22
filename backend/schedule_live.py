"""Authenticated change notifications; business data stays in the API."""
import base64,hashlib,hmac,json,logging,os,secrets,time
from urllib.request import Request,urlopen

def configuration():
 secret=os.environ.get('SCHEDULE_LIVE_SECRET','')
 origin=os.environ.get('FRONTEND_ORIGIN','').rstrip('/')
 return secret,origin

def ticket():
 secret,origin=configuration()
 if len(secret)<32 or not origin.startswith('https://'):return {'enabled':False}
 expires=int(time.time())+300
 payload=base64.urlsafe_b64encode(json.dumps({'exp':expires,'room':'schedule','nonce':secrets.token_hex(12)},separators=(',',':')).encode()).decode().rstrip('=')
 signature=hmac.new(secret.encode(),payload.encode(),hashlib.sha256).hexdigest()
 return {'enabled':True,'ticket':payload+'.'+signature,'expires':expires}

def notify():
 secret,origin=configuration()
 if len(secret)<32 or not origin.startswith('https://'):return
 body=b'{"type":"schedule-changed"}'
 stamp=str(int(time.time()))
 signature=hmac.new(secret.encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
 try:
  request=Request(origin+'/__schedule-publish',data=body,headers={'Content-Type':'application/json','X-Schedule-Time':stamp,'X-Schedule-Signature':signature},method='POST')
  with urlopen(request,timeout=.75) as response:response.read(128)
 except Exception:logging.warning('Schedule live notification unavailable; automatic refresh remains active.')
