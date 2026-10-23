import os
import sys
import pytest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app as flask_app
from models import db, Contact, IncomingInvoice


@pytest.fixture
def app():
    flask_app.config['TESTING'] = True
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_delete_plain_contact_succeeds(app, client):
    with app.app_context():
        c = Contact(organisation='DEL_plain_lead')
        db.session.add(c)
        db.session.commit()
        cid = c.id
    resp = client.post(f'/contacts/{cid}/delete', follow_redirects=False)
    assert resp.status_code in (302, 303)
    with app.app_context():
        assert Contact.query.get(cid) is None


def test_delete_contact_with_incoming_invoice_blocked(app, client):
    with app.app_context():
        c = Contact(organisation='DEL_supplier', contact_type='supplier')
        db.session.add(c)
        db.session.commit()
        cid = c.id
        inv = IncomingInvoice(
            number='TEST-DEL-1', supplier_id=cid,
            external_invoice_number='EXT-DEL-1', subject='Guard-Test',
            invoice_date=date(2026, 6, 1), posting_date=date(2026, 6, 1),
            net_amount=50, vat_rate=20, vat_amount=10, gross_amount=60)
        db.session.add(inv)
        db.session.commit()
    resp = client.post(f'/contacts/{cid}/delete', follow_redirects=False)
    assert resp.status_code in (302, 303)
    with app.app_context():
        assert Contact.query.get(cid) is not None, 'Kontakt wurde trotz Beleg gelöscht'
        IncomingInvoice.query.filter_by(supplier_id=cid).delete()
        Contact.query.filter_by(id=cid).delete()
        db.session.commit()
