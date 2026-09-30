"""Dated academic-calendar rows, including wrapped date ranges."""
import re
from datetime import datetime

DATE = r'\d{1,2}[/-]\d{1,2}[/-]\d{4}'
START = re.compile(r'^\s*(' + DATE + r')\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b', re.I | re.M)
MONTH = re.compile(r'^(January|February|March|April|May|June|July|August|September|October|November|December|\d+)$', re.I)


def day(value):
    return datetime.strptime(value.replace('-', '/'), '%d/%m/%Y').date()


def parse_calendar_report(text):
    starts = list(START.finditer(text))
    if not starts:
        return None
    rows, warnings = [], ['Calendar dates and event types are suggestions. Review the selected semester, vacation ranges and exam applicability. Exams and general events do not automatically cancel lectures.']
    for i, match in enumerate(starts):
        end = starts[i+1].start() if i+1 < len(starts) else len(text)
        chunk = text[match.end():end]
        chunk = re.split(r'\*\*\*|The calendar is tentative|Principal\s*$', chunk, flags=re.I)[0]
        lines = [s.strip() for s in chunk.splitlines() if s.strip() and not MONTH.fullmatch(s.strip())]
        title = ' '.join(lines)
        if not title:
            warnings.append(f'Activity for {match[1]} was not recognized; add it manually.')
            continue
        try:
            first = last = day(match[1])
            ranges = re.finditer('(' + DATE + r')\s*(?:to|[-–])\s*(' + DATE + ')', title, re.I)
            for dates in ranges:
                if day(dates[1]) == first:
                    last = day(dates[2])
                    break
            if last < first:
                raise ValueError()
        except ValueError:
            warnings.append(f'Invalid date range at {match[1]}; enter the correct dates manually.')
            continue
        if first.strftime('%A').lower() != match[2].lower():
            warnings.append(f'{match[1]} does not match its printed weekday ({match[2]}). Verify the source year/date; it was not silently changed.')
        kind = 'holiday' if re.search(r'public\s*holiday|vacation|(?:mid\s*term|winter)\s*break', title, re.I) else 'exam' if re.search(r'\bexam|examination|\bCIA[-–]', title, re.I) else 'event'
        if re.search(r'Last day of teaching', title, re.I):
            warnings.append(f'Teaching ends on {first.isoformat()}. Check your semester end date so classes are not generated after teaching finishes.')
        if len(title) > 150:
            warnings.append(f'Activity title for {match[1]} was shortened to fit the editor. Consult the full extracted text for details.')
        rows.append(dict(title=title[:150], start_date=first.isoformat(), end_date=last.isoformat(), kind=kind))
    return {'rows': rows, 'warnings': warnings, 'method': 'dated academic-calendar table; human review required'}
