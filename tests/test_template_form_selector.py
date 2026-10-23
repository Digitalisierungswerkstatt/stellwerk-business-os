import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / 'templates'

ERWEITERT_BASE = re.compile(r"""\{%-?\s*extends\s+['"]base\.html['"]""")

ERSTES_FORMULAR = re.compile(
    r"""querySelector\(\s*['"]\s*form\s*['"]\s*\)"""
    r"""|\bforms\s*\[\s*0\s*\]"""
    r"""|getElementsByTagName\(\s*['"]form['"]\s*\)\s*\[\s*0\s*\]"""
)


def _seiten_templates():
    return [p for p in sorted(TEMPLATES.rglob('*.html'))
            if ERWEITERT_BASE.search(p.read_text(encoding='utf-8'))]


def test_templates_ueberhaupt_gefunden():
    assert TEMPLATES.is_dir(), f'Template-Verzeichnis fehlt: {TEMPLATES}'
    assert len(_seiten_templates()) >= 30, \
        'Zu wenige Templates mit extends base.html gefunden: Regex oder Pfad kaputt, nicht das Repo sauber'


@pytest.mark.parametrize('schnipsel', [
    "const form = document.querySelector('form');",
    'document.querySelector("form").submit();',
    'const f = document.forms[0];',
    "document.getElementsByTagName('form')[0].submit();",
])
def test_regex_erkennt_das_erste_formular(schnipsel):
    assert ERSTES_FORMULAR.search(schnipsel)


@pytest.mark.parametrize('schnipsel', [
    """document.querySelector('form[method="POST"]').submit();""",
    "document.querySelectorAll('form').forEach(f => f.reset());",
    "const form = feld.closest('form');",
    "const form = document.querySelector('[name=organisation]').form;",
])
def test_regex_laesst_benannte_auswahl_durch(schnipsel):
    assert not ERSTES_FORMULAR.search(schnipsel)


def test_kein_template_nimmt_das_erste_formular():
    treffer = []
    for pfad in _seiten_templates():
        for nr, zeile in enumerate(pfad.read_text(encoding='utf-8').splitlines(), 1):
            if ERSTES_FORMULAR.search(zeile):
                treffer.append(f'{pfad.relative_to(TEMPLATES)}:{nr}: {zeile.strip()}')

    assert not treffer, (
        'Das erste <form> jeder Seite ist die Suche im Kopf (base.html). Diese Stellen '
        'bekommen die Suche statt ihres Formulars. Das Formular benennen, z.B. '
        'document.querySelector(\'form[method="POST"]\'):\n  ' + '\n  '.join(treffer)
    )


def test_base_hat_kein_post_formular():
    formulare = re.findall(r'<form\b[^>]*>', (TEMPLATES / 'base.html').read_text(encoding='utf-8'))
    assert formulare, 'Kein <form> in base.html gefunden, die Suche muesste da sein: Regex oder Pfad kaputt'

    post = [f for f in formulare if re.search(r"""method\s*=\s*['"]?post""", f, re.I)]
    assert not post, (
        'base.html hat ein POST-Formular. Die Ctrl+S-Handler waehlen form[method="POST"] '
        'und wuerden es vor dem eigenen Formular finden:\n  ' + '\n  '.join(post)
    )
