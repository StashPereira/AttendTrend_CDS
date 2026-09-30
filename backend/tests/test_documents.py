import io
from PIL import Image
from reportlab.pdfgen import canvas
from app.services.documents import validate_bytes, extract, parse
from app.worker import process_one


def test_pdf_extraction(tmp_path):
    path = tmp_path / "attendance.pdf"
    c = canvas.Canvas(str(path))
    c.drawString(50, 750, "M101 Mathematics 8 / 10 2020-01-31")
    c.save()
    validate_bytes(path.name, path.read_bytes(), 10 * 1024 * 1024)
    rows = parse(extract(path), "attendance")["rows"]
    assert rows[0]["attended"] == 8 and rows[0]["conducted"] == 10


def test_image_ocr(tmp_path):
    from PIL import ImageDraw, ImageFont

    im = Image.new("RGB", (1800, 160), "white")
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 38)
    ImageDraw.Draw(im).text(
        (20, 45), "M101 Mathematics Monday 09:00 - 10:00 Room1", fill="black", font=font
    )
    path = tmp_path / "timetable.png"
    im.save(path)
    validate_bytes(path.name, path.read_bytes(), 10 * 1024 * 1024)
    text = extract(path)
    assert "Mathematics" in text
    rows = parse(text, "timetable")["rows"]
    assert rows[0]["weekday"] == 0 and rows[0]["start_time"] == "09:00"


def test_calendar_parser():
    rows = parse(
        "2020-01-26 holiday Republic Day\n2020-03-01 - 2020-03-05 exam Midterms",
        "calendar",
    )["rows"]
    assert len(rows) == 2 and rows[1]["end_date"] == "2020-03-05"


def test_unrecognized_document_has_no_fabricated_rows():
    data = parse("A completely unrelated document", "attendance")
    assert data["rows"] == [] and len(data["warnings"]) > 0
