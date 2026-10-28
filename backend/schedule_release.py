"""Atomic header reassignment and explicit workshop journeys."""
import copy, datetime as dt
from core import Problem


def swap_headers(state, data, user):
    import schedule as s
    import schedule_links as links
    date = s.day(data.get('date'))
    first, second = data.get('fromTechnician'), data.get('toTechnician')
    names = s.settings(state)['technicianOrder']
    if first not in names or second not in names or first == second:
        raise Problem(400, 'Choose two different current technicians.')
    kinds = s.settings(state)['staffTypes']
    if kinds[first] != kinds[second]:
        raise Problem(409, 'Office staff must remain in the office columns.')
    mapping = {first: second, second: first}
    rename = lambda name: mapping.get(name, name)
    before = links.day_blocks(state, date)
    result = copy.deepcopy(state)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    affected = set()
    for block in before:
        if block.get('source') in ('leave', 'note', 'travel'):
            continue
        if not set(s.assigned(block)) & mapping.keys():
            continue
        technicians = [rename(name) for name in s.assigned(block)]
        result.setdefault('appointments', {})[block['id']] = {
            **block, 'technician': technicians[0], 'technicians': technicians,
            'version': block.get('version', 0) + 1, 'updatedAt': now, 'updatedBy': user['email']}
        affected.add(block['id'])
    # Preserve explicit/hidden travel and edge decisions through a bijective remap.
    id_map = {}
    candidates = s.travel_candidates(state, date)
    for block in candidates:
        if block['technician'] in mapping:
            id_map[block['id']] = s.travel_id(date, rename(block['technician']), block['anchorId'], block['side'])
    for collection in ('travelBlocks', 'scheduleHiddenTravel'):
        original = state.get(collection, {})
        target = result.setdefault(collection, {})
        for identifier in id_map:
            target.pop(identifier, None)
        for identifier, new_id in id_map.items():
            if identifier not in original:
                continue
            value = copy.deepcopy(original[identifier])
            if collection == 'travelBlocks':
                if value.get('technician'):
                    value['technician'] = rename(value['technician'])
                value.update(version=value.get('version', 0) + 1, updatedBy=user['email'])
            target[new_id] = value
    # Detached travel may be anchored in a different technician's column.
    for block in before:
        if block.get('source') == 'travel' and block['technician'] in mapping:
            identifier = id_map.get(block['id'], block['id'])
            if not block.get('linked', True):
                result.setdefault('travelBlocks', {}).setdefault(identifier, {}).update(
                    technician=rename(block['technician']), start=block['start'], linked=False,
                    date=date, duration=block['duration'], locked=block.get('locked', True))
    original_links = state.get('scheduleLinks', {})
    for key in original_links:
        parts = key.rsplit('|', 2)
        if len(parts) == 3 and (parts[1] in id_map or parts[2] in id_map or
                parts[1] in affected or parts[2] in affected):
            result.setdefault('scheduleLinks', {}).pop(key, None)
    for key, value in original_links.items():
        parts = key.rsplit('|', 2)
        if len(parts) == 3 and (parts[1] in id_map or parts[2] in id_map or
                parts[1] in affected or parts[2] in affected):
            result['scheduleLinks'][links.edge_id(rename(parts[0]), id_map.get(parts[1], parts[1]), id_map.get(parts[2], parts[2]))] = value
    saved_order = state.get('scheduleColumnOrders', {}).get(date, [])
    order = [name for name in saved_order if name in names] + [name for name in names if name not in saved_order]
    result.setdefault('scheduleColumnOrders', {})[date] = [rename(name) for name in order]
    after = links.day_blocks(result, date)
    after_ids = {block['id']: block for block in after}
    for old in before:
        if old.get('source') in ('leave', 'note') or not set(s.assigned(old)) & mapping.keys():
            continue
        new = after_ids.get(id_map.get(old['id'], old['id']))
        if not new or (new['start'], new['duration']) != (old['start'], old['duration']):
            raise Problem(409, 'This header change would change a travel time or remove a block. Review the route first.')
        if new.get('routeError') and new.get('routeError') != old.get('routeError'):
            raise Problem(409, 'A reassigned travel route could not be calculated. Review the route first.')
        for other in after:
            if new['id'] != other['id'] and s.overlaps(new, other):
                raise Problem(409, f"Cannot reassign {new['client']}: overlaps {other['client']} for {', '.join(s.assigned(new))}. No times or owners were changed.")
    return result


def workshop_travel(state, data, user):
    import schedule as s
    date = s.day(data.get('date'))
    name, side = data.get('technician'), data.get('side')
    if side not in ('before', 'after'):
        raise Problem(400, 'Choose travel from or to the workshop.')
    rows = sorted([b for b in s.read_without_travel(state, date)
                   if not b.get('source') and name in s.assigned(b)], key=lambda b: (b['start'], b['id']))
    minute = s.minutes(data.get('start'))
    candidates = [b for b in rows if (s.minutes(b['start']) >= minute if side == 'before'
                  else s.minutes(b['start']) + b['duration'] <= minute)]
    if not candidates:
        raise Problem(409, 'No appointment on this side of the clicked time. Book the appointment first.')
    anchor = candidates[0] if side == 'before' else candidates[-1]
    workshop = s.settings(state)['workshopAddress']
    origin, destination = (workshop, anchor['address']) if side == 'before' else (anchor['address'], workshop)
    route = s.schedule_routes.estimate(origin, destination, force=True)
    if 'duration' not in route:
        raise Problem(400, route.get('error', 'Travel could not be calculated. Check the addresses.'))
    duration = route['duration']
    if duration <= 0:
        raise Problem(400, 'These addresses need no driving time.')
    start = s.minutes(anchor['start']) - duration if side == 'before' else s.minutes(anchor['start']) + anchor['duration']
    if start < 0 or start + duration > 1440:
        raise Problem(409, 'Workshop travel would leave the selected day.')
    identifier = s.travel_id(date, name, anchor['id'], side)
    trial = {'id': identifier, 'technician': name, 'start': s.time_string(start), 'duration': duration}
    barriers = s.read_without_travel(state, date) + [b for b in s.travel_blocks(state, date) if b['id'] != identifier]
    if any(s.overlaps(trial, other) for other in barriers):
        raise Problem(409, 'Workshop travel overlaps a booking, travel, recurring note or approved leave. No blocks were moved.')
    result = copy.deepcopy(state)
    old = result.setdefault('travelBlocks', {}).get(identifier, {})
    result['travelBlocks'][identifier] = {**old, 'date': date, 'duration': duration,
        'start': trial['start'], 'workshop': True, 'locked': True, 'linked': True,
        'version': old.get('version', 0) + 1, 'updatedBy': user['email']}
    result.setdefault('scheduleHiddenTravel', {}).pop(identifier, None)
    before = {b['id']: b for b in s.travel_blocks(state, date)}
    after = s.travel_blocks(result, date)
    if not any(block['id'] == identifier for block in after):
        raise Problem(409, 'The workshop journey could not fit inside this day. No changes were saved.')
    barriers = s.read_without_travel(result, date)
    for block in after:
        previous = before.get(block['id'], {})
        fields = ('start', 'duration', 'origin', 'destination')
        if block['id'] == identifier or any(block.get(field) != previous.get(field) for field in fields):
            if block.get('routeError'):
                raise Problem(400, block['routeError'])
            if any(s.overlaps(block, other) for other in barriers + after if other['id'] != block['id']):
                raise Problem(409, 'Workshop and onward travel would overlap another block. No bookings were moved or changed.')
    return result


def header_preview(state, data, user):
    import schedule as s
    candidate = swap_headers(state, data, user)
    date = s.day(data.get('date'))
    previous = {b['id']: b for b in s.read_without_travel(state, date)}
    changes = [{'id': key, 'client': value['client'], 'start': value['start'],
                'duration': value['duration'], 'before': s.assigned(previous.get(key, value)),
                'after': s.assigned(value)} for key, value in candidate.get('appointments', {}).items()
               if value != state.get('appointments', {}).get(key)]
    mapping = {data['fromTechnician']: data['toTechnician'], data['toTechnician']: data['fromTechnician']}
    for block in s.travel_blocks(state, date):
        if block['technician'] in mapping:
            changes.append({'id': block['id'], 'client': block['client'], 'start': block['start'],
                            'duration': block['duration'], 'before': [block['technician']],
                            'after': [mapping[block['technician']]]})
    return {'changes': sorted(changes, key=lambda row: (row['start'], row['client']))}
