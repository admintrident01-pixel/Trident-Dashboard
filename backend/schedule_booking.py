"""Booking controls, including the owner's approved legacy interpretation.

Reads never migrate the register. Version 1 is stored only on an intentional edit.
"""
from core import Problem

STATUSES=('action-needed','confirmed','option')
LABELS={'action-needed':'Not booked','confirmed':'Booked','option':'Optional'}
# Owner's explicit decision, 28 October 2026, for the audited Fixed + Optional row.
LEGACY_NOT_BOOKED={'ba7a4325-00a6-46a1-8ec5-82549ca1f3df'}

def status(row):
    value=row.get('bookingStatus','action-needed')
    if row.get('bookingControlsVersion')==1:
        if value not in STATUSES:raise Problem(400,'Choose a valid booking status.')
        return value
    timing=row.get('timing','flexible')
    if value not in (*STATUSES,'high-priority') or timing not in ('fixed','flexible'):
        raise Problem(409,'An appointment has unrecognised old booking marks. Ask the owner before converting them.')
    if timing=='fixed' and value=='option':
        if row.get('id') in LEGACY_NOT_BOOKED:return 'action-needed'
        raise Problem(409,'An appointment is both Fixed and Optional. Ask the owner which booking status to keep.')
    return 'confirmed' if timing=='fixed' or value=='confirmed' else 'option' if value=='option' else 'action-needed'

def urgency(row):
    value=row.get('urgency','high' if row.get('bookingStatus')=='high-priority' else 'low')
    if value not in ('high','low'):raise Problem(400,'Choose High or Low urgency.')
    return value

def booked(row):
    if row.get('source'):return row.get('timing')=='fixed'
    return status(row)=='confirmed'

def controls(row):
    if not row or row.get('source'):return row
    value=status(row)
    return {**row,'bookingStatus':value,'urgency':urgency(row),'timing':'fixed' if value=='confirmed' else 'flexible','bookingControlsVersion':1}
