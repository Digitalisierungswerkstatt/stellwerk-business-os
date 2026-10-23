import os
import sys
import pytest
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app as flask_app
from models import db, Contact, ContentCalendarEntry, CONTENT_CALENDAR_STAGES, CONTENT_PLATFORMS


@pytest.fixture
def app():
    flask_app.config['TESTING'] = True
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()



def test_invalid_status_raises_value_error(app):
    with app.app_context():
        with pytest.raises(ValueError):
            ContentCalendarEntry(platform='instagram', title='x', status='quatsch')


def test_invalid_platform_raises_value_error(app):
    with app.app_context():
        with pytest.raises(ValueError):
            ContentCalendarEntry(platform='quatsch', title='x', status='idee')


def test_valid_status_and_platform_ok(app):
    with app.app_context():
        entry = ContentCalendarEntry(platform='instagram', title='x', status='rohentwurf')
        assert entry.status == 'rohentwurf'
        assert entry.platform == 'instagram'



def test_table_exists_with_fk_on_contacts(app):
    with app.app_context():
        result = db.session.execute(db.text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='content_calendar'"
        )).fetchone()
        assert result is not None

        fk_rows = db.session.execute(db.text(
            "PRAGMA foreign_key_list('content_calendar')"
        )).fetchall()
        assert any(row[2] == 'contacts' for row in fk_rows), \
            f"Erwarte FK auf contacts, gefunden: {fk_rows}"



def test_calendar_view_empty_month_200(client):
    resp = client.get('/content-calendar')
    assert resp.status_code == 200


def test_board_view_200(client):
    resp = client.get('/content-calendar?view=board')
    assert resp.status_code == 200


def test_new_entry_appears_on_correct_day(app, client):
    resp = client.post('/content-calendar/new', data={
        'platform': 'instagram',
        'status': 'rohentwurf',
        'title': 'TEST_CC Neue Landtechnik-Serie',
        'scheduled_for': '2026-07-15T09:00',
    }, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        entry = ContentCalendarEntry.query.filter_by(title='TEST_CC Neue Landtechnik-Serie').first()
        assert entry is not None
        assert entry.scheduled_for == datetime(2026, 7, 15, 9, 0)
        entry_id = entry.id

    resp = client.get('/content-calendar?year=2026&month=7')
    assert resp.status_code == 200
    assert b'TEST_CC Neue Landtechnik-Serie' in resp.data

    with app.app_context():
        ContentCalendarEntry.query.filter_by(id=entry_id).delete()
        db.session.commit()


def test_move_to_posted_sets_posted_at(app, client):
    with app.app_context():
        entry = ContentCalendarEntry(platform='instagram', title='TEST_CC Move', status='scheduled')
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    resp = client.post(f'/content-calendar/{entry_id}/move',
                       json={'status': 'posted'})
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True

    with app.app_context():
        entry = ContentCalendarEntry.query.get(entry_id)
        assert entry.status == 'posted'
        assert entry.posted_at is not None

    resp = client.post(f'/content-calendar/{entry_id}/move',
                       json={'status': 'rohentwurf'})
    assert resp.status_code == 200

    with app.app_context():
        entry = ContentCalendarEntry.query.get(entry_id)
        assert entry.status == 'rohentwurf'
        assert entry.posted_at is None
        db.session.delete(entry)
        db.session.commit()


def test_move_rejects_invalid_status(app, client):
    with app.app_context():
        entry = ContentCalendarEntry(platform='instagram', title='TEST_CC Invalid', status='rohentwurf')
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    resp = client.post(f'/content-calendar/{entry_id}/move', json={'status': 'quatsch'})
    assert resp.status_code == 400

    with app.app_context():
        ContentCalendarEntry.query.filter_by(id=entry_id).delete()
        db.session.commit()



@pytest.fixture
def kunde(app):
    with app.app_context():
        contact = Contact(organisation='TEST_CC Landtechnik GmbH', contact_type='customer',
                          has_social_mandate=True)
        db.session.add(contact)
        db.session.commit()
        entry = ContentCalendarEntry(platform='instagram', title='TEST_CC Zuordnung',
                                     status='rohentwurf', contact_id=contact.id)
        db.session.add(entry)
        db.session.commit()
        ids = (contact.id, entry.id)

    yield ids

    with app.app_context():
        ContentCalendarEntry.query.filter_by(id=ids[1]).delete()
        Contact.query.filter_by(id=ids[0]).delete()
        db.session.commit()


def test_edit_ohne_contact_id_feld_behaelt_zuordnung(app, client, kunde):
    contact_id, entry_id = kunde

    resp = client.post(f'/content-calendar/{entry_id}', data={
        'platform': 'instagram',
        'status': 'rohentwurf',
        'title': 'TEST_CC Zuordnung',
        'scheduled_for': '2026-08-12T10:15',
    }, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        entry = ContentCalendarEntry.query.get(entry_id)
        assert entry.scheduled_for == datetime(2026, 8, 12, 10, 15), 'Umterminierung nicht angekommen'
        assert entry.contact_id == contact_id, \
            'contact_id wurde genullt, obwohl das Formular das Feld nie gesendet hat'


def test_edit_mit_leerem_contact_id_loescht_bewusst(app, client, kunde):
    _contact_id, entry_id = kunde

    resp = client.post(f'/content-calendar/{entry_id}', data={
        'contact_id': '',
        'platform': 'instagram',
        'status': 'rohentwurf',
        'title': 'TEST_CC Zuordnung',
    }, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        assert ContentCalendarEntry.query.get(entry_id).contact_id is None


def test_formular_traegt_contact_id_auch_ohne_alpine(client, kunde):
    contact_id, entry_id = kunde

    resp = client.get(f'/content-calendar/{entry_id}')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    marker = html[html.index('name="contact_id"'):]
    marker = marker[:marker.index('>')]
    assert f'value="{contact_id}"' in marker, \
        f'hidden contact_id ohne statischen Ist-Wert, ohne Alpine geht die Zuordnung verloren: {marker}'



@pytest.fixture
def li_post(app, tmp_path):
    from PIL import Image
    bild = tmp_path / 'li-test.png'
    Image.new('RGB', (40, 50), 'white').save(bild)
    with app.app_context():
        neu_315 = db.session.get(Contact, 315) is None
        if neu_315:
            db.session.add(Contact(id=315, organisation='TEST_CC DW', contact_type='customer'))
            db.session.commit()
        entry = ContentCalendarEntry(
            platform='linkedin', title='TEST_CC Vorschau', status='visual_fertig', contact_id=315,
            content_text='Kurzer Text. ' * 30 + 'Link im ersten Kommentar.',
            asset_link=str(bild), notes='Vorlauf\nErster Kommentar: https://x.at/blog')
        db.session.add(entry)
        db.session.commit()
        eid = entry.id
    yield eid, bild
    with app.app_context():
        ContentCalendarEntry.query.filter_by(id=eid).delete()
        if neu_315:
            Contact.query.filter_by(id=315).delete()
        db.session.commit()


def test_board_freigabe_springt_in_die_vorschau(app, client, li_post):
    eid, _ = li_post
    resp = client.post(f'/content-calendar/{eid}/move', json={'status': 'scheduled'})
    assert resp.status_code == 409
    assert resp.get_json()['href'].endswith(f'/content-calendar/{eid}')
    with app.app_context():
        assert ContentCalendarEntry.query.get(eid).status == 'visual_fertig'


def test_vorschau_zeigt_bild_text_und_kommentar(client, li_post):
    eid, _ = li_post
    html = client.get(f'/content-calendar/{eid}').get_data(as_text=True)
    assert 'Feed-Vorschau' in html
    assert f'/content-calendar/{eid}/asset/0' in html
    assert '· erster Kommentar</div><div class="text-gray-800 break-all">https://x.at/blog</div>' in html
    assert '>mehr</button>' in html


def test_vorschau_zeigt_publisher_sperre(app, client, li_post):
    eid, _ = li_post
    with app.app_context():
        e = ContentCalendarEntry.query.get(eid)
        e.notes = 'kein Kommentar'
        db.session.commit()
    html = client.get(f'/content-calendar/{eid}').get_data(as_text=True)
    assert 'Der Publisher würde diesen Post sperren' in html


def test_asset_route_liefert_nur_dateien_des_eintrags(client, li_post):
    eid, bild = li_post
    resp = client.get(f'/content-calendar/{eid}/asset/0')
    assert resp.status_code == 200 and resp.mimetype == 'image/png'
    assert resp.data == bild.read_bytes()
    assert client.get(f'/content-calendar/{eid}/asset/1').status_code in (302, 404)


def test_vorschau_gbp_mit_bild_url_ohne_fehlalarme(app, client):
    url = 'https://beispielverein.example/images/test%20bild.jpg'
    with app.app_context():
        entry = ContentCalendarEntry(platform='google_business', title='TEST_CC GBP',
                                     status='visual_fertig', content_text='Text', asset_link=url)
        db.session.add(entry)
        db.session.commit()
        eid = entry.id
    try:
        html = client.get(f'/content-calendar/{eid}').get_data(as_text=True)
        assert f'<img src="{url}"' in html
        assert 'Datei fehlt' not in html
        assert 'Wisch-Hinweis' not in html
        assert 'Kein erster Kommentar' not in html
    finally:
        with app.app_context():
            ContentCalendarEntry.query.filter_by(id=eid).delete()
            db.session.commit()
