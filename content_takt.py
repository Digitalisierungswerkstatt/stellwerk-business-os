from datetime import date, timedelta

ANKER = date(2024, 1, 1)
HORIZONT_WOCHEN = 4

EINHEIT_TEXT = {'woche': ('Woche', 'Wochen'), 'monat': ('Monat', 'Monate')}

_KUNDE_SQL = """COALESCE(NULLIF(c.organisation, ''),
                NULLIF(TRIM(COALESCE(c.vorname, '') || ' ' || COALESCE(c.nachname, '')), ''),
                'ohne Kontakt')"""


def _datum(wert):
    if wert is None or wert == '':
        return None
    if isinstance(wert, date):
        return wert
    return date.fromisoformat(str(wert)[:10])


def label(takt):
    einzahl, mehrzahl = EINHEIT_TEXT[takt['einheit']]
    je = einzahl if takt['intervall'] == 1 else f"{takt['intervall']} {mehrzahl}"
    return f"{takt['anzahl']} je {je}"


MONATE = ['Jän', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']


def periode_text(start, ende, einheit):
    letzter = ende - timedelta(days=1)
    if einheit == 'woche':
        a, b = start.isocalendar()[1], letzter.isocalendar()[1]
        return f"KW {a}" if a == b else f"KW {a}–{b}"
    if (start.year, start.month) == (letzter.year, letzter.month):
        return f"{MONATE[start.month - 1]} {start.year}"
    return f"{MONATE[start.month - 1]}–{MONATE[letzter.month - 1]} {letzter.year}"


def _monat_plus(jahr, monat, n):
    i = jahr * 12 + (monat - 1) + n
    return date(i // 12, i % 12 + 1, 1)


def perioden(takt, heute, horizont_wochen=HORIZONT_WOCHEN):
    bis = heute + timedelta(weeks=horizont_wochen)
    ab, ende_gueltig = _datum(takt.get('gueltig_ab')), _datum(takt.get('gueltig_bis'))
    if ende_gueltig and ende_gueltig < heute:
        return []
    ergebnis = []
    if takt['einheit'] == 'woche':
        anker = (ab - timedelta(days=ab.weekday())) if ab else ANKER
        laenge = timedelta(weeks=takt['intervall'])
        k = max(0, (heute - anker).days // laenge.days)
        start = anker + k * laenge
        while start <= bis:
            ergebnis.append((start, start + laenge))
            start += laenge
    else:
        anker = date(ab.year, ab.month, 1) if ab else ANKER
        diff = (heute.year - anker.year) * 12 + heute.month - anker.month
        k = max(0, diff // takt['intervall'])
        while True:
            start = _monat_plus(anker.year, anker.month, k * takt['intervall'])
            if start > bis:
                break
            ergebnis.append((start, _monat_plus(start.year, start.month, takt['intervall'])))
            k += 1
    ergebnis = [(s, e) for s, e in ergebnis if e > heute]
    if ende_gueltig:
        ergebnis = [(s, e) for s, e in ergebnis if s <= ende_gueltig]
    return ergebnis


def abdeckung(takte, eintraege, heute, horizont_wochen=HORIZONT_WOCHEN):
    ergebnis = []
    for takt in takte:
        zeilen = []
        for start, ende in perioden(takt, heute, horizont_wochen):
            treffer = [e for e in eintraege
                       if e['contact_id'] == takt['contact_id'] and e['platform'] == takt['platform']
                       and start <= e['termin'] < ende]
            zeilen.append(dict(start=start, ende=ende, text=periode_text(start, ende, takt['einheit']),
                               ist=len(treffer), soll=takt['anzahl'],
                               eintraege=treffer, luecke=len(treffer) < takt['anzahl']))
        ergebnis.append(dict(takt=takt, label=label(takt), perioden=zeilen))
    return ergebnis


def luecken(abdeckung_liste):
    return [(a['takt'], p) for a in abdeckung_liste for p in a['perioden'] if p['luecke']]


def lade(con, heute):
    cur = con.cursor()
    cur.execute(f"""
        SELECT t.id, t.contact_id, {_KUNDE_SQL}, t.platform, t.anzahl, t.intervall,
               t.einheit, t.gueltig_ab, t.gueltig_bis, t.notiz
          FROM content_takte t LEFT JOIN contacts c ON c.id = t.contact_id
      ORDER BY 3, t.platform, t.gueltig_ab""")
    takte = [dict(id=r[0], contact_id=r[1], kunde=r[2], platform=r[3], anzahl=r[4],
                  intervall=r[5], einheit=r[6], gueltig_ab=_datum(r[7]),
                  gueltig_bis=_datum(r[8]), notiz=r[9]) for r in cur.fetchall()]
    cur.execute("""SELECT id, contact_id, platform, scheduled_for, status, title
                     FROM content_calendar WHERE scheduled_for IS NOT NULL""")
    eintraege = [dict(id=r[0], contact_id=r[1], platform=r[2], termin=_datum(r[3]),
                      status=r[4], title=r[5]) for r in cur.fetchall()]
    gueltig = {t['contact_id'] for t in takte if not t['gueltig_bis'] or t['gueltig_bis'] >= heute}
    cur.execute(f"""SELECT c.id, {_KUNDE_SQL} FROM contacts c
                     WHERE c.contact_type = 'customer' AND c.has_social_mandate = 1
                       AND COALESCE(c.archived, 0) = 0 ORDER BY 2""")
    ohne = [dict(contact_id=r[0], kunde=r[1]) for r in cur.fetchall() if r[0] not in gueltig]
    return takte, eintraege, ohne
