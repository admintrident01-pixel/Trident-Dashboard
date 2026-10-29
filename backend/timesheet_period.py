"""One active draft or submission per person and Monday; legacy history is retained."""
from core import Problem

def matches(state,name,week,exclude_submission=None,exclude_draft=None):
 if not isinstance(name,str) or not isinstance(week,str):return []
 result=[]
 for collection,draft,exclude in [('timesheets',False,exclude_submission),('timesheetDrafts',True,exclude_draft)]:
  for row in state.get(collection,{}).values():
   if row.get('id')!=exclude and row.get('technician','').strip().casefold()==name.strip().casefold() and row.get('weekStart')==week:result.append((row,draft))
 return result

def require_available(state,name,week,user=None,exclude_submission=None,exclude_draft=None):
 found=matches(state,name,week,exclude_submission,exclude_draft)
 if not found:return
 error=Problem(409,'A time sheet already exists for this person and week. Open the existing draft or submitted sheet instead.')
 error.details={'existingTimesheets':[{'id':row['id'],'technician':row['technician'],'weekStart':row['weekStart'],'isDraft':draft,'status':'Draft' if draft else 'Submitted','canOpen':not draft or user is None or user.get('role')=='admin' or row.get('owner')==user.get('email')} for row,draft in found]}
 raise error
