"""Read-only appointment search across dates without routing-provider calls."""
from core import Problem

def search(state,params):
 query=params.get('q',[''])[0].strip()
 if not query:return {'results':[],'total':0}
 if len(query)>300:raise Problem(400,'Use a search of up to 300 characters.')
 terms=query.casefold().split();cancelled=params.get('cancelled',['0'])[0]=='1';rows=[]
 for row in state.get('appointments',{}).values():
  if row.get('source') or row.get('type','').strip().casefold()=='lunch' or row.get('cancelled') and not cancelled:continue
  staff=row.get('technicians') or [row.get('technician','')]
  text=' '.join(str(row.get(k,'')) for k in ('client','address','notes','type','date'))+' '+' '.join(staff)
  if not all(term in text.casefold() for term in terms):continue
  rows.append({**{key:row.get(key,'') for key in ('id','client','address','notes','type','date','start','duration','cancelled')},'technicians':staff})
 rows.sort(key=lambda row:(row['date'],row['start'],row['id']),reverse=True)
 return {'results':rows[:100],'total':len(rows)}
