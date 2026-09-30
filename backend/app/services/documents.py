"""Bounded extraction and conservative parsing. Human-reviewed rows are authoritative."""

import csv
import os
import shutil
import io
import re
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from .attendance_reports import parse_attendance_summary
from .calendar_reports import parse_calendar_report
from .timetable_reports import extract_grid, parse_grid

Image.MAX_IMAGE_PIXELS = 20_000_000


def validate_bytes(name, content, max_bytes):
    if not content or len(content) > max_bytes:
        raise ValueError("File must be non-empty and at most 10 MB")
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise ValueError("Invalid PDF signature")
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted or len(reader.pages) > 60:
            raise ValueError("PDF must be unencrypted and contain at most 60 pages")
    elif suffix in (".png", ".jpg", ".jpeg"):
        with Image.open(io.BytesIO(content)) as im:
            if im.format not in ("PNG", "JPEG") or im.width * im.height > 20_000_000:
                raise ValueError("Only PNG/JPEG images up to 20 megapixels")
            im.verify()
    elif suffix in (".csv", ".txt"):
        content.decode("utf-8-sig")
    else:
        raise ValueError("Supported: PDF, PNG, JPEG, UTF-8 CSV or TXT")
    return suffix


def ocr(path):
    executable = os.environ.get('TESSERACT_CMD') or shutil.which('tesseract')
    if not executable and os.name == 'nt':
        candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Tesseract-OCR/tesseract.exe'
        if candidate.exists(): executable = str(candidate)
    if not executable:
        raise RuntimeError('OCR_UNAVAILABLE: This document is a scan. Install Tesseract OCR, or upload the reviewed timetable CSV instead. Restart AttendTrend after installation. You can also set TESSERACT_CMD to tesseract.exe.')
    result = subprocess.run(
        [executable, str(path), "stdout", "--psm", "6"],
        capture_output=True,
        timeout=45,
        check=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def extract(path, kind=None):
    path = Path(path)
    if path.suffix == ".pdf":
        reader = PdfReader(path)
        parts = []
        for index, page in enumerate(reader.pages):
            text = (page.extract_text(extraction_mode="layout") if kind == "calendar" else page.extract_text()) or ""
            if len(text.strip()) < 15:
                with tempfile.TemporaryDirectory() as temp:
                    def read_image(image):
                        target = Path(temp) / 'cell.png'
                        image.save(target)
                        return ocr(target)
                    # Image-only PDFs commonly embed the entire scanned page.
                    # Reading that image avoids requiring Poppler on Windows.
                    images = list(page.images)
                    if len(images) == 1:
                        image = images[0].image
                        try:
                            text = extract_grid(image, read_image) if kind == 'timetable' else None
                            text = text or read_image(image.resize((image.width*3, image.height*3)))
                        except RuntimeError as exc:
                            if str(exc).startswith('OCR_UNAVAILABLE:'):
                                text = 'IMPORT_WARNING: ' + str(exc)
                            else: raise
                        parts.append(text)
                        continue
                    prefix = Path(temp) / "page"
                    subprocess.run(
                        [
                            "pdftoppm",
                            "-f",
                            str(index + 1),
                            "-l",
                            str(index + 1),
                            "-scale-to",
                            "2000",
                            "-png",
                            "-singlefile",
                            str(path),
                            str(prefix),
                        ],
                        timeout=45,
                        check=True,
                        capture_output=True,
                    )
                    text = ocr(prefix.with_suffix(".png"))
            parts.append(text)
        return "\n".join(parts)
    if path.suffix in (".png", ".jpg", ".jpeg"):
        try:
            return ocr(path)
        except RuntimeError as exc:
            if str(exc).startswith('OCR_UNAVAILABLE:'):
                return 'IMPORT_WARNING: ' + str(exc)
            raise
    return path.read_text(encoding="utf-8-sig")


WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def parse(text, kind):
    """CSV headers are the reliable interchange format. Text/OCR patterns are suggestions."""
    text = text[:500_000]
    warnings = [line.removeprefix("IMPORT_WARNING: ") for line in text.splitlines() if line.startswith("IMPORT_WARNING: ")]
    rows = []
    headers = {
        "attendance": {"code", "name", "attended", "conducted", "through_date"},
        "timetable": {"code", "name", "weekday", "start_time", "end_time"},
        "calendar": {"title", "start_date", "end_date", "kind"},
    }[kind]
    try:
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames and headers.issubset(
            {h.strip().lower() for h in reader.fieldnames}
        ):
            for row in reader:
                clean = {
                    k.strip().lower(): (v or "").strip() for k, v in row.items() if k
                }
                if kind == "attendance":
                    clean = {k: clean[k] for k in headers} | {
                        'kind': clean.get('kind') or 'theory',
                        'instructor': clean.get('instructor', ''),
                    }
                    clean["attended"] = int(clean["attended"])
                    clean["conducted"] = int(clean["conducted"])
                elif kind == "timetable":
                    clean = {k: clean[k] for k in headers} | {
                        "room": clean.get("room", "")
                    }
                    clean["weekday"] = WEEKDAYS.get(
                        clean["weekday"][:3].lower(), clean["weekday"]
                    )
                    clean["weekday"] = int(clean["weekday"])
                else:
                    clean = {k: clean[k] for k in headers}
                rows.append(clean)
    except (ValueError, TypeError):
        warnings.append(
            "Some CSV values require correction. Review the extracted text."
        )
    if not rows and kind == 'timetable':
        report = parse_grid(text)
        if report is not None:
            return report | {'text': text[:20000]}
    if not rows and kind == 'calendar':
        report = parse_calendar_report(text)
        if report is not None:
            return report | {'text': text[:20000]}
    if not rows and kind == 'attendance':
        report = parse_attendance_summary(text)
        if report is not None:
            return report | {'text': text[:20000]}
    if not rows:
        for line in text.splitlines():
            if kind == "attendance":
                match = re.fullmatch(
                    r"\s*([\w-]+)\s+(.+?)\s+(\d+)\s*[/, ]\s*(\d+)\s+(\d{4}-\d{2}-\d{2})\s*",
                    line,
                )
                if match:
                    code, name, a, c, day = match.groups()
                    rows.append(
                        dict(
                            code=code,
                            name=name,
                            attended=int(a),
                            conducted=int(c),
                            through_date=day,
                        )
                    )
            elif kind == "timetable":
                match = re.fullmatch(
                    r"\s*([\w-]+)\s+(.+?)\s+(Mon\w*|Tue\w*|Wed\w*|Thu\w*|Fri\w*|Sat\w*|Sun\w*)\s+(\d{2}:\d{2})\s*[-–]\s*(\d{2}:\d{2})(?:\s+(.+))?\s*",
                    line,
                    re.I,
                )
                if match:
                    code, name, weekday, start, end, room = match.groups()
                    rows.append(
                        dict(
                            code=code,
                            name=name,
                            weekday=WEEKDAYS[weekday[:3].lower()],
                            start_time=start,
                            end_time=end,
                            room=room or "",
                        )
                    )
            else:
                match = re.fullmatch(
                    r"\s*(\d{4}-\d{2}-\d{2})(?:\s*[-–]\s*(\d{4}-\d{2}-\d{2}))?\s+(holiday|exam|event)\s+(.+)",
                    line,
                    re.I,
                )
                if match:
                    start, end, typ, title = match.groups()
                    rows.append(
                        dict(
                            title=title,
                            start_date=start,
                            end_date=end or start,
                            kind=typ.lower(),
                        )
                    )
        warnings.append(
            "Text/OCR parsing is a suggestion. Verify every date, count, subject and time before confirming."
        )
    if not rows:
        warnings.append(
            "No structured rows recognized. Add rows manually using the review editor."
        )
    return {
        "rows": rows[:1000],
        "text": text[:20000],
        "warnings": warnings,
        "method": "extracted document; human review required",
    }
