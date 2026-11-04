"""Explicit communication markers; never sends mail or alters free-text notes."""
import copy
from core import Problem

KEYS={'voicemail','text','email'}

def saved(data,old):
    value=data.get('contactStatus',(old or {}).get('contactStatus',{}))
    if not isinstance(value,dict) or set(value)-KEYS or any(type(v) is not bool for v in value.values()):
        raise Problem(400,'Use Yes or No for each contact marker.')
    return copy.deepcopy(value)
