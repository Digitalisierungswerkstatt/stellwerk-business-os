import io
import os
import sys
import pytest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as app_module
from app import app as flask_app
from models import (db, Contact, NumberSequence,
                    IncomingInvoice, IncomingLineItem, ExpenseCategory)


TEST_PREFIX = 'TEST_IIV_'
REAL_PDF_DIR = os.path.normcase(os.path.abspath(os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'uploads', 'incoming_invoices')))


@pytest.fixture
def app():
    flask_app.config['TESTING'] = True
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def supplier_id(app):
    with app.app_context():
        s = Contact.query.filter_by(organisation=f'{TEST_PREFIX}Anthropic GmbH').first()
        if not s:
            s = Contact(organisation=f'{TEST_PREFIX}Anthropic GmbH',
                        contact_type='supplier',
                        uid='ATU99999999',
                        land='AT')
            db.session.add(s)
            db.session.commit()
        return s.id


@pytest.fixture
def category_id(app):
    with app.app_context():
        c = ExpenseCategory.query.filter_by(code='software').first()
        return c.id if c else None


def _purge_test_data(app):
    with app.app_context():
        ids = [s.id for s in
               Contact.query.filter(Contact.organisation.like(f'{TEST_PREFIX}%')).all()]
        if ids:
            IncomingInvoice.query.filter(
                IncomingInvoice.supplier_id.in_(ids)).delete(synchronize_session=False)
            Contact.query.filter(
                Contact.id.in_(ids)).delete(synchronize_session=False)
            db.session.commit()


@pytest.fixture(autouse=True)
def cleanup_test_data(app):
    _purge_test_data(app)
    yield
    _purge_test_data(app)
    pdf_dir = app_module.INCOMING_PDF_DIR
    if os.path.normcase(os.path.abspath(pdf_dir)) == REAL_PDF_DIR:
        raise RuntimeError(f'Test-Cleanup zeigt auf den echten Belegordner {pdf_dir}, '
                           'STELLWERK_INCOMING_PDF_DIR ist nicht gesetzt (conftest.py)')
    if os.path.isdir(pdf_dir):
        with app.app_context():
            for f in os.listdir(pdf_dir):
                if f.startswith('E-') and f.endswith('.pdf'):
                    inv = IncomingInvoice.query.filter_by(number=f[:-4]).first()
                    if not inv:
                        try:
                            os.remove(os.path.join(pdf_dir, f))
                        except OSError:
                            pass



def test_smoke_expense_categories_seeded(app):
    with app.app_context():
        assert ExpenseCategory.query.count() >= 11
        software = ExpenseCategory.query.filter_by(code='software').first()
        assert software is not None
        assert software.gmbh_account_code == '7320'



def test_contact_type_default_customer(app):
    with app.app_context():
        null_count = Contact.query.filter(Contact.contact_type.is_(None)).count()
        assert null_count == 0, 'Es gibt Kontakte ohne contact_type'


def test_supplier_filter_only_supplier_and_both(app, client, supplier_id):
    with app.app_context():
        assert Contact.query.filter(Contact.contact_type.in_(['supplier', 'both'])).count() >= 1
    r = client.get('/incoming-invoices/new')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert f'{TEST_PREFIX}Anthropic GmbH' in body



def test_number_sequence_E_increments(app, supplier_id, category_id):
    with app.app_context():
        seq_before = NumberSequence.query.filter_by(prefix='E').first().next_number

        seq = NumberSequence.query.filter_by(prefix='E').first()
        n1 = seq.generate()
        db.session.commit()
        n2 = seq.generate()
        db.session.commit()

        assert n1 == f'E-{str(seq_before).zfill(5)}'
        assert n2 == f'E-{str(seq_before + 1).zfill(5)}'



def test_create_incoming_invoice_minimal(app, client, supplier_id, category_id):
    r = client.post('/incoming-invoices/new', data={
        'supplier_id': supplier_id,
        'expense_category_id': category_id,
        'external_invoice_number': 'INV-2026-TEST-001',
        'subject': 'Software-Abo Test',
        'invoice_date': '2026-05-15',
        'posting_date': '2026-05-15',
        'net_amount': '100.00',
        'vat_rate': '20',
        'is_vat_deductible': 'on',
    }, follow_redirects=False)
    assert r.status_code in (302, 200), f'Got {r.status_code}: {r.get_data(as_text=True)[:200]}'
    with app.app_context():
        inv = IncomingInvoice.query.filter_by(external_invoice_number='INV-2026-TEST-001').first()
        assert inv is not None
        assert float(inv.net_amount) == 100.0
        assert float(inv.vat_amount) == 20.0
        assert float(inv.gross_amount) == 120.0
        assert inv.status == 'open'


def test_create_reverse_charge_requires_exemption_reason(app, client, supplier_id):
    r = client.post('/incoming-invoices/new', data={
        'supplier_id': supplier_id,
        'external_invoice_number': 'INV-RC-NO-REASON',
        'subject': 'Anthropic API',
        'invoice_date': '2026-05-15',
        'posting_date': '2026-05-15',
        'net_amount': '50.00',
        'vat_rate': '0',
    }, follow_redirects=False)
    with app.app_context():
        inv = IncomingInvoice.query.filter_by(external_invoice_number='INV-RC-NO-REASON').first()
        assert inv is None, 'Beleg ohne Befreiungsgrund wurde faelschlich gespeichert'


def test_create_reverse_charge_with_reason(app, client, supplier_id):
    r = client.post('/incoming-invoices/new', data={
        'supplier_id': supplier_id,
        'external_invoice_number': 'INV-RC-OK',
        'subject': 'Anthropic API',
        'invoice_date': '2026-05-15',
        'posting_date': '2026-05-15',
        'net_amount': '50.00',
        'vat_rate': '0',
        'vat_exemption_reason': 'Reverse Charge §19 UStG',
    }, follow_redirects=False)
    with app.app_context():
        inv = IncomingInvoice.query.filter_by(external_invoice_number='INV-RC-OK').first()
        assert inv is not None
        assert float(inv.vat_amount) == 0.0
        assert inv.vat_exemption_reason == 'Reverse Charge §19 UStG'


def test_gross_validation_rejects_mismatch(app, client, supplier_id):
    r = client.post('/incoming-invoices/new', data={
        'supplier_id': supplier_id,
        'external_invoice_number': 'INV-GROSS-MISMATCH',
        'subject': 'Bug-Beleg',
        'invoice_date': '2026-05-15',
        'posting_date': '2026-05-15',
        'net_amount': '100.00',
        'vat_rate': '20',
        'gross_amount': '999.00',
    }, follow_redirects=False)
    with app.app_context():
        inv = IncomingInvoice.query.filter_by(external_invoice_number='INV-GROSS-MISMATCH').first()
        assert inv is None


def test_duplicate_invoice_rejected(app, client, supplier_id):
    payload = {
        'supplier_id': supplier_id,
        'external_invoice_number': 'INV-DUPLICATE',
        'subject': 'Beleg 1',
        'invoice_date': '2026-05-15',
        'posting_date': '2026-05-15',
        'net_amount': '50.00',
        'vat_rate': '20',
    }
    r1 = client.post('/incoming-invoices/new', data=payload, follow_redirects=False)
    r2 = client.post('/incoming-invoices/new', data=payload, follow_redirects=False)
    with app.app_context():
        count = IncomingInvoice.query.filter_by(external_invoice_number='INV-DUPLICATE').count()
        assert count == 1, f'Dublette akzeptiert: {count} Belege'



def test_mark_paid_sets_status_and_date(app, client, supplier_id):
    client.post('/incoming-invoices/new', data={
        'supplier_id': supplier_id,
        'external_invoice_number': 'INV-MARK-PAID',
        'subject': 'Zu-bezahlen-Beleg',
        'invoice_date': '2026-05-01',
        'posting_date': '2026-05-01',
        'net_amount': '100.00',
        'vat_rate': '20',
    })
    with app.app_context():
        inv = IncomingInvoice.query.filter_by(external_invoice_number='INV-MARK-PAID').first()
        assert inv.status == 'open'
        inv_id = inv.id

    r = client.post(f'/incoming-invoices/{inv_id}/mark-paid', data={
        'payment_date': '2026-05-20',
        'payment_method': 'sepa',
    }, follow_redirects=False)

    with app.app_context():
        inv = IncomingInvoice.query.get(inv_id)
        assert inv.status == 'paid'
        assert inv.payment_date == date(2026, 5, 20)
        assert inv.payment_method == 'sepa'



def test_pdf_upload_rejects_non_pdf(app, client, supplier_id):
    client.post('/incoming-invoices/new', data={
        'supplier_id': supplier_id,
        'external_invoice_number': 'INV-PDF-VALIDATION',
        'subject': 'PDF-Test',
        'invoice_date': '2026-05-01',
        'posting_date': '2026-05-01',
        'net_amount': '50.00',
        'vat_rate': '20',
    })
    with app.app_context():
        inv = IncomingInvoice.query.filter_by(external_invoice_number='INV-PDF-VALIDATION').first()
        inv_id = inv.id

    txt_data = b'This is plain text, not a PDF'
    r = client.post(f'/incoming-invoices/{inv_id}/upload-pdf', data={
        'pdf_file': (io.BytesIO(txt_data), 'fake.txt'),
    }, content_type='multipart/form-data', follow_redirects=False)

    with app.app_context():
        inv = db.session.get(IncomingInvoice, inv_id)
        assert inv.document_file_path is None, \
            'Non-PDF wurde faelschlich akzeptiert'
        pdf_path = os.path.join(app_module.INCOMING_PDF_DIR, f'{inv.number}.pdf')
        assert not os.path.exists(pdf_path), 'PDF-Datei wurde angelegt obwohl Upload fehlschlagen sollte'
