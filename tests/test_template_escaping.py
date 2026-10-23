import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / 'templates'

DATENFELD = re.compile(
    r'\$\{\s*(?!escapeHtml\(|encodeURIComponent\()'
    r'[A-Za-z_]+\.(name|sub|email|url|error|existing_name|initial|status|title|label|'
    r'organisation|notes|text|subject|file_path)\b(?!\s*\?)')
HTML_ZEILE = re.compile(r'<[A-Za-z/]')

JINJA = re.compile(r'\{\{.*?\}\}', re.S)
JS_ATTR = re.compile(r'''(?<=\s)(x-[\w:.-]+|@[\w.:-]+|:[\w.-]+|on[a-z]+)\s*=\s*("([^"]*)"|'([^']*)')''', re.S)
HARMLOS = re.compile(
    r'''^(?:[\w.]*\bid|[\w.]*_id|loop\.\w+|url_for\(.*\)|\d+|[\w.\[\]:]+\s*\|\s*(?:length|int|float)'''
    r'''|.*\.isoformat\(\)(?: if .* else '')?|.*\.strftime\('[^']*'\)(?: if .* else '')?'''
    r'''|'true' if .* else 'false'|',' if not loop\.last|\[[\w.]+, \d+\]\|max if .* else 0)$''')
GEPRUEFT = {
    ('board.html', 'stage_key'), ('pipeline.html', 'stage_key'),
    ('contact_view.html', 'value'), ('contacts.html', 'value'),
    ('contact_view.html', 'status_active[value]'), ('contact_view.html', 'status_btn[value]'),
    ('contact_view.html', "kontakt_wie_options[1][0] if kontakt_wie_options|length > 1 else ''"),
    ('dashboard.html', 'wid'), ('dashboard.html', 'stats.get(stage_key, 0)'),
    ('goals.html', 'paid_w'), ('goals.html', 'open_w'),
    ('document_view.html', 'document.type_label'), ('document_view.html', 'document.number'),
    ('bank.html', "tx.booking_date.strftime('%d.%m.%Y')"),
    ('bank.html', "'%.2f'|format(tx.amount|float)"),
    ('content_calendar.html', 'due_count'),
    ('board.html', "task.display_score or ''"), ('board.html', "task.recurrence_days or ''"),
    ('board_task_detail.html', "task.contact_id or ''"),
    ('board_task_form.html', "preselect_contact or ''"),
    ('content_calendar_form.html',
     "entry.contact_id if entry and entry.contact_id else (preselect_contact or '')"),
    ('timetracking.html', "entry.contact_id or ''"),
}


def _templates():
    return [p for p in TEMPLATES.rglob('*.html') if '.bak' not in p.name]


def _ist_sicher(datei, ausdruck, quote):
    a = re.sub(r'\s*\|\s*', '|', ausdruck.strip())
    if a.endswith('|tojson|forceescape'):
        return True
    if quote == "'" and a.endswith('|tojson'):
        return True
    if re.search(r'\|tojson_(service|group_template)$', a):
        return True
    return bool(HARMLOS.match(a)) or (datei, ausdruck.strip()) in GEPRUEFT


def js_attribut_funde(text, datei):
    platz = []

    def merken(m):
        platz.append(m.group(0))
        return f'\x00{len(platz) - 1}\x00'

    t = JINJA.sub(merken, text)
    funde = []
    for m in JS_ATTR.finditer(t):
        wert = m.group(3) if m.group(3) is not None else m.group(4)
        for i in re.findall(r'\x00(\d+)\x00', wert):
            ausdruck = platz[int(i)][2:-2].strip()
            if not _ist_sicher(datei, ausdruck, m.group(2)[0]):
                zeile = t[:m.start()].count('\n') + 1
                funde.append(f'{datei}:{zeile}: {m.group(1)} -> {ausdruck}')
    return funde


def test_koeder_alle_muster_greifen():
    assert DATENFELD.search('list.innerHTML = `<div>${c.name}</div>`')
    assert not DATENFELD.search('`<div>${escapeHtml(c.name)}</div>`')
    assert not DATENFELD.search('${c.sub ? `<div>${escapeHtml(c.sub)}</div>` : ""}')
    for boese in ('''<div x-data="{ v: '{{ view }}' }">''',
                  '''<b @click="f('{{ c.name|e }}')">''',
                  '''<b onclick="copy('{{ fl.file_path|e }}')">''',
                  '''<b x-data="{ n: {{ c.name|tojson }} }">'''):
        assert js_attribut_funde(' ' + boese, 'x.html'), boese
    for gut in ('''<div x-data="{ v: {{ view|tojson|forceescape }} }">''',
                '''<b @click='f({{ c.name | tojson }})'>''',
                '''<b @click="f({{ task.id }}, '{{ d.isoformat() }}')">'''):
        assert not js_attribut_funde(' ' + gut, 'x.html'), gut
    namen = {p.name for p in _templates()}
    assert {'base.html', 'contact_view.html', 'import.html'} <= namen, \
        'Templates nicht gefunden, Waechter waere blind'


def test_keine_rohen_datenfelder_in_template_literals():
    funde = []
    for p in _templates():
        for n, zeile in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
            if HTML_ZEILE.search(zeile) and DATENFELD.search(zeile):
                funde.append(f'{p.relative_to(TEMPLATES)}:{n}: {zeile.strip()[:120]}')
    assert not funde, 'Datenfeld ohne escapeHtml():\n' + '\n'.join(funde)


def test_js_attribute_nur_sichere_werte():
    funde = []
    for p in _templates():
        funde += js_attribut_funde(p.read_text(encoding='utf-8'), p.name)
    assert not funde, ('Jinja-Wert in JS-Attribut ohne |tojson|forceescape:\n'
                       + '\n'.join(funde))
