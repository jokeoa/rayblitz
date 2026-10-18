"""Per-analysis immutable people and independently trusted frame associations."""
import io
from bisect import bisect_right
from contextvars import ContextVar

from PIL import Image, ImageDraw

current: ContextVar[dict | None] = ContextVar('person_tracks', default=None)
objects: ContextVar[dict | None] = ContextVar('tabletop_objects', default=None)


def row_at(t: float) -> dict | None:
    data = current.get()
    if data is None: return None
    index = bisect_right([r['t'] for r in data['rows']], t+1e-8)-1
    if index < 0 or t-data['rows'][index]['t'] > 1.1/data['fps']:
        return None
    return data['rows'][index]


def banker_boxes(t: float, width: int) -> list[list[float]] | None:
    data = current.get()
    if data is None: return None
    row = row_at(t)
    if row is None: return []
    scale = width / data['info']['width']
    return [[v * scale for v in tr['box']] for tr in row['tracks']
            if tr['association']['usable_for_actions'] and
            data['people'].get(tr['person_id'], {}).get('role') == 'banker']


def frame_evidence(frame) -> tuple[bytes, str]:
    data = current.get()
    if data is None: return frame.path.read_bytes(), ''
    image = Image.open(frame.path).convert('RGB')
    draw = ImageDraw.Draw(image)
    scale = image.width / data['info']['width']
    descriptions = []
    for tr in (row_at(frame.t) or {'tracks': []})['tracks']:
        pid = tr['person_id']
        supported = tr['association']['usable_for_actions']
        classification = tr['classification']
        role = classification['role']
        if classification['possible_reflection']:
            role = 'possible reflection'
        elif pid and data['people'][pid]['initialized_at'] > frame.t:
            role = 'unknown'
        label = f'{pid if supported else "T" + str(tr["id"])} {role}'
        box = [round(v * scale) for v in tr['box']]
        color = '#15b38b' if role == 'banker' else '#e8b64c' if role == 'customer' else '#aab2bc'
        draw.rectangle(box, outline=color, width=2)
        draw.text((box[0], max(0, box[1] - 12)), label, fill=color, stroke_width=1, stroke_fill='black')
        descriptions.append(label)
    stream = io.BytesIO(); image.save(stream, format='JPEG', quality=92)
    hint = ('Scene geometry / reviewed opening-frame roles with separate frame association: ' + ', '.join(descriptions) +
            '. Roles stay fixed for each P ID. Unknown boxes cannot establish an employee-specific violation. '
            'Possible reflections are not additional people. A missing or uncertain box is not proof of departure; verify the visible action. '
            'Object class proposals, especially money, card and packaging, are uncertain and cannot alone establish a violation.')
    return stream.getvalue(), hint


def desk_events(rows: list[dict], zone: list[float] | None, width: int) -> dict | None:
    if current.get() is None: return None
    counts, leaves, arrivals, empty = [], [], [], []
    previous, start = None, None
    overlaps = lambda b: b[0] < zone[2] and b[2] > zone[0] and b[1] < zone[3] and b[3] > zone[1]
    for row in rows:
        boxes = banker_boxes(row['t'], width)
        if zone is None:
            inside = None
        elif boxes:
            inside = int(any(overlaps(b) for b in boxes))
        elif 'objects' in row and not any(o['label'] == 'person' and overlaps(o['box']) for o in row['objects']):
            inside = 0
        else:
            inside = None
        counts.append(inside)
        if previous == 1 and inside == 0: leaves.append(row['t'])
        if previous == 0 and inside == 1: arrivals.append(row['t'])
        if inside == 0 and start is None: start = row['t']
        if inside != 0 and start is not None:
            if row['t'] - start >= 1.: empty.append([start, row['t']])
            start = None
        previous = inside
    if start is not None and rows[-1]['t'] - start >= 1.: empty.append([start, rows[-1]['t']])
    return {'zone': zone, 'counts': counts, 'leaves': leaves, 'arrivals': arrivals, 'empty': empty,
            'basis': 'supported_banker_tracks_only; missing identity never proves absence'}
