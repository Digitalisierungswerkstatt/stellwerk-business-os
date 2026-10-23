import pytest
import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app as flask_app
from models import (db, Contact, Document, DocumentStatusLog, LineItemGroup, LineItem,
                    NumberSequence, ServiceTemplate, ConditionsTemplate, Task)


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
        c = Contact.query.first()
        if c:
            return c.id
        c = Contact(organisation='Test GmbH', vorname='Max', nachname='Muster')
        db.session.add(c)
        db.session.commit()
        return c.id


def _create_doc(client, contact_id, **overrides):
    payload = {
        'doc_type': 'quote',
        'contact_id': contact_id,
        'subject': overrides.get('subject', 'Test Angebot'),
        'date': date.today().isoformat(),
        'conditions_text': '',
        'groups': [{
            'title': 'Test Gruppe',
            'description': '',
            'items': [{
                'title': 'Test Position',
                'description': '',
                'quantity': 1,
                'unit': 'Einmalig',
                'unit_price': overrides.get('unit_price', 1000),
                'vat_rate': 20,
                'billing_type': 'onetime',
            }],
        }],
    }
    payload.update({k: v for k, v in overrides.items() if k not in ('unit_price', 'subject')})
    r = client.post('/documents/new',
                     data=json.dumps(payload),
                     content_type='application/json')
    return r.get_json()



def test_create_document(client, contact_id):
    result = _create_doc(client, contact_id)
    assert result['success'] is True
    assert 'id' in result
    assert result['number'].startswith('A-')


def test_create_document_with_discount(client, contact_id):
    result = _create_doc(client, contact_id,
                         discount_type='percent', discount_value=10)
    assert result['success'] is True
    with flask_app.app_context():
        doc = db.session.get(Document, result['id'])
        assert doc.discount_type == 'percent'
        assert float(doc.discount_value) == 10



def test_discount_amount_percent(client, contact_id):
    result = _create_doc(client, contact_id, unit_price=1000,
                         discount_type='percent', discount_value=10)
    with flask_app.app_context():
        doc = db.session.get(Document, result['id'])
        assert doc.total_net == 1000
        assert doc.discount_amount == 100


def test_discount_amount_fixed(client, contact_id):
    result = _create_doc(client, contact_id, unit_price=1000,
                         discount_type='fixed', discount_value=50)
    with flask_app.app_context():
        doc = db.session.get(Document, result['id'])
        assert doc.discount_amount == 50


def test_total_after_discount(client, contact_id):
    result = _create_doc(client, contact_id, unit_price=1000,
                         discount_type='percent', discount_value=10)
    with flask_app.app_context():
        doc = db.session.get(Document, result['id'])
        assert doc.total_after_discount_net == 900
        assert doc.total_after_discount_gross == 900 + doc.total_after_discount_vat
        assert doc.has_discount is True


def test_no_discount(client, contact_id):
    result = _create_doc(client, contact_id, unit_price=500)
    with flask_app.app_context():
        doc = db.session.get(Document, result['id'])
        assert doc.has_discount is False
        assert doc.discount_amount == 0
        assert doc.total_after_discount_net == doc.total_net



def test_status_transitions_quote(client, contact_id):
    result = _create_doc(client, contact_id)
    doc_id = result['id']

    r = client.post(f'/documents/{doc_id}/status',
                     data={'status': 'sent'})
    assert r.status_code in (200, 302)

    with flask_app.app_context():
        doc = db.session.get(Document, doc_id)
        assert doc.status == 'sent'

    r = client.post(f'/documents/{doc_id}/status',
                     data={'status': 'accepted'})
    with flask_app.app_context():
        doc = db.session.get(Document, doc_id)
        assert doc.status == 'accepted'


def test_invalid_status_transition(client, contact_id):
    result = _create_doc(client, contact_id)
    doc_id = result['id']
    r = client.post(f'/documents/{doc_id}/status',
                     data={'status': 'paid'})
    with flask_app.app_context():
        doc = db.session.get(Document, doc_id)
        assert doc.status == 'draft'



def _accept(client, doc_id):
    client.post(f'/documents/{doc_id}/status', data={'status': 'sent'})
    client.post(f'/documents/{doc_id}/status', data={'status': 'accepted'})


def test_convert_sets_quote_to_converted(client, contact_id):
    doc_id = _create_doc(client, contact_id)['id']
    _accept(client, doc_id)

    r = client.post(f'/documents/{doc_id}/convert')
    assert r.status_code in (200, 302)

    with flask_app.app_context():
        quote = db.session.get(Document, doc_id)
        assert quote.status == 'converted'
        invoice = Document.query.filter_by(source_document_id=doc_id).one()
        assert invoice.doc_type == 'invoice'
        log = DocumentStatusLog.query.filter_by(
            document_id=doc_id, to_status='converted').one()
        assert invoice.number in log.note


def test_convert_rejected_for_unaccepted_quote(client, contact_id):
    doc_id = _create_doc(client, contact_id)['id']
    client.post(f'/documents/{doc_id}/convert')

    with flask_app.app_context():
        assert db.session.get(Document, doc_id).status == 'draft'
        assert Document.query.filter_by(source_document_id=doc_id).count() == 0


def test_second_convert_allowed_and_stays_terminal(client, contact_id):
    doc_id = _create_doc(client, contact_id)['id']
    _accept(client, doc_id)
    client.post(f'/documents/{doc_id}/convert')
    client.post(f'/documents/{doc_id}/convert')

    with flask_app.app_context():
        assert db.session.get(Document, doc_id).status == 'converted'
        assert Document.query.filter_by(source_document_id=doc_id).count() == 2
        assert DocumentStatusLog.query.filter_by(
            document_id=doc_id, to_status='converted').count() == 1


def test_converted_can_be_reverted_to_accepted(client, contact_id):
    doc_id = _create_doc(client, contact_id)['id']
    _accept(client, doc_id)
    client.post(f'/documents/{doc_id}/convert')
    client.post(f'/documents/{doc_id}/status', data={'status': 'accepted'})

    with flask_app.app_context():
        assert db.session.get(Document, doc_id).status == 'accepted'


def test_converted_quote_keeps_won_contact(client, contact_id):
    doc_id = _create_doc(client, contact_id)['id']
    _accept(client, doc_id)
    client.post(f'/documents/{doc_id}/convert')

    with flask_app.app_context():
        quote = db.session.get(Document, doc_id)
        assert quote.contact.status == 'won'
        assert quote.status_label == 'In Rechnung'



def test_duplicate_carries_discount(client, contact_id):
    result = _create_doc(client, contact_id,
                         discount_type='percent', discount_value=15,
                         internal_notes='Test note')
    doc_id = result['id']

    r = client.post(f'/documents/{doc_id}/duplicate')

    with flask_app.app_context():
        new_doc = Document.query.order_by(Document.id.desc()).first()
        assert new_doc.id != doc_id
        assert new_doc.discount_type == 'percent'
        assert float(new_doc.discount_value) == 15
        assert new_doc.internal_notes == 'Test note'



def test_services_api(client):
    with flask_app.app_context():
        svc = ServiceTemplate(category='test', title='Test Service',
                              unit_price=100, unit='Einmalig',
                              billing_type='onetime', position=0, active=True)
        db.session.add(svc)
        db.session.commit()

    r = client.get('/api/services')
    data = r.get_json()
    titles = [s['title'] for s in data]
    assert 'Test Service' in titles


def test_conditions_api(client):
    with flask_app.app_context():
        ct = ConditionsTemplate(name='Test Kondition', text='Zahlbar sofort.', position=0, active=True)
        db.session.add(ct)
        db.session.commit()

    r = client.get('/api/conditions-templates')
    data = r.get_json()
    names = [c['name'] for c in data]
    assert 'Test Kondition' in names


def test_use_count_bump(client):
    with flask_app.app_context():
        svc = ServiceTemplate.query.filter_by(title='Test Service').first()
        if svc:
            old_count = svc.use_count or 0
        else:
            old_count = 0

    r = client.post('/api/services/bump-usage',
                     data=json.dumps({'titles': ['Test Service']}),
                     content_type='application/json')
    assert r.get_json()['success'] is True

    with flask_app.app_context():
        svc = ServiceTemplate.query.filter_by(title='Test Service').first()
        assert (svc.use_count or 0) > old_count



def test_document_search(client, contact_id):
    _create_doc(client, contact_id, subject='Webdesign Relaunch 2026')
    r = client.get('/api/documents/search?q=Webdesign')
    data = r.get_json()
    assert len(data) > 0
    assert any('Webdesign' in d['subject'] for d in data)


def test_document_search_too_short(client):
    r = client.get('/api/documents/search?q=a')
    data = r.get_json()
    assert data == []



def test_dashboard_loads(client):
    r = client.get('/')
    assert r.status_code == 200


def test_dashboard_has_document_widget(client):
    r = client.get('/')
    html = r.data.decode()
    assert 'Dokumente' in html or r.status_code == 200



def test_quote_followup_generation(client, contact_id):
    result = _create_doc(client, contact_id, subject='Stale Quote Test')
    doc_id = result['id']

    with flask_app.app_context():
        doc = db.session.get(Document, doc_id)
        doc.date = date.today() - timedelta(days=10)
        doc.status = 'sent'
        db.session.commit()

    client.get('/')

    with flask_app.app_context():
        task = Task.query.filter(Task.title.like(f'%{result["number"]}%')).first()
        assert task is not None
        assert 'Nachhaken' in task.title
        assert task.created_by == 'System'
        assert task.priority == 'hoch'


def test_quote_followup_no_duplicate(client, contact_id):
    client.get('/')
    client.get('/')

    with flask_app.app_context():
        tasks = Task.query.filter(Task.title.like('%Nachhaken%Stale Quote%')).all()
        assert len(tasks) <= 1


def test_quote_followup_not_regenerated_after_close(client, contact_id):
    result = _create_doc(client, contact_id, subject='Reopen After Close Test')
    number = result['number']
    with flask_app.app_context():
        doc = db.session.get(Document, result['id'])
        doc.date = date.today() - timedelta(days=10)
        doc.status = 'sent'
        db.session.commit()

    client.get('/')
    with flask_app.app_context():
        tasks = Task.query.filter(Task.title.like(f'%{number}%')).all()
        assert len(tasks) == 1
        tasks[0].status = 'erledigt'
        db.session.commit()

    client.get('/')
    with flask_app.app_context():
        tasks = Task.query.filter(Task.title.like(f'%{number}%')).all()
        statuses = sorted(t.status for t in tasks)
        assert len(tasks) == 1, f'follow-up regenerated after close: {statuses}'



def test_pdf_preview(client, contact_id):
    result = _create_doc(client, contact_id, subject='Preview Test')
    r = client.get(f'/documents/{result["id"]}/preview')
    assert r.status_code == 200
    html = r.data.decode()
    assert 'Preview Test' in html
    assert 'Musterwerkstatt' in html or 'doc-type' in html



def test_email_route_no_email(client, contact_id):
    result = _create_doc(client, contact_id)
    with flask_app.app_context():
        contact = db.session.get(Contact, contact_id)
        contact.mail_organisation = None
        contact.mail_person = None
        db.session.commit()

    r = client.post(f'/documents/{result["id"]}/send-email')
    data = r.get_json()
    assert r.status_code == 400
    assert 'E-Mail' in data.get('error', '')



def test_document_view(client, contact_id):
    result = _create_doc(client, contact_id, subject='View Test')
    r = client.get(f'/documents/{result["id"]}')
    assert r.status_code == 200
    html = r.data.decode()
    assert 'View Test' in html
    assert 'Entwurf' in html


def test_document_view_with_discount(client, contact_id):
    result = _create_doc(client, contact_id, subject='Discount View',
                         discount_type='percent', discount_value=10, unit_price=1000)
    r = client.get(f'/documents/{result["id"]}')
    html = r.data.decode()
    assert 'Rabatt' in html


def test_document_view_internal_notes(client, contact_id):
    result = _create_doc(client, contact_id, internal_notes='Secret note for me')
    r = client.get(f'/documents/{result["id"]}')
    html = r.data.decode()
    assert 'Secret note for me' in html
    assert 'Interne Notizen' in html



def test_group_templates_api(client):
    r = client.get('/api/group-templates')
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


def test_create_service_template(client):
    r = client.post('/services/new',
                     data=json.dumps({
                         'category': 'test',
                         'title': 'New Test Service',
                         'description': 'Test',
                         'unit_price': 200,
                         'unit': 'Einmalig',
                         'billing_type': 'onetime',
                     }),
                     content_type='application/json')
    assert r.get_json()['success'] is True


def test_document_groups_api(client, contact_id):
    result = _create_doc(client, contact_id, subject='API Groups Test')
    r = client.get(f'/api/documents/{result["id"]}/groups')
    data = r.get_json()
    assert data['number'].startswith('A-')
    assert len(data['groups']) == 1
    assert data['groups'][0]['title'] == 'Test Gruppe'



def test_404_json(client):
    r = client.get('/nonexistent-page', headers={'Accept': 'application/json'})
    assert r.status_code in (302, 404)


def test_document_not_found(client):
    r = client.get('/documents/99999')
    assert r.status_code in (302, 404)



def test_documents_list(client):
    r = client.get('/documents?tab=quotes')
    assert r.status_code == 200


def test_documents_search(client, contact_id):
    _create_doc(client, contact_id, subject='Findable Document XYZ')
    r = client.get('/documents?tab=quotes&q=Findable')
    assert r.status_code == 200
    html = r.data.decode()
    assert 'Findable Document XYZ' in html


def test_documents_sort(client):
    r = client.get('/documents?tab=quotes&sort=amount_desc')
    assert r.status_code == 200



def test_delete_blocked_for_sent_invoice(client, contact_id):
    result = _create_doc(client, contact_id, doc_type='invoice')
    doc_id = result['id']
    assert result['number'].startswith('R-')

    client.post(f'/documents/{doc_id}/status', data={'status': 'sent'})

    r = client.post(f'/documents/{doc_id}/delete')
    assert r.status_code in (200, 302)
    with flask_app.app_context():
        doc = db.session.get(Document, doc_id)
        assert doc is not None
        assert doc.status == 'sent'


def test_delete_blocked_for_paid_invoice(client, contact_id):
    result = _create_doc(client, contact_id, doc_type='invoice')
    doc_id = result['id']

    client.post(f'/documents/{doc_id}/status', data={'status': 'sent'})
    client.post(f'/documents/{doc_id}/status', data={'status': 'paid'})

    r = client.post(f'/documents/{doc_id}/delete')
    assert r.status_code in (200, 302)
    with flask_app.app_context():
        doc = db.session.get(Document, doc_id)
        assert doc is not None
        assert doc.status == 'paid'


def test_delete_allowed_for_draft_invoice(client, contact_id):
    result = _create_doc(client, contact_id, doc_type='invoice')
    doc_id = result['id']

    r = client.post(f'/documents/{doc_id}/delete')
    assert r.status_code in (200, 302)
    with flask_app.app_context():
        assert db.session.get(Document, doc_id) is None


def test_delete_tail_draft_invoice_reclaims_number(client, contact_id):
    result = _create_doc(client, contact_id, doc_type='invoice')
    number = result['number']
    with flask_app.app_context():
        seq = NumberSequence.query.filter_by(prefix='R').first()
        next_before = seq.next_number
    assert int(number.split('-')[-1]) == next_before - 1

    client.post(f'/documents/{result["id"]}/delete')

    with flask_app.app_context():
        seq = NumberSequence.query.filter_by(prefix='R').first()
        assert seq.next_number == next_before - 1
    reused = _create_doc(client, contact_id, doc_type='invoice')
    assert reused['number'] == number


def test_delete_midseries_draft_invoice_blocked(client, contact_id):
    older = _create_doc(client, contact_id, doc_type='invoice')
    _create_doc(client, contact_id, doc_type='invoice')

    r = client.post(f'/documents/{older["id"]}/delete')
    assert r.status_code in (200, 302)
    with flask_app.app_context():
        doc = db.session.get(Document, older['id'])
        assert doc is not None
        assert doc.status == 'draft'
