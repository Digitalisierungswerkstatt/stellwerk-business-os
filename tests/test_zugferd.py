import io
import json
from datetime import date

import pytest
from pypdf import PdfReader, PdfWriter

from app import app as flask_app
from models import db, Contact, Document, LineItemGroup, LineItem, CompanySettings
from zugferd import build_zugferd_xml, embed_zugferd_xml, VAT_EXEMPTION_REASON, _ensure_pdfa3_base
from facturx import xml_check_xsd, xml_check_schematron


@pytest.fixture
def app():
    flask_app.config['TESTING'] = True
    yield flask_app


def _seed_company_uid():
    if CompanySettings.query.get('uid') is None:
        db.session.add(CompanySettings(key='uid', value='ATU00000000'))
        db.session.commit()


def _make_invoice(number, *, rate=20.0, with_address=True, due=True,
                  discount=0.0, second_rate=None, negate=False):
    _seed_company_uid()
    c = Contact(organisation='Muster GmbH', vorname='Max', nachname='Muster',
                mail_organisation='billing@muster.at')
    if with_address:
        c.strasse = 'Teststrasse 1'
        c.plz = '4020'
        c.stadt = 'Linz'
        c.land = 'Österreich'
    db.session.add(c)
    db.session.commit()

    doc = Document(
        contact_id=c.id, doc_type='invoice', number=number,
        subject='Testrechnung', status='final', date=date(2026, 7, 1),
        due_date=date(2026, 7, 15) if due else None, payment_term_days=14,
        discount_type='fixed' if discount else None,
        discount_value=discount or None,
    )
    db.session.add(doc)
    db.session.commit()

    g = LineItemGroup(document_id=doc.id, position=0, title='Leistungen')
    db.session.add(g)
    db.session.commit()
    db.session.add(LineItem(group_id=g.id, position=0, title='Beratung',
                            quantity=(-1 if negate else 1), unit='Stunden', unit_price=100,
                            vat_rate=rate, billing_type='onetime'))
    if second_rate is not None:
        db.session.add(LineItem(group_id=g.id, position=1, title='Sonderposten',
                                quantity=1, unit='Einmalig', unit_price=50,
                                vat_rate=second_rate, billing_type='onetime'))
    db.session.commit()
    return doc.id


def _xml(doc_id):
    doc = Document.query.get(doc_id)
    return build_zugferd_xml(doc, CompanySettings.get_all())


def _assert_valid(xml):
    xml_check_xsd(xml, flavor='factur-x', level='basic')
    xml_check_schematron(xml, flavor='factur-x', level='basic')


def test_standard_20_percent_valid(app):
    with app.app_context():
        xml = _xml(_make_invoice('R-T20', rate=20.0))
        _assert_valid(xml)
        assert b'<ram:CategoryCode>S</ram:CategoryCode>' in xml


def test_exempt_zero_percent_kleinunternehmer_valid(app):
    with app.app_context():
        xml = _xml(_make_invoice('R-T0', rate=0.0, due=False))
        _assert_valid(xml)
        assert b'<ram:CategoryCode>E</ram:CategoryCode>' in xml
        assert VAT_EXEMPTION_REASON.encode('utf-8') in xml


def test_buyer_without_address_valid(app):
    with app.app_context():
        xml = _xml(_make_invoice('R-TNA', rate=20.0, with_address=False))
        _assert_valid(xml)
        assert b'PostalTradeAddress' in xml
        assert b'<ram:CountryID>AT</ram:CountryID>' in xml


def test_mixed_rates_valid(app):
    with app.app_context():
        xml = _xml(_make_invoice('R-TMX', rate=20.0, second_rate=0.0))
        _assert_valid(xml)
        assert b'<ram:CategoryCode>S</ram:CategoryCode>' in xml
        assert b'<ram:CategoryCode>E</ram:CategoryCode>' in xml


def test_discount_valid(app):
    with app.app_context():
        xml = _xml(_make_invoice('R-TD', rate=20.0, discount=30.0))
        _assert_valid(xml)
        assert b'SpecifiedTradeAllowanceCharge' in xml
        assert b'<ram:AllowanceTotalAmount>30.00</ram:AllowanceTotalAmount>' in xml


def test_no_empty_payment_terms(app):
    with app.app_context():
        xml = _xml(_make_invoice('R-TPT', rate=20.0, due=False))
        _assert_valid(xml)
        assert b'<ram:SpecifiedTradePaymentTerms/>' not in xml
        assert b'<ram:SpecifiedTradePaymentTerms />' not in xml
        assert b'Zahlbar innerhalb' in xml


def test_tax_totals_are_internally_consistent(app):
    with app.app_context():
        xml = _xml(_make_invoice('R-TSUM', rate=20.0))
        assert b'<ram:TaxBasisTotalAmount>100.00</ram:TaxBasisTotalAmount>' in xml
        assert b'<ram:GrandTotalAmount>120.00</ram:GrandTotalAmount>' in xml


def test_credit_note_typecode_381(app):
    with app.app_context():
        xml = _xml(_make_invoice('R-TCN', rate=20.0, negate=True))
        _assert_valid(xml)
        assert b'<ram:TypeCode>381</ram:TypeCode>' in xml
        assert b'<ram:TypeCode>380</ram:TypeCode>' not in xml


def _blank_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_ensure_pdfa3_base_sets_trailer_id():
    base = _blank_pdf()
    assert PdfReader(io.BytesIO(base)).trailer.get('/ID') is None

    patched = _ensure_pdfa3_base(base)
    ids = PdfReader(io.BytesIO(patched)).trailer.get('/ID')
    assert ids is not None
    assert len(ids) == 2
    assert ids[0] == ids[1]


def test_ensure_pdfa3_base_adds_srgb_output_intent():
    patched = _ensure_pdfa3_base(_blank_pdf())
    root = PdfReader(io.BytesIO(patched)).trailer['/Root']
    intents = root.get('/OutputIntents')
    assert intents is not None and len(intents) == 1

    intent = intents[0].get_object()
    assert intent['/S'] == '/GTS_PDFA1'
    assert intent['/OutputConditionIdentifier'] == 'sRGB IEC61966-2.1'

    profile_stream = intent['/DestOutputProfile'].get_object()
    assert profile_stream['/N'] == 3
    assert profile_stream['/Alternate'] == '/DeviceRGB'
    icc_bytes = profile_stream.get_data()
    assert len(icc_bytes) > 100
    assert icc_bytes[36:40] == b'acsp'


def test_embed_zugferd_xml_output_is_pdfa3_hardened(app):
    with app.app_context():
        doc = Document.query.get(_make_invoice('R-TPDFA', rate=20.0))
        result = embed_zugferd_xml(_blank_pdf(), doc, CompanySettings.get_all())

    reader = PdfReader(io.BytesIO(result))
    assert reader.trailer.get('/ID') is not None
    assert reader.trailer['/Root'].get('/OutputIntents') is not None
    assert reader.trailer['/Root']['/Names']['/EmbeddedFiles'] is not None


def test_vat_rate_label_property(app):
    with app.app_context():
        from models import Document
        d20 = Document.query.get(_make_invoice('R-TL20', rate=20.0))
        assert d20.vat_rate_label == '20% '
        d0 = Document.query.get(_make_invoice('R-TL0', rate=0.0, due=False))
        assert d0.vat_rate_label == '0% '
        dmix = Document.query.get(_make_invoice('R-TLMX', rate=20.0, second_rate=10.0))
        assert dmix.vat_rate_label == ''
