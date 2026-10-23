import os
import sys
import json
import pytest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app as flask_app, _create_storno
from models import db, Contact, Document, NumberSequence

NEW_YEAR = '2027-01-01'


@pytest.fixture
def app():
    flask_app.config['TESTING'] = True
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def contact_id(app):
    with app.app_context():
        c = Contact(organisation='Jahreswechsel Test GmbH', vorname='Max', nachname='Muster')
        db.session.add(c)
        db.session.commit()
        return c.id


def _create_doc(client, contact_id, doc_type, doc_date):
    payload = {
        'doc_type': doc_type,
        'contact_id': contact_id,
        'subject': f'Jahreswechsel-Test {doc_type}',
        'date': doc_date,
        'conditions_text': '',
        'groups': [{
            'title': 'Gruppe',
            'description': '',
            'items': [{
                'title': 'Position',
                'description': '',
                'quantity': 1,
                'unit': 'Einmalig',
                'unit_price': 100,
                'vat_rate': 20,
                'billing_type': 'onetime',
            }],
        }],
    }
    r = client.post('/documents/new', data=json.dumps(payload), content_type='application/json')
    return r.get_json()


def test_number_format_has_no_year_component(app):
    with app.app_context():
        seq = NumberSequence(prefix='ZZ', next_number=1, padding=5)
        db.session.add(seq)
        db.session.commit()

        number = seq.generate()
        db.session.commit()

        assert number == 'ZZ-00001'
        assert '2026' not in number
        assert '2027' not in number


def test_quote_number_continues_across_year_boundary(app, client, contact_id):
    with app.app_context():
        seq = NumberSequence.query.filter_by(prefix='A').first()
        seq.next_number = 99998
        db.session.commit()

    result = _create_doc(client, contact_id, 'quote', NEW_YEAR)

    assert result['success'] is True
    assert result['number'] == 'A-99998'
    with app.app_context():
        assert NumberSequence.query.filter_by(prefix='A').first().next_number == 99999


def test_invoice_number_continues_across_year_boundary(app, client, contact_id):
    with app.app_context():
        seq = NumberSequence.query.filter_by(prefix='R').first()
        seq.next_number = 55000
        db.session.commit()

    result = _create_doc(client, contact_id, 'invoice', NEW_YEAR)

    assert result['success'] is True
    assert result['number'] == 'R-55000'
    with app.app_context():
        assert NumberSequence.query.filter_by(prefix='R').first().next_number == 55001


def test_honorarnote_number_continues_across_year_boundary(app):
    with app.app_context():
        seq = NumberSequence.query.filter_by(prefix='H').first()
        assert seq is not None, 'H-Sequenz fehlt -- Migration unvollstaendig?'
        seq.next_number = 7
        db.session.commit()

        number = seq.generate()
        db.session.commit()

        assert number == 'H-00007'
        assert NumberSequence.query.filter_by(prefix='H').first().next_number == 8


def test_storno_number_continues_across_year_boundary(app, client, contact_id):
    created = _create_doc(client, contact_id, 'invoice', NEW_YEAR)
    assert created['success'] is True

    with app.app_context():
        seq = NumberSequence.query.filter_by(prefix='R').first()
        seq.next_number = 20000
        db.session.commit()

        original = Document.query.get(created['id'])
        original.status = 'sent'
        db.session.commit()

        storno_id = _create_storno(original)
        db.session.commit()

        storno = Document.query.get(storno_id)
        assert storno.number == 'R-20000'
        assert storno.doc_type == 'invoice'
        assert NumberSequence.query.filter_by(prefix='R').first().next_number == 20001


def test_storno_inherits_service_period(app, client, contact_id):
    created = _create_doc(client, contact_id, 'invoice', '2026-05-01')
    with app.app_context():
        original = Document.query.get(created['id'])
        original.status = 'sent'
        original.service_period = '01.04.2026 – 30.04.2026'
        db.session.commit()

        storno = Document.query.get(_create_storno(original))
        db.session.commit()
        assert storno.service_period == '01.04.2026 – 30.04.2026'


def test_storno_keeps_own_issue_date_not_the_originals(app, client, contact_id):
    created = _create_doc(client, contact_id, 'invoice', '2026-05-01')
    with app.app_context():
        original = Document.query.get(created['id'])
        original.status = 'sent'
        db.session.commit()
        original_datum = original.date

        storno = Document.query.get(_create_storno(original))
        db.session.commit()
        assert storno.date == date.today()
        assert storno.date != original_datum
        assert storno.source_document_id == original.id
        assert original.number in storno.conditions_text


def test_storno_without_service_period_stays_empty(app, client, contact_id):
    created = _create_doc(client, contact_id, 'invoice', '2026-05-01')
    with app.app_context():
        original = Document.query.get(created['id'])
        original.status = 'sent'
        original.service_period = None
        db.session.commit()

        storno = Document.query.get(_create_storno(original))
        db.session.commit()
        assert storno.service_period is None


def test_duplicate_does_not_inherit_service_period(app, client, contact_id):
    created = _create_doc(client, contact_id, 'invoice', '2026-05-01')
    with app.app_context():
        original = Document.query.get(created['id'])
        original.service_period = '01.05.2026 – 31.05.2026'
        db.session.commit()
        original_id = original.id

    res = client.post(f'/documents/{original_id}/duplicate', follow_redirects=True)
    assert res.status_code == 200
    with app.app_context():
        dup = (Document.query.filter(Document.contact_id == contact_id,
                                     Document.id != original_id)
               .order_by(Document.id.desc()).first())
        assert dup is not None
        assert dup.service_period is None
