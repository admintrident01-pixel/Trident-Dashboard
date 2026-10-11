"""Admin-managed calculator catalogue; prices are NZD excluding GST."""
import copy
from core import Problem
from quote_settings import text, num

CATEGORIES = ('consumables', 'parts', 'labour', 'travel', 'mileage')

def defaults():
    rows = [{'id':'consumables','category':'consumables','name':'Consumables','cost':20,'margin':0,'markup':0},
            {'id':'parts','category':'parts','name':'Parts','cost':0,'margin':0,'markup':0}]
    for category in ('labour','travel'):
        rows.extend({'id':f'{category}-{rate}','category':category,'name':f'{category.title()} ${rate}/hour','cost':rate,'margin':0,'markup':0} for rate in (91,95,110))
    rows.append({'id':'mileage','category':'mileage','name':'Fuel mileage','cost':1.2,'margin':0,'markup':0})
    return {'items': rows}

def read(state):
    config=copy.deepcopy(state.get('labourSettings',defaults()))
    for item in config['items']:item.setdefault('markup',0)
    return config

def save(state,data):
    if not isinstance(data,dict) or not isinstance(data.get('items'),list) or not 1<=len(data['items'])<=200:
        raise Problem(400,'Keep 1 to 200 calculator items.')
    rows=[];seen=set()
    for item in data['items']:
        if not isinstance(item,dict):raise Problem(400,'Invalid calculator item.')
        key=text(item.get('id'),'calculator item ID',80,True)
        if key in seen:raise Problem(400,'Calculator item IDs must be unique.')
        seen.add(key)
        if item.get('category') not in CATEGORIES:raise Problem(400,'Choose a valid calculator category.')
        rows.append({'id':key,'category':item['category'],'name':text(item.get('name'),'calculator item name',200,True).strip(),'cost':num(item.get('cost'),'base cost',0,1000000),'margin':num(item.get('margin'),'margin percent',0,99),'markup':num(item.get('markup',0),'markup percent',0,1000)})
    if any(not any(row['category']==category for row in rows) for category in CATEGORIES):
        raise Problem(400,'Keep at least one item in each calculator category.')
    result=copy.deepcopy(state);result['labourSettings']={'items':rows}
    return result
