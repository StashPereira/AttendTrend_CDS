from datetime import datetime
from app.services.documents import parse
from app.services.attendance import subject_stats
from app.models import Subject, Profile
from app.db import SessionLocal
from app.services.timetable_reports import parse_cell


def test_calendar_wrapped_ranges_and_continue_lectures():
    result = parse('''DATE DAY NATURE OF ACTIVITIES
14/9/2026 Monday 14/09/2026 to 19/09/2026)
Mid Term Break (Ganpati Vacation)
31/8/2026 Monday CIA-II (Lectures Continue)
(31/8/2026 to 07/09/2026)
24/12/2026 Thursday Winter Break (Christmas Vacation)
(24/12/2026 to
01/1/2027)
''', 'calendar')
    assert len(result['rows']) == 3
    assert result['rows'][0]['kind'] == 'holiday'
    assert result['rows'][0]['end_date'] == '2026-09-19'
    assert result['rows'][1]['kind'] == 'exam'
    assert result['rows'][1]['end_date'] == '2026-09-07'
    assert result['rows'][2]['end_date'] == '2027-01-01'


def test_calendar_source_date_typo_warned_not_changed():
    result = parse('01-05-2026 Saturday Maharashtra Day celebration', 'calendar')
    assert result['rows'][0]['start_date'] == '2026-05-01'
    assert any('weekday' in w for w in result['warnings'])


def test_missing_ocr_shows_actionable_review_warning():
    result = parse('IMPORT_WARNING: OCR_UNAVAILABLE: Install Tesseract or upload CSV.', 'timetable')
    assert not result['rows']
    assert any('Install Tesseract' in w for w in result['warnings'])


def test_timetable_time_and_practical_cell():
    row = parse_cell('DBMS PRACTICAL RT (12:30-2:30) BDA Lab', 1)
    assert row['weekday'] == 1
    assert row['start_time'] == '12:30' and row['end_time'] == '14:30'
    assert row['name'].endswith('PRACTICAL')
    assert parse_cell('Linear Algebra (2:30-1:30)', 2) is None


def test_lecture_totals_persist_and_validate(academic):
    c, semester, subject = academic
    payload = {'semester_id':semester['id'], 'code':subject['code'], 'name':subject['name'], 'planned_lectures':40}
    assert c.put('/api/subjects/'+str(subject['id']), json=payload).status_code == 200
    assert c.get('/api/subjects',params={'semester_id':semester['id']}).json()[0]['planned_lectures']==40
    payload['planned_lectures']=-1
    assert c.put('/api/subjects/'+str(subject['id']), json=payload).status_code==422


def test_totals_cap_remaining_and_pending_blocks_calendar(academic):
    from app.models import Occurrence, Attendance, Baseline
    from datetime import date
    c, semester, subject = academic
    with SessionLocal() as db:
        s=db.get(Subject,subject['id']);s.planned_lectures=11
        db.add(Baseline(user_id=s.user_id,subject_id=s.id,through_date=date(2020,1,31),attended=10,conducted=10))
        for day in [2,3,4]:
            db.add(Occurrence(user_id=s.user_id,subject_id=s.id,starts_at=datetime(2020,2,day,9),ends_at=datetime(2020,2,day,10)))
        db.flush()
        stat=subject_stats(db,s,db.get(Profile,s.user_id),datetime(2020,2,1))
        assert stat['scheduled_remaining']==3
        assert stat['recovery']['remaining']==1
        assert stat['calendar_skip_allowance']==1
        assert stat['planning_warnings']
        # One unmarked elapsed occurrence is pending and consumes the available total.
        stat=subject_stats(db,s,db.get(Profile,s.user_id),datetime(2020,2,2,11))
        assert stat['pending']==1
        assert stat['calendar_skip_allowance']==0


def test_calendar_requires_totals_and_respects_safety_buffer(academic):
    from app.models import Occurrence, Baseline
    from datetime import date
    _, _, subject = academic
    with SessionLocal() as db:
        s=db.get(Subject,subject['id'])
        profile=db.get(Profile,s.user_id)
        profile.target=75;profile.safety_buffer=5
        db.add(Baseline(user_id=s.user_id,subject_id=s.id,through_date=date(2020,1,31),attended=9,conducted=10))
        for day in [2,3,4]:
            db.add(Occurrence(user_id=s.user_id,subject_id=s.id,starts_at=datetime(2020,2,day,9),ends_at=datetime(2020,2,day,10)))
        db.flush()
        unknown=subject_stats(db,s,profile,datetime(2020,2,1))
        assert unknown['calendar_skip_allowance']==0
        s.planned_lectures=13
        result=subject_stats(db,s,profile,datetime(2020,2,1))
        assert result['recovery']['safe_to_skip']==2
        assert result['calendar_skip_allowance']==1
        assert result['calendar_target']==80
        s.planned_lectures=9
        invalid=subject_stats(db,s,profile,datetime(2020,2,1))
        assert invalid['calendar_skip_allowance']==0
        assert any('below conducted' in w for w in invalid['planning_warnings'])
