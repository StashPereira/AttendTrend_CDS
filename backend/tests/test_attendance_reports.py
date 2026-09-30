"""Synthetic reports: no student documents or personal information."""
from app.services.documents import parse

HEADER = 'Summary Time\nJanuary 31, 2020\nSubject Code\nT\nP\nA\n%\nSEM :\nI\n'
ROW = '1.\nLINEAR ALGEBRA\nTheory\nTEST6001CR\n1\n3.00\nExample Faculty\n30\n22\n8\n73.33\n'
PRACTICAL = '2.\nLINEAR ALGEBRA PRACTICAL\nPractical\nTEST6001CR\n1PR\n1.00\nExample Faculty\n19\n13\n6\n68.42\n'


def test_wrapped_rows_and_summary():
    data = parse(HEADER + ROW + PRACTICAL + 'SEM :\nI\nSummary\n49\n35\n14\n71.43', 'attendance')
    assert len(data['rows']) == 2
    theory, practical = data['rows']
    assert theory['code'] == 'TEST6001CR1'
    assert theory['attended'] == 22 and theory['conducted'] == 30
    assert practical['code'] == 'TEST6001CR1PR'
    assert practical['name'] == 'LINEAR ALGEBRA PRACTICAL'
    assert practical['kind'] == 'practical'
    assert practical['instructor'] == 'Example Faculty'
    assert practical['through_date'] == '2020-01-31'
    assert any('timestamp' in w for w in data['warnings'])
    assert not any('totals do not match' in w for w in data['warnings'])


def test_wrapped_name_code_and_multiple_faculty():
    text = ROW.replace('LINEAR ALGEBRA', 'RESEARCH AND\nSTATISTICAL METHODS').replace('TEST6001CR\n1', 'TEST6001R\nM1').replace('Example Faculty', 'Faculty One , Faculty Two')
    row = parse(HEADER + text, 'attendance')['rows'][0]
    assert row['code'] == 'TEST6001RM1'
    assert row['name'] == 'RESEARCH AND STATISTICAL METHODS'
    assert row['instructor'] == 'Faculty One , Faculty Two'


def test_inconsistent_counts_not_accepted():
    data = parse(HEADER + ROW.replace('22\n8', '22\n9'), 'attendance')
    assert data['rows'] == []
    assert any('inconsistent' in w for w in data['warnings'])


def test_inconsistent_percentage_not_accepted():
    assert parse(HEADER + ROW.replace('73.33', '22.00'), 'attendance')['rows'] == []


def test_missing_date_requires_manual_date():
    data = parse('Subject Code\nT\nP\nA\n%\n' + ROW, 'attendance')
    assert data['rows'][0]['through_date'] == ''
    assert any('Enter the correct date' in w for w in data['warnings'])


def test_summary_mismatch_warns():
    data = parse(HEADER + ROW + 'SEM :\nI\nSummary\n49\n35\n14\n71.43', 'attendance')
    assert any('totals do not match' in w for w in data['warnings'])


def test_reversed_headers_not_assumed():
    assert parse(HEADER.replace('T\nP\nA', 'P\nT\nA') + ROW, 'attendance')['rows'] == []


def test_review_retry_and_metadata_confirmation(academic):
    from app.worker import process_one
    from .test_api import upload_csv
    c, semester, _ = academic
    d = upload_csv(c, semester, 'attendance', 'code,name,kind,instructor,attended,conducted,through_date\nP101,Physics lab,practical,Example Faculty,13,19,2020-01-31\n')
    response = c.post(f"/api/documents/{d['id']}/retry", json={})
    assert response.status_code == 200
    assert response.json()['preview'] == {}
    assert process_one()
    d = c.get(f"/api/documents/{d['id']}").json()
    response = c.post(f"/api/documents/{d['id']}/confirm", json={'rows': d['preview']['rows']})
    assert response.status_code == 200, response.text
    subject = next(s for s in c.get('/api/subjects', params={'semester_id': semester['id']}).json() if s['code']=='P101')
    assert subject['kind'] == 'practical'
    assert subject['instructor'] == 'Example Faculty'
    assert c.post(f"/api/documents/{d['id']}/retry", json={}).status_code == 409
