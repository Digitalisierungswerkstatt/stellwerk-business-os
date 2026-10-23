import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

TEMPLATE_DIR = Path(__file__).parent.parent / 'templates'

ALPINE_ONLY_ERLAUBT = {
    ('content_calendar.html', 'view', 'activeView'):
        'GET-Filterformular. Steuert nur die Ansicht (Monat/Woche/Board), wird nie in die '
        'DB geschrieben. Ohne Alpine faellt die Ansicht auf den Server-Default zurueck, '
        'es geht kein gespeicherter Wert verloren.',

    ('timetracking.html', 'contact_id', 'addContactId'):
        'Neuanlage-Formular (timetracking_add). Es gibt keinen serverseitigen Ist-Wert, den '
        'ein leeres Feld ueberschreiben koennte. Ohne Alpine ist das Suchfeld ohnehin '
        'unbedienbar, es entsteht hoechstens ein Eintrag ohne Kontakt statt eines geloeschten.',

    ('timetracking.html', 'contact_id', 'filterContactId'):
        'GET-Filter der Zeitenliste. Schreibt nichts in die DB, ein leerer Wert bedeutet '
        'schlicht "alle Kontakte" und ist damit ein gueltiger Zustand.',
}

INPUT_TAG = re.compile(r'<input\b[^>]*>', re.S)
ALPINE_VALUE = re.compile(r':value\s*=\s*"([^"]*)"')
STATIC_VALUE = re.compile(r'(?<![:\w-])value\s*=\s*"')
NAME_ATTR = re.compile(r'\bname\s*=\s*"([^"]*)"')


def _hidden_alpine_felder():
    treffer = []
    for pfad in sorted(TEMPLATE_DIR.rglob('*.html')):
        markup = pfad.read_text(encoding='utf-8')
        for tag in INPUT_TAG.findall(markup):
            if 'type="hidden"' not in tag:
                continue
            gebunden = ALPINE_VALUE.search(tag)
            if not gebunden:
                continue
            name = NAME_ATTR.search(tag)
            treffer.append((
                pfad.name,
                name.group(1) if name else '<ohne name>',
                gebunden.group(1).strip(),
                bool(STATIC_VALUE.search(tag)),
            ))
    return treffer


def test_templates_ueberhaupt_gefunden():
    assert TEMPLATE_DIR.is_dir(), f'Template-Verzeichnis fehlt: {TEMPLATE_DIR}'
    assert len(_hidden_alpine_felder()) >= 5, \
        'Zu wenige hidden-Alpine-Felder gefunden — Regex oder Pfad kaputt, nicht das Repo sauber'


def test_hidden_felder_tragen_den_ist_wert():
    ungedeckt = []
    for datei, name, ausdruck, hat_static in _hidden_alpine_felder():
        if hat_static:
            continue
        if (datei, name, ausdruck) in ALPINE_ONLY_ERLAUBT:
            continue
        ungedeckt.append(f'{datei}: name="{name}" :value="{ausdruck}"')

    assert not ungedeckt, (
        'hidden field haengt allein an Alpine (CDN, defer). Faellt das CDN aus, sendet das '
        'Formular hier leer und ein Vollueberschreiber nullt den Wert still.\n'
        'Entweder value="{{ ...ist_wert... }}" ergaenzen oder mit Begruendung in '
        'ALPINE_ONLY_ERLAUBT eintragen:\n  ' + '\n  '.join(ungedeckt)
    )


def test_registry_hat_keine_leichen():
    offen = {(d, n, a) for d, n, a, static in _hidden_alpine_felder() if not static}
    verwaist = sorted(set(ALPINE_ONLY_ERLAUBT) - offen)
    assert not verwaist, \
        f'Ausnahme ohne Fundstelle im Markup, bitte entfernen: {verwaist}'


@pytest.mark.parametrize('schluessel', sorted(ALPINE_ONLY_ERLAUBT))
def test_ausnahmen_sind_begruendet(schluessel):
    begruendung = ALPINE_ONLY_ERLAUBT[schluessel].strip()
    assert len(begruendung) >= 30, f'Begruendung zu duenn fuer {schluessel}'
    assert not re.search(r'\b(TODO|TBD|FIXME|noch offen|siehe oben)\b', begruendung, re.I), \
        f'Platzhalter statt Begruendung bei {schluessel}'
