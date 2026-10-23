import csv
import hashlib
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


class BankFormatError(ValueError):
    pass


REQUIRED_FIELDS = {'booking_date', 'amount'}

SCHEMAS = [
    {
        'name': 'n26_en',
        'decimal': '.',
        'date_formats': ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'),
        'columns': {
            'Booking Date': 'booking_date',
            'Value Date': 'value_date',
            'Partner Name': 'partner_name',
            'Partner Iban': 'partner_iban',
            'Partner IBAN': 'partner_iban',
            'Type': 'tx_type',
            'Transaction Type': 'tx_type',
            'Payment Reference': 'reference',
            'Amount (EUR)': 'amount',
            'Amount': 'amount',
            'Original Amount': 'foreign_amount',
            'Original Currency': 'foreign_currency',
            'Exchange Rate': 'exchange_rate',
        },
    },
    {
        'name': 'n26_de',
        'decimal': ',',
        'date_formats': ('%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y'),
        'columns': {
            'Datum': 'booking_date',
            'Buchungsdatum': 'booking_date',
            'Wertstellung': 'value_date',
            'Empfänger': 'partner_name',
            'Empfaenger': 'partner_name',
            'Kontonummer': 'partner_iban',
            'Transaktionstyp': 'tx_type',
            'Verwendungszweck': 'reference',
            'Betrag (EUR)': 'amount',
            'Betrag': 'amount',
            'Betrag (Fremdwährung)': 'foreign_amount',
            'Betrag (Fremdwaehrung)': 'foreign_amount',
            'Fremdwährung': 'foreign_currency',
            'Fremdwaehrung': 'foreign_currency',
            'Wechselkurs': 'exchange_rate',
        },
    },
]

_TEXT_FIELDS = ('partner_name', 'partner_iban', 'reference', 'tx_type')


def _parse_amount(raw, decimal_sep=None):
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = re.sub(r'[^\d,.\-+]', '', s)
    if not re.search(r'\d', s):
        return None
    if decimal_sep is None:
        last_comma, last_dot = s.rfind(','), s.rfind('.')
        decimal_sep = ',' if last_comma > last_dot else '.'
    if decimal_sep == ',':
        s = s.replace('.', '').replace(',', '.')
    else:
        s = s.replace(',', '')
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _parse_date(raw, formats=('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y')):
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def compute_row_hash(row, occurrence):
    booking = row.get('booking_date')
    amount = row.get('amount') or Decimal('0')
    parts = [
        booking.strftime('%Y-%m-%d') if booking else '',
        f'{Decimal(amount):.2f}',
        (row.get('partner_iban') or '').strip(),
        (row.get('reference') or '').strip(),
        str(occurrence),
    ]
    return hashlib.sha256('|'.join(parts).encode('utf-8')).hexdigest()


def assign_occurrences(rows):
    seen = {}
    for row in rows:
        key = (row.get('booking_date'), row.get('amount'),
               row.get('reference'), row.get('partner_iban'))
        row['occurrence'] = seen.get(key, 0)
        seen[key] = row['occurrence'] + 1
    return rows


def _detect_schema(headers):
    present = {h.strip() for h in headers if h}
    best, best_score = None, 0
    for schema in SCHEMAS:
        matched = [src for src in schema['columns'] if src in present]
        targets = {schema['columns'][src] for src in matched}
        if not REQUIRED_FIELDS <= targets:
            continue
        if len(matched) > best_score:
            best, best_score = schema, len(matched)
    if best is None:
        found = ', '.join(sorted(present)) or '(keine)'
        raise BankFormatError(
            'Kein bekanntes Spalten-Schema erkannt. Gefundene Spalten: '
            f'{found}. Erwartet wird ein N26-CSV-Export mit Buchungsdatum und '
            'Betrag (englisch "Booking Date"/"Amount (EUR)" oder deutsch '
            '"Datum"/"Betrag (EUR)"). Bitte den Export unveraendert hochladen.'
        )
    return best


def parse_csv(source):
    text = source if isinstance(source, str) else source.read()
    text = text.lstrip('﻿')
    if not text.strip():
        raise BankFormatError('Die Datei ist leer.')

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise BankFormatError('Die Datei hat keine Kopfzeile.')

    schema = _detect_schema(reader.fieldnames)
    mapping = {src.strip(): target for src, target in schema['columns'].items()}

    rows = []
    for raw in reader:
        row = {'currency': 'EUR'}
        for header, value in raw.items():
            target = mapping.get((header or '').strip())
            if not target:
                continue
            if target in ('booking_date', 'value_date'):
                row[target] = _parse_date(value, schema['date_formats'])
            elif target in ('amount', 'foreign_amount', 'exchange_rate'):
                row[target] = _parse_amount(value, schema['decimal'])
            elif target == 'foreign_currency':
                code = (value or '').strip().upper()
                row['foreign_currency'] = code if code and code != 'EUR' else None
            else:
                row[target] = (value or '').strip() or None

        if row.get('booking_date') is None or row.get('amount') is None:
            continue
        if not row.get('foreign_currency'):
            row['foreign_currency'] = None
            row['foreign_amount'] = None
        for field in _TEXT_FIELDS:
            row.setdefault(field, None)
        row.setdefault('foreign_currency', None)
        row.setdefault('foreign_amount', None)
        rows.append(row)

    assign_occurrences(rows)
    for row in rows:
        row['row_hash'] = compute_row_hash(row, row['occurrence'])
    return rows, schema['name']
