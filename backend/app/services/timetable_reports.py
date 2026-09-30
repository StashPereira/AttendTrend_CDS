"""OCR table cells separately to avoid reading across neighboring subjects."""
import json
import re
from PIL import Image

MARKER = 'ATTENDTREND_GRID_CELL '


def bands(values):
    groups = []
    for n in values:
        if not groups or n > groups[-1][-1] + 1:
            groups.append([n])
        else:
            groups[-1].append(n)
    return [round(sum(g)/len(g)) for g in groups if len(g) <= 3]


def extract_grid(image, ocr):
    im = image.convert('L')
    if im.width > 1600:
        im.thumbnail((1600, 1600))
    w, h = im.size
    pixels = im.load()
    lines = bands([y for y in range(h) if sum(pixels[x,y] < 205 for x in range(w)) > w * .8])
    # Six day rows; refuse unrelated tables rather than assigning invented weekdays.
    if len(lines) != 7:
        return None
    header_top = max(0, lines[0] - 12)
    columns = bands([x for x in range(w) if all(pixels[x,y] < 235 for y in range(header_top+1, lines[0]-1))])
    if len(columns) < 5:
        return None
    output = []
    recognized = 0
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
    for weekday, (top, bottom) in enumerate(zip(lines, lines[1:])):
        xs = [x for x in columns if max(
            sum(pixels[q,y] < 215 for y in range(top+2,bottom-2))/(bottom-top-4)
            for q in range(max(0,x-1), min(w,x+2))
        ) > .94]
        # Keep day-column boundaries even if a faint rule is lost in the scan.
        xs = sorted(set(xs + columns[:2] + columns[-1:]))
        if len(xs) < 3:
            return None
        def read(left, right):
            crop = im.crop((left+2, top+2, right-2, bottom-2)).convert('RGB')
            crop = crop.resize((crop.width*4,crop.height*4), Image.Resampling.LANCZOS)
            return ocr(crop)
        label = read(xs[0], xs[1]).strip().lower()
        if days[weekday] in label:
            recognized += 1
        # Restrict vertical boundaries to header columns to avoid treating
        # letters in a cell as a divider.
        for left,right in zip(xs[1:],xs[2:]):
            text = read(left,right)
            if text.strip():
                output.append(MARKER + json.dumps({'weekday':weekday,'text':text}))
    return '\n'.join(output) if recognized >= 4 else None


def parse_cell(text, weekday):
    lower = text.lower()
    if 'probability' in lower:
        name = 'PROBABILITY AND STOCHASTIC PROCESSES'
    elif re.search(r'd[be]ms', lower):
        name = 'DATABASE MANAGEMENT RELATIONAL'
    elif 'computing' in lower:
        name = 'COMPUTING FOR DATA SCIENCE'
    elif 'algebra' in lower:
        name = 'LINEAR ALGEBRA'
    elif 'programming' in lower:
        name = 'BASICS OF PROGRAMMING'
    elif 'statistical' in lower or 'methodology' in lower:
        name = 'RESEARCH METHODOLOGY AND STATISTICAL METHODS'
    else:
        return None
    if 'practical' in lower:
        name += ' PRACTICAL'
    match = re.search(r'(\d{1,2})(?:[.:,](\d{2}))?\s*(?:a\.?m\.?|p\.?m\.?)?\s*[-–]\s*(\d{1,2})(?:[.:,](\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?', lower)
    if not match:
        return None
    start, sm, end, em, suffix = match.groups()
    start, end, sm, em = int(start), int(end), int(sm or 0), int(em or 0)
    if start > 23 or end > 23 or sm > 59 or em > 59:
        return None
    # Daytime college timetable: 1–7 denotes afternoon; 8–11 morning.
    if start < 8: start += 12
    if end < 8: end += 12
    if suffix and suffix.startswith('p') and end < 12: end += 12
    if end*60+em <= start*60+sm or end*60+em-start*60-sm > 240:
        return None
    room = 'BDA Lab' if re.search(r'bda\s*lab', lower) else 'BDA Classroom' if re.search(r'bda\s*class', lower) else 'KC Lab' if re.search(r'kc\s*lab', lower) else ''
    return dict(code='', name=name, weekday=weekday, start_time=f'{start:02}:{sm:02}', end_time=f'{end:02}:{em:02}', room=room)


def parse_grid(text):
    if MARKER not in text:
        return None
    rows, skipped = [], 0
    for line in text.splitlines():
        if not line.startswith(MARKER): continue
        cell = json.loads(line[len(MARKER):])
        row = parse_cell(cell['text'], cell['weekday'])
        if row: rows.append(row)
        elif cell['text'].strip(): skipped += 1
    warnings = ['Scanned timetable: choose existing course codes, verify theory/practical assignments, AM/PM and every printed slot. OCR may miss cells. Each session counts as one lecture regardless of duration.']
    if skipped: warnings.append(f'{skipped} cell fragments could not be parsed. Compare all six days with the source and add missing slots.')
    return dict(rows=rows, warnings=warnings, method='cell-based scanned timetable OCR; human review required')
