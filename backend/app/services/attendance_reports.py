"""Parse numbered attendance-summary tables whose cells wrap across lines.

Only recognized T/P/A/% headers activate this parser. Counts and percentages
are cross-checked; document dates are suggestions that remain editable.
"""
import re
from datetime import datetime
from decimal import Decimal


HEADER = re.compile(r"\bT\s+P\s+A\s*%", re.I)
ROW_START = re.compile(r"^\s*(\d{1,4})\.(?:\s*\n|[ \t]+(?=[A-Za-z]))", re.M)
ROW = re.compile(
    r"^(?P<name>.+?)\s+(?P<kind>Theory|Practical)\s+"
    r"(?P<code>(?=[A-Z0-9_-]*\d)[A-Z][A-Z0-9_-]*(?:\s+[A-Z0-9_-]+)*?)\s+"
    r"(?P<credits>\d+\.\d{1,2})\s+(?P<faculty>.+?)\s+"
    r"(?P<total>\d+)\s+(?P<present>\d+)\s+(?P<absent>\d+)\s+"
    r"(?P<percentage>\d+(?:\.\d+)?)(?:\s*%)?$",
    re.I,
)
MONTHS = {name: i for i, name in enumerate(
    ['January', 'February', 'March', 'April', 'May', 'June', 'July',
     'August', 'September', 'October', 'November', 'December'], 1)}


def report_date(text):
    # Prefer an explicitly labelled attendance end/as-of date over print time.
    explicit = re.search(
        r"(?:as\s+of|through\s+date|to\s+date|attendance\s+(?:up\s+to|through))"
        r"\s*:?\s*(\d{4}-\d{2}-\d{2})", text, re.I,
    )
    if explicit:
        try:
            return datetime.strptime(explicit[1], '%Y-%m-%d').date().isoformat(), 'attendance date'
        except ValueError:
            pass
    stamp = re.search(
        r"(?:Summary\s+Time|Report\s+Date|Time)\s*:?\s*"
        r"(" + '|'.join(MONTHS) + r")\s+(\d{1,2}),?\s+(\d{4})", text, re.I,
    )
    if stamp:
        try:
            month = next(number for name, number in MONTHS.items() if name.lower() == stamp[1].lower())
            return datetime(int(stamp[3]), month, int(stamp[2])).date().isoformat(), 'report timestamp'
        except ValueError:
            pass
    return '', 'missing date'


def parse_attendance_summary(text):
    if not HEADER.search(text) or not re.search(r'Subject\s+Code', text, re.I):
        return None
    starts = list(ROW_START.finditer(text))
    if not starts:
        return None
    through, date_source = report_date(text)
    warnings = ['Recognized attendance table: T = conducted, P = present, A = absent. Review every extracted row.']
    if date_source == 'report timestamp':
        warnings.append(f'Through-date {through} is suggested from the report timestamp. Verify it is the last attendance date, and correct it if necessary.')
    elif not through:
        warnings.append('No attendance through-date recognized. Enter the correct date in every row before confirming.')
    rows = []
    seen = set()
    for i, match in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        chunk = text[match.end():end]
        chunk = re.split(r'^\s*SEM\s*:', chunk, flags=re.I | re.M)[0]
        fields = ROW.fullmatch(' '.join(chunk.split()))
        if not fields:
            warnings.append(f'Subject row {match[1]} could not be parsed safely. Add or correct that row manually.')
            continue
        values = fields.groupdict()
        total, present, absent = (int(values[k]) for k in ('total', 'present', 'absent'))
        reported = Decimal(values['percentage'])
        computed = Decimal(present) * 100 / total if total else Decimal(0)
        if total != present + absent or not 0 <= reported <= 100 or abs(computed - reported) > Decimal('0.06'):
            warnings.append(f'Subject row {match[1]} has inconsistent counts/percentage and was not accepted. Check the source.')
            continue
        code = re.sub(r'\s+', '', values['code']).upper()
        if code in seen:
            warnings.append(f'Duplicate course code {code} was not added again. Check repeated pages or rows.')
            continue
        seen.add(code)
        rows.append({'code': code, 'name': values['name'], 'kind': values['kind'].lower(),
                     'instructor': values['faculty'], 'attended': present, 'conducted': total,
                     'through_date': through})
    summary = re.search(r'\bSummary\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+(?:\.\d+)?)\s*%?\s*$', text, re.I)
    if summary and rows:
        total, present, absent = map(int, summary.group(1, 2, 3))
        if (sum(r['conducted'] for r in rows), sum(r['attended'] for r in rows)) != (total, present) or total != present + absent:
            warnings.append('Extracted row totals do not match the report summary. Resolve missing or inconsistent rows before confirming.')
    return {'rows': rows, 'warnings': warnings, 'method': 'numbered T/P/A attendance-summary table; human review required'}
