"""Server-only routing with durable plans; refreshes never renew saved journeys."""
import json, math, os, re, time, urllib.request, urllib.error, threading, logging
import route_plans
from pathlib import Path

_cache={}
_itinerary_cache={}
_lock=threading.Lock()
_request_locks=[threading.Lock() for _ in range(64)]
_controls_signature=None

def observe_controls(controls):
    """A deliberate shared travel edit invalidates worker-local copies only.

    Reload the durable plan after another worker recalculates it, without making
    another Google request. Unchanged polling does not touch shared storage.
    """
    global _controls_signature
    signature=json.dumps(controls,sort_keys=True,separators=(',',':'))
    with _lock:
        if _controls_signature is not None and signature!=_controls_signature:
            _cache.clear();_itinerary_cache.clear()
        _controls_signature=signature

def configuration():
    local={}
    if os.environ.get('TRIDENT_LOCAL_DATA'):
        try:local=json.loads((Path(os.environ['TRIDENT_LOCAL_DATA'])/'travel-routing.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
    return {'key':os.environ.get('GOOGLE_ROUTES_API_KEY') or local.get('key',''),'depot':os.environ.get('TRIDENT_DEPOT_ADDRESS') or local.get('depot','255 Port Road, Whangarei')}

def rounded_minutes(seconds):
    return max(0,math.ceil(float(seconds)/900)*15)

def missing_location(value):
    if not isinstance(value,str) or not value.strip():return True
    value=' '.join(re.sub(r'[^a-z0-9]+',' ',value.casefold()).split())
    placeholders={'','tbc','t b c','tba','t b a','tbd','t b d','to be confirmed','to be advised','to be determined','unknown','not known','not confirmed','not provided','not supplied','not available','none','nil','na','n a','no address','no location','no fixed address'}
    return value in placeholders or any(value.startswith(label+' ') and value[len(label)+1:] in placeholders for label in ('address','location','site','destination','client address'))

def estimate(origin,destination,force=False,cache_only=False):
    # Check before cache/config/provider lookup: old guessed routes must never win.
    if missing_location(origin) or missing_location(destination):
        return {'error':'Location not confirmed. Default travel is 0.25 hours; add a real address to calculate it.','defaultDuration':15,'locationMissing':True}
    if force:
        with _lock:_itinerary_cache.clear()
    cache_key=tuple(' '.join(value.split()).casefold() for value in (origin,destination))
    with _lock:
        cached=_cache.get(cache_key)
        if not force and cached and cached[0]>time.monotonic():return cached[1].copy()
        if not force and not cache_only and cached and 'duration' in cached[1]:return cached[1].copy()
    # The bookings-only response stays non-blocking. The route response loads
    # durable plans in the background after a worker restart, without Google.
    if cache_only:return {**cached[1],'pending':True} if cached else {'pending':True}
    name=route_plans.key(origin,destination)
    with _request_locks[int(name[:8],16)%len(_request_locks)]:
        with _lock:
            cached=_cache.get(cache_key)
            if not force and cached and (cached[0]>time.monotonic() or 'duration' in cached[1]):return cached[1].copy()
        try:
            backend=route_plans.store();generation,record=backend.read(name)
            if record and not force:result=route_plans.result(record)
            else:
                config=configuration()
                if not config['key']:return {'error':'Automatic routing is not configured.'}
                lease,result=route_plans.claim(backend,name,generation,record,force=force)
        except Exception:
            logging.warning('Travel plan storage unavailable; Google Maps was not called.')
            return {'error':'Saved travel calculations are temporarily unavailable. Google Maps was not called.','defaultDuration':15}
        if (not record or force) and lease:
            result=_provider(origin,destination,config)
            try:route_plans.finish(backend,name,lease,result)
            except Exception:logging.warning('Travel plan could not be saved; automatic provider retry is blocked by its reservation.')
            # Keep a good saved plan when a deliberate retry fails.
            remembered=lease[1].get('previous') if 'duration' not in result else None
            if remembered:
                with _lock:_cache[cache_key]=(float('inf'),remembered.copy())
                return result.copy()
        if not result.get('pending'):
            with _lock:
                if len(_cache)>=1000:_cache.pop(next(iter(_cache)))
                _cache[cache_key]=(float('inf'),result.copy())
        return result.copy()

def _provider(origin,destination,config):
    body={'origin':{'address':origin},'destination':{'address':destination},'travelMode':'DRIVE','routingPreference':'TRAFFIC_UNAWARE','regionCode':'NZ'}
    req=urllib.request.Request('https://routes.googleapis.com/directions/v2:computeRoutes',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Goog-Api-Key':config['key'],'X-Goog-FieldMask':'routes.duration,routes.distanceMeters'})
    try:
        with urllib.request.urlopen(req,timeout=5) as response:payload=json.load(response)
        route=payload.get('routes',[None])[0]
        if not route:raise ValueError('No route')
        seconds=float(route['duration'].removesuffix('s'))
        result={'duration':rounded_minutes(seconds),'seconds':seconds,'distanceMeters':route.get('distanceMeters')}
    except urllib.error.HTTPError as exc:
        # Read only the reason code; never expose response bodies or credentials.
        try:reasons=[d.get('reason') for d in json.load(exc).get('error',{}).get('details',[])]
        except (ValueError,OSError):reasons=[]
        result={'error':{400:'Google could not find this route. Check the addresses.',401:'Google rejected the routing key.',403:'Google Routes access was denied. Check API activation, billing and key restrictions.',429:'Google Routes quota reached. Try again later.'}.get(exc.code,'Google Routes is unavailable. Try again later.')}
        if 'SERVICE_DISABLED' in reasons:result={'error':'Google Routes API is disabled for this key. Enable Routes API in Google Cloud.'}
    except (OSError,ValueError,KeyError,IndexError,TypeError,AttributeError,OverflowError):result={'error':'Travel could not be calculated. Check the addresses or try again.'}
    return result.copy()


def itinerary_totals(appointments,names,depot=None,travel_overrides=None,date=None,cache_only=False):
    """Planned depot-to-depot distances; never present partial estimates as totals."""
    from concurrent.futures import ThreadPoolExecutor
    depot=depot or configuration()['depot'];legs={}
    for name in names:
        rows=sorted([a for a in appointments if not a.get('cancelled') and not a.get('source') and name in a.get('technicians',[a.get('technician')])],key=lambda a:(a['start'],a['id']))
        stops=[depot]
        for a in rows:
            import schedule as s
            if (travel_overrides or {}).get(s.travel_id(date,name,a['id'],'before'),{}).get('workshop') and stops[-1]!=depot:stops.append(depot)
            stops.append(a.get('address',''))
            if (travel_overrides or {}).get(s.travel_id(date,name,a['id'],'after'),{}).get('workshop'):stops.append(depot)
        if stops[-1]!=depot:stops.append(depot)
        legs[name]=list(zip(stops,stops[1:])) if rows else []
    cache_key=tuple((name,tuple(values)) for name,values in legs.items())
    with _lock:
        cached=_itinerary_cache.get(cache_key)
        if cached and cached[0]>time.monotonic():return {name:value.copy() for name,value in cached[1].items()}
    if cache_only and cached:return {name:{**value,'pending':True} for name,value in cached[1].items()}
    pairs=list({pair for values in legs.values() for pair in values})
    with ThreadPoolExecutor(max_workers=4) as pool:estimates=dict(zip(pairs,pool.map(lambda pair:estimate(*pair,cache_only=True) if cache_only else estimate(*pair),pairs)))
    result={}
    for name,values in legs.items():
        known=[estimates[pair].get('distanceMeters') for pair in values if not estimates[pair].get('error') and isinstance(estimates[pair].get('distanceMeters'),(int,float)) and estimates[pair]['distanceMeters']>=0]
        complete=len(known)==len(values)
        result[name]={'distanceMeters':sum(known) if complete else None,'knownDistanceMeters':sum(known),'complete':complete,'legCount':len(values),'knownLegs':len(known),**({'pending':True} if any(estimates[pair].get('pending') for pair in values) else {})}
    if cache_only:return result
    with _lock:
        if len(_itinerary_cache)>=128:_itinerary_cache.clear()
        _itinerary_cache[cache_key]=(time.monotonic()+(900 if all(v['complete'] for v in result.values()) else 60),{name:value.copy() for name,value in result.items()})
    return result
