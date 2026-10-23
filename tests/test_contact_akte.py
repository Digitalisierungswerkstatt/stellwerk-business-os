import os
import sys
import pytest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app as flask_app
from models import db, Contact, TimeEntry


@pytest.fixture
def app():
    flask_app.config['TESTING'] = True
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_contact_view_shows_billing_status(app, client):
    with app.app_context():
        c = Contact(organisation='AKTE_stundenbasis',
                    abrechnungsmodell='stundenbasis', hourly_rate=100)
        db.session.add(c)
        db.session.commit()
        cid = c.id
        db.session.add(TimeEntry(contact_id=cid, datum=date(2026, 7, 1),
                                 dauer_minuten=120, taetigkeit='beratung'))
        db.session.commit()
    resp = client.get(f'/contacts/{cid}')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Abrechnungs-Status' in body
    assert 'Unverrechnet' in body
    assert 'Offener Wert' in body
    assert '200' in body
    with app.app_context():
        TimeEntry.query.filter_by(contact_id=cid).delete()
        Contact.query.filter_by(id=cid).delete()
        db.session.commit()


def test_contact_view_intern_hides_billing(app, client):
    with app.app_context():
        c = Contact(organisation='AKTE_intern', abrechnungsmodell='intern')
        db.session.add(c)
        db.session.commit()
        cid = c.id
    resp = client.get(f'/contacts/{cid}')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Abrechnungs-Status' not in body
    with app.app_context():
        Contact.query.filter_by(id=cid).delete()
        db.session.commit()


def test_contact_view_no_time_still_renders(app, client):
    with app.app_context():
        c = Contact(organisation='AKTE_leer', abrechnungsmodell='stundenbasis')
        db.session.add(c)
        db.session.commit()
        cid = c.id
    resp = client.get(f'/contacts/{cid}')
    assert resp.status_code == 200
    with app.app_context():
        Contact.query.filter_by(id=cid).delete()
        db.session.commit()
