import logging
from collections import OrderedDict
from datetime import date
from xml.etree.ElementTree import Element, SubElement, tostring

logger = logging.getLogger(__name__)

UNIT_CODE_MAP = {
    'Stunden': 'HUR',
    'Stunde': 'HUR',
    'Tage': 'DAY',
    'Tag': 'DAY',
    'Monate': 'MON',
    'Monat': 'MON',
    'Monatlich': 'MON',
    'Einmalig': 'C62',
    'Pauschal': 'C62',
    'Seite': 'C62',
    'Seiten': 'C62',
}

NS = {
    'rsm': 'urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100',
    'ram': 'urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100',
    'qdt': 'urn:un:unece:uncefact:data:standard:QualifiedDataType:100',
    'udt': 'urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100',
}


def _fmt_date(d):
    if isinstance(d, date):
        return d.strftime('%Y%m%d')
    return ''


def _fmt_amount(amount):
    return f'{float(amount):.2f}'


def _el(parent, tag, text=None, **attribs):
    el = SubElement(parent, tag, **attribs)
    if text is not None:
        el.text = str(text)
    return el


def _parse_zip_city(zip_city_str):
    if not zip_city_str:
        return '', ''
    parts = zip_city_str.strip().split(' ', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], ''


def _get_unit_code(unit_label):
    if not unit_label:
        return 'C62'
    return UNIT_CODE_MAP.get(unit_label, 'C62')


def _get_country_code(land):
    if not land:
        return 'AT'
    mapping = {
        'oesterreich': 'AT', 'austria': 'AT',
        'deutschland': 'DE', 'germany': 'DE',
        'schweiz': 'CH', 'switzerland': 'CH',
    }
    return mapping.get(land.lower().replace('ö', 'oe'), 'AT')


VAT_EXEMPTION_REASON = 'Steuerbefreiung für Kleinunternehmer gemäß § 6 Abs. 1 Z 27 UStG'


def _vat_category(rate):
    return 'S' if float(rate) > 0 else 'E'


def build_zugferd_xml(doc, company):
    contact = doc.contact

    for prefix, uri in NS.items():
        import xml.etree.ElementTree as ET
        ET.register_namespace(prefix, uri)

    root = Element(f'{{{NS["rsm"]}}}CrossIndustryInvoice')

    ctx = _el(root, f'{{{NS["rsm"]}}}ExchangedDocumentContext')
    guide = _el(ctx, f'{{{NS["ram"]}}}GuidelineSpecifiedDocumentContextParameter')
    _el(guide, f'{{{NS["ram"]}}}ID', 'urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic')

    is_credit_note = doc.total_net < 0
    exdoc = _el(root, f'{{{NS["rsm"]}}}ExchangedDocument')
    _el(exdoc, f'{{{NS["ram"]}}}ID', doc.number)
    _el(exdoc, f'{{{NS["ram"]}}}TypeCode', '381' if is_credit_note else '380')
    issue_dt = _el(exdoc, f'{{{NS["ram"]}}}IssueDateTime')
    _el(issue_dt, f'{{{NS["udt"]}}}DateTimeString', _fmt_date(doc.date), format='102')

    tx = _el(root, f'{{{NS["rsm"]}}}SupplyChainTradeTransaction')

    line_num = 0
    for group in doc.groups:
        for item in group.items:
            line_num += 1
            line = _el(tx, f'{{{NS["ram"]}}}IncludedSupplyChainTradeLineItem')

            line_doc = _el(line, f'{{{NS["ram"]}}}AssociatedDocumentLineDocument')
            _el(line_doc, f'{{{NS["ram"]}}}LineID', str(line_num))

            product = _el(line, f'{{{NS["ram"]}}}SpecifiedTradeProduct')
            name = item.title or f'Position {line_num}'
            if item.description:
                name = f'{name} ({item.description[:80]})'
            _el(product, f'{{{NS["ram"]}}}Name', name)

            agreement = _el(line, f'{{{NS["ram"]}}}SpecifiedLineTradeAgreement')
            net_price = _el(agreement, f'{{{NS["ram"]}}}NetPriceProductTradePrice')
            _el(net_price, f'{{{NS["ram"]}}}ChargeAmount', _fmt_amount(item.unit_price))

            delivery = _el(line, f'{{{NS["ram"]}}}SpecifiedLineTradeDelivery')
            _el(delivery, f'{{{NS["ram"]}}}BilledQuantity',
                _fmt_amount(item.quantity), unitCode=_get_unit_code(item.unit))

            settlement = _el(line, f'{{{NS["ram"]}}}SpecifiedLineTradeSettlement')
            line_tax = _el(settlement, f'{{{NS["ram"]}}}ApplicableTradeTax')
            _el(line_tax, f'{{{NS["ram"]}}}TypeCode', 'VAT')
            _el(line_tax, f'{{{NS["ram"]}}}CategoryCode', _vat_category(item.vat_rate))
            _el(line_tax, f'{{{NS["ram"]}}}RateApplicablePercent', _fmt_amount(item.vat_rate))

            line_total = _el(settlement, f'{{{NS["ram"]}}}SpecifiedTradeSettlementLineMonetarySummation')
            _el(line_total, f'{{{NS["ram"]}}}LineTotalAmount',
                _fmt_amount(float(item.quantity) * float(item.unit_price)))

    agreement = _el(tx, f'{{{NS["ram"]}}}ApplicableHeaderTradeAgreement')

    seller = _el(agreement, f'{{{NS["ram"]}}}SellerTradeParty')
    _el(seller, f'{{{NS["ram"]}}}Name', company.get('company_name', ''))

    seller_addr = _el(seller, f'{{{NS["ram"]}}}PostalTradeAddress')
    plz, city = _parse_zip_city(company.get('zip_city', ''))
    _el(seller_addr, f'{{{NS["ram"]}}}PostcodeCode', plz)
    _el(seller_addr, f'{{{NS["ram"]}}}LineOne', company.get('street', ''))
    _el(seller_addr, f'{{{NS["ram"]}}}CityName', city)
    _el(seller_addr, f'{{{NS["ram"]}}}CountryID', 'AT')

    if company.get('uid'):
        tax_reg_va = _el(seller, f'{{{NS["ram"]}}}SpecifiedTaxRegistration')
        _el(tax_reg_va, f'{{{NS["ram"]}}}ID', company['uid'], schemeID='VA')
    if company.get('tax_number'):
        tax_reg_fc = _el(seller, f'{{{NS["ram"]}}}SpecifiedTaxRegistration')
        _el(tax_reg_fc, f'{{{NS["ram"]}}}ID', company['tax_number'], schemeID='FC')
    if not company.get('uid') and not company.get('tax_number'):
        tax_reg_fc = _el(seller, f'{{{NS["ram"]}}}SpecifiedTaxRegistration')
        _el(tax_reg_fc, f'{{{NS["ram"]}}}ID', 'UNKNOWN', schemeID='FC')

    buyer = _el(agreement, f'{{{NS["ram"]}}}BuyerTradeParty')
    buyer_name = contact.billing_name or f'{contact.vorname or ""} {contact.nachname or ""}'.strip()
    _el(buyer, f'{{{NS["ram"]}}}Name', buyer_name)

    buyer_addr = _el(buyer, f'{{{NS["ram"]}}}PostalTradeAddress')
    if contact.billing_plz:
        _el(buyer_addr, f'{{{NS["ram"]}}}PostcodeCode', contact.billing_plz)
    if contact.billing_strasse:
        _el(buyer_addr, f'{{{NS["ram"]}}}LineOne', contact.billing_strasse)
    if contact.billing_stadt:
        _el(buyer_addr, f'{{{NS["ram"]}}}CityName', contact.billing_stadt)
    _el(buyer_addr, f'{{{NS["ram"]}}}CountryID', _get_country_code(contact.billing_land))

    if contact.billing_uid:
        buyer_tax = _el(buyer, f'{{{NS["ram"]}}}SpecifiedTaxRegistration')
        _el(buyer_tax, f'{{{NS["ram"]}}}ID', contact.billing_uid, schemeID='VA')

    delivery_header = _el(tx, f'{{{NS["ram"]}}}ApplicableHeaderTradeDelivery')
    actual_delivery = _el(delivery_header, f'{{{NS["ram"]}}}ActualDeliverySupplyChainEvent')
    occ_dt = _el(actual_delivery, f'{{{NS["ram"]}}}OccurrenceDateTime')
    _el(occ_dt, f'{{{NS["udt"]}}}DateTimeString', _fmt_date(doc.date), format='102')

    settlement = _el(tx, f'{{{NS["ram"]}}}ApplicableHeaderTradeSettlement')
    _el(settlement, f'{{{NS["ram"]}}}InvoiceCurrencyCode', 'EUR')

    payment = _el(settlement, f'{{{NS["ram"]}}}SpecifiedTradeSettlementPaymentMeans')
    _el(payment, f'{{{NS["ram"]}}}TypeCode', '58')
    if company.get('iban'):
        payer_account = _el(payment, f'{{{NS["ram"]}}}PayeePartyCreditorFinancialAccount')
        _el(payer_account, f'{{{NS["ram"]}}}IBANID', company['iban'].replace(' ', ''))

    rate_nets = OrderedDict()
    for group in doc.groups:
        for item in group.items:
            r = round(float(item.vat_rate), 2)
            rate_nets[r] = round(rate_nets.get(r, 0.0) + item.line_total, 2)
    if not rate_nets:
        rate_nets[20.0] = 0.0

    total_net = doc.total_net
    discount = float(doc.discount_amount) if doc.has_discount else 0.0
    allow_by_rate = {}
    if discount > 0 and total_net > 0:
        for r, net in rate_nets.items():
            allow_by_rate[r] = round(discount * net / total_net, 2)

    tax_basis_total = 0.0
    tax_total = 0.0
    for r, net in rate_nets.items():
        basis = round(net - allow_by_rate.get(r, 0.0), 2)
        calc = round(basis * r / 100, 2)
        tax_basis_total = round(tax_basis_total + basis, 2)
        tax_total = round(tax_total + calc, 2)
        trade_tax = _el(settlement, f'{{{NS["ram"]}}}ApplicableTradeTax')
        _el(trade_tax, f'{{{NS["ram"]}}}CalculatedAmount', _fmt_amount(calc))
        _el(trade_tax, f'{{{NS["ram"]}}}TypeCode', 'VAT')
        if _vat_category(r) == 'E':
            _el(trade_tax, f'{{{NS["ram"]}}}ExemptionReason', VAT_EXEMPTION_REASON)
        _el(trade_tax, f'{{{NS["ram"]}}}BasisAmount', _fmt_amount(basis))
        _el(trade_tax, f'{{{NS["ram"]}}}CategoryCode', _vat_category(r))
        _el(trade_tax, f'{{{NS["ram"]}}}RateApplicablePercent', _fmt_amount(r))

    if discount > 0 and total_net > 0:
        for r, net in rate_nets.items():
            amt = allow_by_rate.get(r, 0.0)
            if amt <= 0:
                continue
            allowance = _el(settlement, f'{{{NS["ram"]}}}SpecifiedTradeAllowanceCharge')
            ind = _el(allowance, f'{{{NS["ram"]}}}ChargeIndicator')
            _el(ind, f'{{{NS["udt"]}}}Indicator', 'false')
            _el(allowance, f'{{{NS["ram"]}}}ActualAmount', _fmt_amount(amt))
            _el(allowance, f'{{{NS["ram"]}}}Reason', 'Rabatt')
            cat_tax = _el(allowance, f'{{{NS["ram"]}}}CategoryTradeTax')
            _el(cat_tax, f'{{{NS["ram"]}}}TypeCode', 'VAT')
            _el(cat_tax, f'{{{NS["ram"]}}}CategoryCode', _vat_category(r))
            _el(cat_tax, f'{{{NS["ram"]}}}RateApplicablePercent', _fmt_amount(r))

    grand_total = round(tax_basis_total + tax_total, 2)
    if doc.due_date:
        terms = _el(settlement, f'{{{NS["ram"]}}}SpecifiedTradePaymentTerms')
        due_dt = _el(terms, f'{{{NS["ram"]}}}DueDateDateTime')
        _el(due_dt, f'{{{NS["udt"]}}}DateTimeString', _fmt_date(doc.due_date), format='102')
    elif grand_total > 0:
        terms = _el(settlement, f'{{{NS["ram"]}}}SpecifiedTradePaymentTerms')
        _el(terms, f'{{{NS["ram"]}}}Description',
            f'Zahlbar innerhalb von {doc.payment_term_days} Tagen ab Rechnungserhalt.')

    summary = _el(settlement, f'{{{NS["ram"]}}}SpecifiedTradeSettlementHeaderMonetarySummation')
    _el(summary, f'{{{NS["ram"]}}}LineTotalAmount', _fmt_amount(doc.total_net))
    if discount > 0:
        _el(summary, f'{{{NS["ram"]}}}AllowanceTotalAmount', _fmt_amount(discount))
    _el(summary, f'{{{NS["ram"]}}}TaxBasisTotalAmount', _fmt_amount(tax_basis_total))
    _el(summary, f'{{{NS["ram"]}}}TaxTotalAmount', _fmt_amount(tax_total), currencyID='EUR')
    _el(summary, f'{{{NS["ram"]}}}GrandTotalAmount', _fmt_amount(grand_total))
    _el(summary, f'{{{NS["ram"]}}}DuePayableAmount', _fmt_amount(grand_total))

    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_body = tostring(root, encoding='unicode', xml_declaration=False)
    return (xml_declaration + xml_body).encode('utf-8')


def _ensure_pdfa3_base(pdf_bytes):
    import io

    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (
        ArrayObject, DecodedStreamObject, DictionaryObject,
        NameObject, NumberObject, TextStringObject,
    )
    from PIL import ImageCms

    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)

    writer.generate_file_identifiers()

    icc_bytes = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    icc_stream = DecodedStreamObject()
    icc_stream.set_data(icc_bytes)
    icc_stream[NameObject('/N')] = NumberObject(3)
    icc_stream[NameObject('/Alternate')] = NameObject('/DeviceRGB')
    icc_ref = writer._add_object(icc_stream)

    output_intent = DictionaryObject()
    output_intent[NameObject('/Type')] = NameObject('/OutputIntent')
    output_intent[NameObject('/S')] = NameObject('/GTS_PDFA1')
    output_intent[NameObject('/OutputConditionIdentifier')] = TextStringObject('sRGB IEC61966-2.1')
    output_intent[NameObject('/Info')] = TextStringObject('sRGB IEC61966-2.1')
    output_intent[NameObject('/RegistryName')] = TextStringObject('http://www.color.org')
    output_intent[NameObject('/DestOutputProfile')] = icc_ref
    intent_ref = writer._add_object(output_intent)

    writer.root_object[NameObject('/OutputIntents')] = ArrayObject([intent_ref])

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def embed_zugferd_xml(pdf_bytes, doc, company):
    from facturx import generate_from_binary

    xml_data = build_zugferd_xml(doc, company)

    try:
        pdf_with_xml = generate_from_binary(
            pdf_bytes,
            xml_data,
            flavor='factur-x',
            level='basic',
            check_xsd=True,
            check_schematron=False,
        )
    except Exception as e:
        logger.warning(f'ZUGFeRD embedding failed for {doc.number}: {e}')
        raise

    try:
        pdf_with_xml = _ensure_pdfa3_base(pdf_with_xml)
    except Exception as e:
        logger.warning(f'PDF/A-3-Haertung fehlgeschlagen fuer {doc.number} (XML bleibt eingebettet): {e}')

    logger.info(f'ZUGFeRD XML embedded in invoice {doc.number}')
    return pdf_with_xml
