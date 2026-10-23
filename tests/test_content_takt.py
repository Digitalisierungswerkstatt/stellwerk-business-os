import os
import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import content_takt
from app import app as flask_app
from models import db, Contact, ContentCalendarEntry, ContentTakt

HEUTE = date(2026, 10, 21)


def takt(**kw):
    t = dict(id=1, contact_id=7, kunde='K', platform='instagram', anzahl=1, intervall=1,
             einheit='woche', gueltig_ab=None, gueltig_bis=None, notiz=None)
    t.update(kw)
    return t


def eintrag(tag, platform='instagram', contact_id=7, status='rohentwurf'):
    return dict(id=0, contact_id=contact_id, platform=platform, termin=tag, status=status, title='x')



def test_woche_beginnt_am_montag_und_reicht_bis_zum_horizont():
    p = content_takt.perioden(takt(), HEUTE, 4)
    assert p[0] == (date(2026, 10, 19), date(2026, 10, 26))
    assert len(p) == 5


def test_zwei_wochen_takt_haengt_am_anker_nicht_an_heute():
    a = content_takt.perioden(takt(intervall=2), HEUTE, 4)
    b = content_takt.perioden(takt(intervall=2), date(2026, 10, 28), 4)
    assert a[0][0] == b[0][0]


def test_luecke_nur_wo_weniger_als_soll():
    eintr = [eintrag(date(2026, 10, 20)), eintrag(date(2026, 11, 3))]
    ab = content_takt.abdeckung([takt()], eintr, HEUTE, 2)
    assert [p['luecke'] for p in ab[0]['perioden']] == [False, True, False]


def test_posted_zaehlt_andere_plattform_und_anderer_kunde_nicht():
    eintr = [eintrag(date(2026, 10, 19), status='posted'),
             eintrag(date(2026, 10, 27), platform='instagram_story'),
             eintrag(date(2026, 10, 27), contact_id=8)]
    p = content_takt.abdeckung([takt()], eintr, HEUTE, 1)[0]['perioden']
    assert [x['ist'] for x in p] == [1, 0]


def test_monatstakt_zaehlt_kalendermonat():
    eintr = [eintrag(date(2026, 10, 2), platform='blog')]
    p = content_takt.abdeckung([takt(platform='blog', anzahl=2, einheit='monat')], eintr, HEUTE, 4)[0]['perioden']
    assert [(x['text'], x['ist'], x['luecke']) for x in p] == [('Okt 2026', 1, True), ('Nov 2026', 0, True)]


def test_gueltigkeit_trennt_taktwechsel():
    alt = takt(gueltig_bis=date(2026, 11, 1))
    neu = takt(id=2, intervall=2, gueltig_ab=date(2026, 11, 2))
    assert content_takt.perioden(alt, HEUTE, 4)[-1][0] == date(2026, 10, 26)
    assert content_takt.perioden(neu, HEUTE, 4)[0][0] == date(2026, 11, 2)
    assert content_takt.perioden(takt(gueltig_bis=date(2026, 10, 1)), HEUTE, 4) == []


def test_label_und_periodentext():
    assert content_takt.label(takt()) == '1 je Woche'
    assert content_takt.label(takt(intervall=2)) == '1 je 2 Wochen'
    assert content_takt.label(takt(anzahl=2, einheit='monat')) == '2 je Monat'
    assert content_takt.periode_text(date(2026, 10, 19), date(2026, 11, 2), 'woche') == 'KW 43–44'



@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    return flask_app.test_client()


@pytest.fixture
def kunde():
    with flask_app.app_context():
        c = Contact(organisation='Takt-Testkunde', contact_type='customer', has_social_mandate=True)
        db.session.add(c)
        db.session.commit()
        yield c.id
        ContentTakt.query.filter_by(contact_id=c.id).delete()
        ContentCalendarEntry.query.filter_by(contact_id=c.id).delete()
        db.session.delete(db.session.get(Contact, c.id))
        db.session.commit()


def test_validatoren():
    with flask_app.app_context():
        for kw in (dict(platform='quatsch'), dict(einheit='jahr'), dict(anzahl=0)):
            with pytest.raises(ValueError):
                ContentTakt(**{**dict(contact_id=1, platform='blog', einheit='woche', anzahl=1), **kw})


def test_mandat_ohne_takt_erscheint_und_verschwindet(client, kunde):
    assert 'Takt-Testkunde' in client.get('/content-calendar/takte').get_data(as_text=True)
    r = client.post('/content-calendar/takte', data=dict(
        contact_id=kunde, platform='instagram', anzahl=1, intervall=1, einheit='woche'))
    assert r.status_code == 302
    with flask_app.app_context():
        assert ContentTakt.query.filter_by(contact_id=kunde).count() == 1
        con = db.session.connection().connection
        _, _, ohne = content_takt.lade(con, date.today())
        assert kunde not in {k['contact_id'] for k in ohne}


def test_luecke_im_kalender_banner(client, kunde):
    client.post('/content-calendar/takte', data=dict(
        contact_id=kunde, platform='instagram', anzahl=1, intervall=1, einheit='woche'))
    html = client.get('/content-calendar').get_data(as_text=True)
    assert 'Takt-Lücke' in html


def test_ungueltige_eingabe_speichert_nichts(client, kunde):
    r = client.post('/content-calendar/takte', data=dict(
        contact_id=kunde, platform='instagram', anzahl=0, intervall=1, einheit='woche'))
    assert r.status_code == 302
    with flask_app.app_context():
        assert ContentTakt.query.filter_by(contact_id=kunde).count() == 0


def test_bearbeiten_und_loeschen(client, kunde):
    client.post('/content-calendar/takte', data=dict(
        contact_id=kunde, platform='blog', anzahl=1, intervall=1, einheit='woche'))
    with flask_app.app_context():
        tid = ContentTakt.query.filter_by(contact_id=kunde).one().id
    assert client.get(f'/content-calendar/takte?edit={tid}').status_code == 200
    client.post('/content-calendar/takte', data=dict(
        takt_id=tid, contact_id=kunde, platform='blog', anzahl=2, intervall=1, einheit='monat'))
    with flask_app.app_context():
        t = db.session.get(ContentTakt, tid)
        assert (t.anzahl, t.einheit) == (2, 'monat')
    client.post(f'/content-calendar/takte/{tid}/delete')
    with flask_app.app_context():
        assert db.session.get(ContentTakt, tid) is None
